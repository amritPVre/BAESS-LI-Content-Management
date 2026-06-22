"""DeepSeek AI service for company research and contact extraction."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import requests

from config.settings import get_settings
from utils.logging import get_logger
from utils.retry import retry_on_failure

logger = get_logger(__name__)


class AIService:
    """OpenAI-compatible DeepSeek chat completions client."""

    def __init__(self, provider: str | None = None) -> None:
        settings = get_settings()
        self.provider = (provider or settings.default_ai_provider).lower()
        self._settings = settings

    @retry_on_failure(exceptions=(requests.RequestException, json.JSONDecodeError))
    def extract_contacts(
        self,
        company_name: str,
        country: str,
        website: str,
        website_text: str,
    ) -> Dict[str, Any]:
        prompt = f"""You are a B2B solar industry lead researcher. Analyze the company data below.

Company: {company_name}
Country: {country}
Website: {website}

Website text excerpt:
{website_text[:5000]}

Tasks:
1. Identify up to 5 key decision makers for solar/B2B outreach: CEO, Founder, Managing Director, Owner, Sales Director, Business Development, Commercial Manager.
2. Use full names only. Do not invent people if unclear.
3. Do NOT guess or generate email addresses. Emails are handled separately by website scraping.

Return ONLY valid JSON:
{{
  "people": [
    {{"name": "Full Name", "title": "Job Title"}}
  ],
  "company_summary": "One sentence about what the company does"
}}"""

        raw = self._chat(prompt)
        return self._parse_json(raw)

    def _chat(self, prompt: str) -> str:
        settings = self._settings
        if self.provider == "deepseek":
            api_key = settings.deepseek_api_key
            base_url = "https://api.deepseek.com/v1/chat/completions"
            model = settings.deepseek_model
        else:
            api_key = settings.openai_api_key
            base_url = "https://api.openai.com/v1/chat/completions"
            model = settings.openai_model

        if not api_key:
            raise ValueError(
                f"No API key configured for {self.provider}. "
                f"Set {'DEEPSEEK_API_KEY' if self.provider == 'deepseek' else 'OPENAI_API_KEY'}."
            )

        response = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You identify key business contacts from website text. "
                            "Never invent or guess email addresses. Respond with JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logger.info("AI response received from %s (%d chars)", self.provider, len(content))
        return content

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Expected JSON object", raw, 0)
        parsed.setdefault("emails", [])
        parsed.setdefault("people", [])
        parsed.setdefault("company_summary", "")
        return parsed
