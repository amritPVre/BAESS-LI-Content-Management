"""Discovery service — processes exactly one ENF directory page per action."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from crawlers.enf_directory import ENFDirectoryCrawler
from models.company import Company, CrawlStatus, EnrichmentStatus, SourceType
from models.country_source import CountrySource
from models.crawl_job import CrawlJob, CrawlJobStatus, CrawlJobType
from utils.logging import get_logger
from utils.url_helpers import (
    build_enf_directory_url,
    build_paginated_directory_url,
    normalize_enf_url,
)

logger = get_logger(__name__)


@dataclass
class DiscoveryResult:
    success: bool
    country_name: str
    page_processed: int
    companies_found: int
    companies_new: int
    companies_duplicate: int
    has_next_page: bool
    message: str
    error: str | None = None


class DiscoveryService:
    def __init__(self, session: Session):
        self.session = session
        self.crawler = ENFDirectoryCrawler()

    def discover_next_page(self, country_source_id: int) -> DiscoveryResult:
        country = (
            self.session.query(CountrySource)
            .filter(CountrySource.id == country_source_id)
            .first()
        )
        if not country:
            return DiscoveryResult(
                success=False,
                country_name="",
                page_processed=0,
                companies_found=0,
                companies_new=0,
                companies_duplicate=0,
                has_next_page=False,
                message="Country not found",
                error="Invalid country_source_id",
            )

        page = country.current_page
        job = CrawlJob(
            job_type=CrawlJobType.DISCOVERY,
            status=CrawlJobStatus.RUNNING,
            country_source_id=country.id,
            page_number=page,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        self.session.flush()

        try:
            crawl_result = self.crawler.crawl_page(
                country.country_slug,
                page,
                directory_base_url=country.enf_directory_url,
            )
            new_count = 0
            dup_count = 0

            for item in crawl_result.companies:
                normalized_url = normalize_enf_url(item.enf_profile_url)
                existing = (
                    self.session.query(Company)
                    .filter(Company.enf_profile_url == normalized_url)
                    .first()
                )
                if existing:
                    dup_count += 1
                    continue
                self.session.add(
                    Company(
                        company_name=item.company_name,
                        country=country.country_name,
                        enf_profile_url=normalized_url,
                        source_type=SourceType.ENF_INSTALLER,
                        crawl_status=CrawlStatus.DISCOVERED,
                        enrichment_status=EnrichmentStatus.PENDING,
                        country_source_id=country.id,
                        discovered_at=datetime.now(timezone.utc),
                    )
                )
                new_count += 1

            country.current_page = page + 1
            country.last_crawled_at = datetime.now(timezone.utc)
            if crawl_result.total_pages:
                country.total_pages = crawl_result.total_pages

            job.status = CrawlJobStatus.COMPLETED
            job.companies_found = len(crawl_result.companies)
            job.completed_at = datetime.now(timezone.utc)

            self.session.flush()

            return DiscoveryResult(
                success=True,
                country_name=country.country_name,
                page_processed=page,
                companies_found=len(crawl_result.companies),
                companies_new=new_count,
                companies_duplicate=dup_count,
                has_next_page=crawl_result.has_next_page,
                message=(
                    f"Processed page {page} for {country.country_name}: "
                    f"{new_count} new, {dup_count} duplicates"
                ),
            )
        except Exception as exc:
            job.status = CrawlJobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            logger.exception("Discovery failed for %s page %d", country.country_name, page)
            return DiscoveryResult(
                success=False,
                country_name=country.country_name,
                page_processed=page,
                companies_found=0,
                companies_new=0,
                companies_duplicate=0,
                has_next_page=True,
                message="Discovery failed",
                error=str(exc),
            )

    def set_directory_url(
        self, country_source_id: int, directory_url: str, *, reset_page: bool = True
    ) -> tuple[bool, str]:
        country = (
            self.session.query(CountrySource)
            .filter(CountrySource.id == country_source_id)
            .first()
        )
        if not country:
            return False, "Country not found"

        directory_url = directory_url.strip()
        if not directory_url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        if "enfsolar.com" not in directory_url.lower():
            return False, "URL must be an ENF Solar directory link"

        country.enf_directory_url = directory_url
        if reset_page:
            country.current_page = 1
            country.total_pages = None
        self.session.flush()
        return True, f"Directory URL saved for {country.country_name}"

    def get_country_stats(self, country_source_id: int) -> dict:
        country = (
            self.session.query(CountrySource)
            .filter(CountrySource.id == country_source_id)
            .first()
        )
        if not country:
            return {}
        total_companies = (
            self.session.query(Company)
            .filter(Company.country_source_id == country.id)
            .count()
        )
        next_page = country.current_page
        return {
            "country_name": country.country_name,
            "country_slug": country.country_slug,
            "current_page": next_page,
            "total_pages": country.total_pages,
            "total_companies": total_companies,
            "last_crawled_at": country.last_crawled_at,
            "directory_url": country.enf_directory_url,
            "auto_directory_url": build_enf_directory_url(country.country_slug, page=1),
            "next_fetch_url": build_paginated_directory_url(
                country.enf_directory_url, next_page
            ),
        }
