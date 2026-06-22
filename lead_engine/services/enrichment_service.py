"""Profile enrichment service — batch and single company enrichment."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from config.settings import get_settings
from crawlers.enf_profile import ENFProfileCrawler
from models.company import Company, CrawlStatus, EnrichmentStatus
from models.company_profile import CompanyProfile
from models.crawl_job import CrawlJob, CrawlJobStatus, CrawlJobType
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EnrichmentResult:
    success: bool
    company_id: int | None
    company_name: str
    message: str
    website: str | None = None
    error: str | None = None


@dataclass
class BatchEnrichmentResult:
    success: bool
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    stopped_reason: str = ""
    results: List[EnrichmentResult] = field(default_factory=list)
    message: str = ""


class EnrichmentService:
    def __init__(self, session: Session):
        self.session = session
        self.crawler = ENFProfileCrawler()

    def _pending_query(self, country: str | None = None):
        query = self.session.query(Company).filter(
            Company.enrichment_status == EnrichmentStatus.PENDING,
            Company.crawl_status.in_(
                [CrawlStatus.DISCOVERED, CrawlStatus.PENDING]
            ),
            or_(Company.website.is_(None), Company.website == ""),
        )
        if country:
            query = query.filter(Company.country == country)
        return query.order_by(
            Company.discovered_at.asc().nullsfirst(), Company.id.asc()
        )

    def get_next_pending_company(self) -> Company | None:
        return self._pending_query().first()

    def get_pending_companies(
        self, limit: int | None = None, country: str | None = None
    ) -> List[Company]:
        settings = get_settings()
        batch_limit = limit or settings.enrichment_batch_size
        return self._pending_query(country=country).limit(batch_limit).all()

    def enrich_next_company(self, country: str | None = None) -> EnrichmentResult:
        company = self._pending_query(country=country).first()
        if not company:
            return EnrichmentResult(
                success=False,
                company_id=None,
                company_name="",
                message="No pending companies to enrich",
            )
        try:
            result = self._enrich_company(
                company_id=company.id,
                company_name=company.company_name,
                enf_profile_url=company.enf_profile_url,
            )
            self.session.commit()
            return result
        except Exception as exc:
            self.session.rollback()
            result = self._mark_enrichment_failed(
                company.id, company.company_name, str(exc)
            )
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
            return result

    def enrich_batch(
        self,
        country: str | None = None,
        batch_size: int | None = None,
        on_progress=None,
    ) -> BatchEnrichmentResult:
        settings = get_settings()
        limit = batch_size or settings.enrichment_batch_size
        companies = self.get_pending_companies(limit=limit, country=country)
        company_rows = [
            {
                "id": company.id,
                "name": company.company_name,
                "enf_profile_url": company.enf_profile_url,
            }
            for company in companies
        ]

        if not company_rows:
            return BatchEnrichmentResult(
                success=False,
                stopped_reason="no_pending",
                message="No pending companies left to enrich",
            )

        results: List[EnrichmentResult] = []
        succeeded = 0
        failed = 0

        for index, company_row in enumerate(company_rows, start=1):
            if on_progress:
                on_progress(index, len(company_rows), company_row["name"])

            try:
                result = self._enrich_company(
                    company_id=company_row["id"],
                    company_name=company_row["name"],
                    enf_profile_url=company_row["enf_profile_url"],
                )
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                logger.exception(
                    "Enrichment transaction failed for %s", company_row["name"]
                )
                result = self._mark_enrichment_failed(
                    company_row["id"], company_row["name"], str(exc)
                )
                try:
                    self.session.commit()
                except Exception:
                    self.session.rollback()

            results.append(result)
            if result.success:
                succeeded += 1
            else:
                failed += 1

        return BatchEnrichmentResult(
            success=True,
            processed=len(company_rows),
            succeeded=succeeded,
            failed=failed,
            stopped_reason="batch_complete",
            results=results,
            message=(
                f"Batch complete: {succeeded} enriched, {failed} failed "
                f"out of {len(company_rows)} companies"
            ),
        )

    def _enrich_company(
        self,
        company_id: int,
        company_name: str,
        enf_profile_url: str,
    ) -> EnrichmentResult:
        job_id = self._start_enrichment_job(company_id)
        # Release the DB connection before the slow ENF profile crawl.
        self.session.commit()

        try:
            profile_data = self.crawler.crawl_profile(enf_profile_url)
        except Exception as exc:
            logger.exception("Enrichment failed for company %s", company_name)
            return self._finalize_enrichment_failure(
                company_id=company_id,
                company_name=company_name,
                job_id=job_id,
                error=str(exc),
            )

        return self._finalize_enrichment_success(
            company_id=company_id,
            company_name=company_name,
            job_id=job_id,
            profile_data=profile_data,
        )

    def _start_enrichment_job(self, company_id: int) -> int:
        company = self.session.get(Company, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")
        company.enrichment_status = EnrichmentStatus.IN_PROGRESS
        job = CrawlJob(
            job_type=CrawlJobType.ENRICHMENT,
            status=CrawlJobStatus.RUNNING,
            company_id=company_id,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        self.session.flush()
        return job.id

    def _finalize_enrichment_success(
        self,
        company_id: int,
        company_name: str,
        job_id: int,
        profile_data,
    ) -> EnrichmentResult:
        company = self.session.get(Company, company_id)
        job = self.session.get(CrawlJob, job_id)
        if company is None or job is None:
            raise ValueError(f"Missing enrichment records for company {company_id}")

        if profile_data.company_name:
            company.company_name = profile_data.company_name
        if profile_data.website:
            company.website = profile_data.website
        if profile_data.phone:
            company.phone = profile_data.phone
        if profile_data.address:
            company.address = profile_data.address
        if profile_data.country:
            company.country = profile_data.country

        company.crawl_status = CrawlStatus.ENRICHED
        company.enrichment_status = EnrichmentStatus.COMPLETED
        company.enriched_at = datetime.now(timezone.utc)

        existing_profile = (
            self.session.query(CompanyProfile)
            .filter(CompanyProfile.company_id == company_id)
            .first()
        )
        extra_json = (
            json.dumps(profile_data.extra_data) if profile_data.extra_data else None
        )
        if existing_profile:
            existing_profile.battery_storage = profile_data.battery_storage
            existing_profile.installation_size = profile_data.installation_size
            existing_profile.operating_area = profile_data.operating_area
            existing_profile.extra_data = extra_json
        else:
            self.session.add(
                CompanyProfile(
                    company_id=company_id,
                    battery_storage=profile_data.battery_storage,
                    installation_size=profile_data.installation_size,
                    operating_area=profile_data.operating_area,
                    extra_data=extra_json,
                )
            )

        job.status = CrawlJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)

        return EnrichmentResult(
            success=True,
            company_id=company_id,
            company_name=company.company_name,
            website=company.website,
            message=f"Enriched {company.company_name}",
        )

    def _finalize_enrichment_failure(
        self,
        company_id: int,
        company_name: str,
        job_id: int,
        error: str,
    ) -> EnrichmentResult:
        self.session.rollback()
        company = self.session.get(Company, company_id)
        job = self.session.get(CrawlJob, job_id)
        if company is not None:
            company.enrichment_status = EnrichmentStatus.FAILED
            company.crawl_status = CrawlStatus.FAILED
        if job is not None:
            job.status = CrawlJobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        return EnrichmentResult(
            success=False,
            company_id=company_id,
            company_name=company_name,
            message="Enrichment failed",
            error=error,
        )

    def _mark_enrichment_failed(
        self,
        company_id: int,
        company_name: str,
        error: str,
    ) -> EnrichmentResult:
        company = self.session.get(Company, company_id)
        if company is not None:
            company.enrichment_status = EnrichmentStatus.FAILED
            company.crawl_status = CrawlStatus.FAILED
        job = (
            self.session.query(CrawlJob)
            .filter(
                CrawlJob.company_id == company_id,
                CrawlJob.job_type == CrawlJobType.ENRICHMENT,
                CrawlJob.status == CrawlJobStatus.RUNNING,
            )
            .order_by(CrawlJob.id.desc())
            .first()
        )
        if job is not None:
            job.status = CrawlJobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        return EnrichmentResult(
            success=False,
            company_id=company_id,
            company_name=company_name,
            message="Enrichment failed",
            error=error,
        )

    def get_enrichment_stats(self) -> dict:
        pending = (
            self.session.query(Company)
            .filter(
                Company.enrichment_status == EnrichmentStatus.PENDING,
                or_(Company.website.is_(None), Company.website == ""),
            )
            .count()
        )
        completed = (
            self.session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.COMPLETED)
            .count()
        )
        failed = (
            self.session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.FAILED)
            .count()
        )
        in_progress = (
            self.session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.IN_PROGRESS)
            .count()
        )
        return {
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "total": pending + completed + failed + in_progress,
        }

    def preview_batch(self, country: str | None = None) -> List[dict]:
        companies = self.get_pending_companies(country=country)
        return [
            {
                "company_name": c.company_name,
                "country": c.country,
                "enf_profile_url": c.enf_profile_url,
            }
            for c in companies
        ]
