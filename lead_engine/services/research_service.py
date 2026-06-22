"""Phase 3 — AI company research: scraped emails and key people from websites."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from config.settings import get_settings
from crawlers.website_crawler import WebsiteCrawler
from sqlalchemy import or_

from models.company import Company, EnrichmentStatus, ResearchStatus
from models.company_contact import CompanyContact, ContactSource
from models.crawl_job import CrawlJob, CrawlJobStatus, CrawlJobType
from services.ai_service import AIService
from utils.logging import get_logger

logger = get_logger(__name__)

TITLE_PRIORITY = (
    "ceo",
    "chief executive",
    "founder",
    "managing director",
    "owner",
    "director",
    "sales",
    "commercial",
    "business development",
)


@dataclass
class ResearchResult:
    success: bool
    company_id: int | None
    company_name: str
    contacts_saved: int = 0
    emails_found: int = 0
    linkedin_found: int = 0
    message: str = ""
    error: str | None = None
    contacts: List[dict] = field(default_factory=list)


@dataclass
class BatchResearchResult:
    success: bool
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    message: str = ""
    results: List[ResearchResult] = field(default_factory=list)


class ResearchService:
    def __init__(self, session: Session, ai_provider: str = "deepseek"):
        self.session = session
        self.website_crawler = WebsiteCrawler()
        self.ai_service = AIService(provider=ai_provider)

    def _pending_query(self, country: str | None = None):
        query = self.session.query(Company).filter(
            Company.enrichment_status == EnrichmentStatus.COMPLETED,
            Company.website.isnot(None),
            Company.website != "",
            Company.research_status == ResearchStatus.PENDING,
        )
        if country:
            query = query.filter(Company.country == country)
        return query.order_by(Company.enriched_at.asc().nullsfirst(), Company.id.asc())

    def get_pending_companies(
        self, limit: int | None = None, country: str | None = None
    ) -> List[Company]:
        settings = get_settings()
        batch_limit = limit or settings.research_batch_size
        return self._pending_query(country=country).limit(batch_limit).all()

    def preview_batch(self, country: str | None = None) -> List[dict]:
        return [
            {
                "company_name": c.company_name,
                "country": c.country,
                "website": c.website,
            }
            for c in self.get_pending_companies(country=country)
        ]

    def research_batch(
        self,
        country: str | None = None,
        batch_size: int | None = None,
        on_progress=None,
    ) -> BatchResearchResult:
        companies = self.get_pending_companies(limit=batch_size, country=country)
        if not companies:
            return BatchResearchResult(
                success=False,
                message="No companies pending research (need enriched company with website)",
            )

        results: List[ResearchResult] = []
        succeeded = failed = 0

        for index, company in enumerate(companies, start=1):
            if on_progress:
                on_progress(index, len(companies), company.company_name)
            try:
                result = self.research_company(company)
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                logger.exception(
                    "Research transaction failed for %s", company.company_name
                )
                result = self._mark_research_failed(
                    company.id, company.company_name, str(exc)
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

        return BatchResearchResult(
            success=True,
            processed=len(companies),
            succeeded=succeeded,
            failed=failed,
            results=results,
            message=f"Research batch: {succeeded} OK, {failed} failed of {len(companies)}",
        )

    def research_company(self, company: Company) -> ResearchResult:
        company_id = company.id
        company_name = company.company_name
        country = company.country
        website = company.website or ""

        job_id = self._start_research_job(company_id)
        # Release the DB connection before long website/AI work.
        self.session.commit()

        try:
            external = self._run_external_research(
                company_name=company_name,
                country=country,
                website=website,
            )
        except Exception as exc:
            logger.exception("Research failed for %s", company_name)
            return self._finalize_research_failure(
                company_id=company_id,
                company_name=company_name,
                job_id=job_id,
                error=str(exc),
            )

        return self._finalize_research_success(
            company_id=company_id,
            company_name=company_name,
            job_id=job_id,
            external=external,
        )

    @staticmethod
    def _prioritize_people(people: List[dict]) -> List[dict]:
        def score(person: dict) -> int:
            title = (person.get("title") or "").lower()
            for index, term in enumerate(TITLE_PRIORITY):
                if term in title:
                    return index
            return len(TITLE_PRIORITY)

        cleaned = [
            person
            for person in people
            if (person.get("name") or "").strip()
        ]
        return sorted(cleaned, key=score)

    def _start_research_job(self, company_id: int) -> int:
        company = self.session.get(Company, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")
        company.research_status = ResearchStatus.IN_PROGRESS
        job = CrawlJob(
            job_type=CrawlJobType.RESEARCH,
            status=CrawlJobStatus.RUNNING,
            company_id=company_id,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        self.session.flush()
        return job.id

    def _run_external_research(
        self,
        company_name: str,
        country: str,
        website: str,
    ) -> dict:
        website_data = self.website_crawler.crawl(website)
        if website_data.error and not website_data.pages_fetched:
            raise RuntimeError(f"Website crawl failed: {website_data.error}")

        ai_data = self.ai_service.extract_contacts(
            company_name=company_name,
            country=country,
            website=website,
            website_text=website_data.text_content,
        )

        scraped_emails = sorted(
            {
                email.lower().strip()
                for email in website_data.emails
                if email and "@" in email
            }
        )
        people: List[dict] = []
        for person in self._prioritize_people(ai_data.get("people", []))[:5]:
            name = (person.get("name") or "").strip()
            title = (person.get("title") or "").strip()
            if not name:
                continue
            people.append({"name": name, "title": title})

        return {
            "scraped_emails": scraped_emails,
            "people": people,
            "company_summary": ai_data.get("company_summary", ""),
        }

    def _finalize_research_success(
        self,
        company_id: int,
        company_name: str,
        job_id: int,
        external: dict,
    ) -> ResearchResult:
        company = self.session.get(Company, company_id)
        job = self.session.get(CrawlJob, job_id)
        if company is None or job is None:
            raise ValueError(f"Missing research records for company {company_id}")

        saved_contacts: List[dict] = []
        for email in external["scraped_emails"]:
            if not self._contact_exists(company_id, email=email):
                self.session.add(
                    CompanyContact(
                        company_id=company_id,
                        email=email,
                        source=ContactSource.WEBSITE,
                        notes="Scraped from company website (not guessed)",
                    )
                )
                saved_contacts.append({"email": email, "name": None, "title": None})

        for person in external["people"]:
            name = person["name"]
            if not self._contact_exists(company_id, name=name):
                self.session.add(
                    CompanyContact(
                        company_id=company_id,
                        full_name=name,
                        job_title=person.get("title") or None,
                        email=None,
                        linkedin_url=None,
                        source=ContactSource.AI,
                        notes=external.get("company_summary", ""),
                    )
                )
                saved_contacts.append(
                    {
                        "email": None,
                        "name": name,
                        "title": person.get("title"),
                    }
                )

        company.research_status = ResearchStatus.COMPLETED
        company.researched_at = datetime.now(timezone.utc)
        job.status = CrawlJobStatus.COMPLETED
        job.companies_found = len(saved_contacts)
        job.completed_at = datetime.now(timezone.utc)

        return ResearchResult(
            success=True,
            company_id=company_id,
            company_name=company_name,
            contacts_saved=len(saved_contacts),
            emails_found=len(external["scraped_emails"]),
            linkedin_found=0,
            message=f"Researched {company_name}: {len(saved_contacts)} contacts",
            contacts=saved_contacts,
        )

    def _finalize_research_failure(
        self,
        company_id: int,
        company_name: str,
        job_id: int,
        error: str,
    ) -> ResearchResult:
        self.session.rollback()
        company = self.session.get(Company, company_id)
        job = self.session.get(CrawlJob, job_id)
        if company is not None:
            company.research_status = ResearchStatus.FAILED
        if job is not None:
            job.status = CrawlJobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        return ResearchResult(
            success=False,
            company_id=company_id,
            company_name=company_name,
            message="Research failed",
            error=error,
        )

    def _mark_research_failed(
        self,
        company_id: int,
        company_name: str,
        error: str,
    ) -> ResearchResult:
        company = self.session.get(Company, company_id)
        if company is not None:
            company.research_status = ResearchStatus.FAILED
        job = (
            self.session.query(CrawlJob)
            .filter(
                CrawlJob.company_id == company_id,
                CrawlJob.job_type == CrawlJobType.RESEARCH,
                CrawlJob.status == CrawlJobStatus.RUNNING,
            )
            .order_by(CrawlJob.id.desc())
            .first()
        )
        if job is not None:
            job.status = CrawlJobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
        return ResearchResult(
            success=False,
            company_id=company_id,
            company_name=company_name,
            message="Research failed",
            error=error,
        )

    def _contact_exists(
        self,
        company_id: int,
        email: str | None = None,
        name: str | None = None,
    ) -> bool:
        query = self.session.query(CompanyContact).filter(
            CompanyContact.company_id == company_id
        )
        if email:
            existing = query.filter(CompanyContact.email == email.lower()).first()
            if existing:
                return True
        if name:
            existing = query.filter(CompanyContact.full_name == name).first()
            if existing:
                return True
        return False

    def get_research_stats(self) -> dict:
        ready_queue = self._pending_query().count()
        completed = (
            self.session.query(Company)
            .filter(Company.research_status == ResearchStatus.COMPLETED)
            .count()
        )
        failed = (
            self.session.query(Company)
            .filter(Company.research_status == ResearchStatus.FAILED)
            .count()
        )
        awaiting_enrichment = (
            self.session.query(Company)
            .filter(
                Company.research_status == ResearchStatus.PENDING,
                or_(
                    Company.enrichment_status != EnrichmentStatus.COMPLETED,
                    Company.website.is_(None),
                    Company.website == "",
                ),
            )
            .count()
        )
        contacts = self.session.query(CompanyContact).count()
        with_people = (
            self.session.query(CompanyContact)
            .filter(CompanyContact.full_name.isnot(None))
            .count()
        )
        with_email = (
            self.session.query(CompanyContact)
            .filter(CompanyContact.email.isnot(None))
            .count()
        )
        return {
            "pending": ready_queue,
            "awaiting_enrichment": awaiting_enrichment,
            "completed": completed,
            "failed": failed,
            "total_contacts": contacts,
            "with_people": with_people,
            "with_email": with_email,
        }

    def get_contact_count(self, country: str | None = None) -> int:
        query = self.session.query(CompanyContact).join(
            Company, CompanyContact.company_id == Company.id
        )
        if country:
            query = query.filter(Company.country == country)
        return query.count()

    def export_contacts_to_excel(self, country: str | None = None) -> bytes:
        query = (
            self.session.query(CompanyContact)
            .options(joinedload(CompanyContact.company))
            .join(Company, CompanyContact.company_id == Company.id)
            .order_by(Company.country, Company.company_name, CompanyContact.id)
        )
        if country:
            query = query.filter(Company.country == country)

        rows: List[dict] = []
        for contact in query.all():
            company = contact.company
            rows.append(
                {
                    "Company": company.company_name if company else "",
                    "Country": company.country if company else "",
                    "Website": company.website if company else "",
                    "Phone": company.phone if company else "",
                    "Address": company.address if company else "",
                    "Research Status": (
                        company.research_status.value if company else ""
                    ),
                    "Researched At": (
                        company.researched_at.strftime("%Y-%m-%d %H:%M")
                        if company and company.researched_at
                        else ""
                    ),
                    "Contact Name": contact.full_name or "",
                    "Job Title": contact.job_title or "",
                    "Email": contact.email or "",
                    "LinkedIn": contact.linkedin_url or "",
                    "Source": contact.source.value,
                    "Notes": contact.notes or "",
                    "Contact Added": contact.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        df = pd.DataFrame(
            rows,
            columns=[
                "Company",
                "Country",
                "Website",
                "Phone",
                "Address",
                "Research Status",
                "Researched At",
                "Contact Name",
                "Job Title",
                "Email",
                "LinkedIn",
                "Source",
                "Notes",
                "Contact Added",
            ],
        )

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Research Contacts")
        buffer.seek(0)
        return buffer.getvalue()

    def get_export_filename(self, country: str | None = None) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        if country and country != "All":
            slug = country.lower().replace(" ", "_")
            return f"baess_research_{slug}_{stamp}.xlsx"
        return f"baess_research_all_{stamp}.xlsx"
