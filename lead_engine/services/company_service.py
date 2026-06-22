"""Company query, filtering, export, and statistics service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from models.company import Company, CrawlStatus, EnrichmentStatus
from models.company_profile import CompanyProfile
from models.country_source import CountrySource


class CompanyService:
    def __init__(self, session: Session):
        self.session = session

    def search_companies(
        self,
        search: str = "",
        country: str | None = None,
        crawl_status: str | None = None,
        enrichment_status: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Tuple[List[Company], int]:
        query = self.session.query(Company).options(joinedload(Company.profile))

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Company.company_name.ilike(pattern),
                    Company.website.ilike(pattern),
                    Company.phone.ilike(pattern),
                    Company.address.ilike(pattern),
                )
            )
        if country and country != "All":
            query = query.filter(Company.country == country)
        if crawl_status and crawl_status != "All":
            query = query.filter(
                Company.crawl_status == CrawlStatus(crawl_status)
            )
        if enrichment_status and enrichment_status != "All":
            query = query.filter(
                Company.enrichment_status == EnrichmentStatus(enrichment_status)
            )

        total = query.count()
        offset = max(0, (page - 1) * per_page)
        companies = (
            query.order_by(Company.updated_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return companies, total

    def get_countries(self) -> List[str]:
        rows = (
            self.session.query(Company.country)
            .distinct()
            .order_by(Company.country)
            .all()
        )
        return [r[0] for r in rows if r[0]]

    def get_dashboard_stats(self) -> Dict[str, Any]:
        total = self.session.query(Company).count()
        enriched = (
            self.session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.COMPLETED)
            .count()
        )
        pending = (
            self.session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.PENDING)
            .count()
        )
        failed = (
            self.session.query(Company)
            .filter(
                or_(
                    Company.crawl_status == CrawlStatus.FAILED,
                    Company.enrichment_status == EnrichmentStatus.FAILED,
                )
            )
            .count()
        )
        with_website = (
            self.session.query(Company)
            .filter(Company.website.isnot(None), Company.website != "")
            .count()
        )
        with_phone = (
            self.session.query(Company)
            .filter(Company.phone.isnot(None), Company.phone != "")
            .count()
        )
        countries_active = self.session.query(CountrySource).filter(
            CountrySource.is_active.is_(True)
        ).count()
        by_country = (
            self.session.query(Company.country, func.count(Company.id))
            .group_by(Company.country)
            .order_by(func.count(Company.id).desc())
            .limit(10)
            .all()
        )
        recent_companies = (
            self.session.query(Company)
            .order_by(Company.created_at.desc())
            .limit(5)
            .all()
        )
        return {
            "total_companies": total,
            "enriched": enriched,
            "pending_enrichment": pending,
            "failed": failed,
            "with_website": with_website,
            "with_phone": with_phone,
            "countries_active": countries_active,
            "by_country": by_country,
            "recent_companies": [
                {
                    "company_name": c.company_name,
                    "country": c.country,
                    "enrichment_status": c.enrichment_status.value,
                    "discovered_at": c.discovered_at,
                }
                for c in recent_companies
            ],
        }

    def companies_to_dataframe(self, companies: List[Company]) -> pd.DataFrame:
        rows = []
        for c in companies:
            profile: Optional[CompanyProfile] = c.profile
            rows.append(
                {
                    "id": c.id,
                    "company_name": c.company_name,
                    "country": c.country,
                    "enf_profile_url": c.enf_profile_url,
                    "website": c.website,
                    "phone": c.phone,
                    "address": c.address,
                    "source_type": c.source_type.value if c.source_type else "",
                    "crawl_status": c.crawl_status.value if c.crawl_status else "",
                    "enrichment_status": (
                        c.enrichment_status.value if c.enrichment_status else ""
                    ),
                    "battery_storage": profile.battery_storage if profile else "",
                    "installation_size": profile.installation_size if profile else "",
                    "operating_area": profile.operating_area if profile else "",
                    "discovered_at": c.discovered_at,
                    "enriched_at": c.enriched_at,
                    "created_at": c.created_at,
                }
            )
        return pd.DataFrame(rows)

    def export_all_to_csv(self) -> pd.DataFrame:
        companies, _ = self.search_companies(per_page=100_000)
        return self.companies_to_dataframe(companies)
