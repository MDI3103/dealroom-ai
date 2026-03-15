"""
Agent 4 — Risk Assessor Agent (Fixed)

Key fixes:
1. Balanced search queries — no longer searching specifically for fraud/SEC
2. Proximity check — company name must appear near the risk keyword
3. Count threshold — need 2+ sources for CRITICAL, 2+ for HIGH
4. Positive signal detection — balances against negative findings
5. Severity downgrade for single-source mentions
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Tuple

from agents.base_agent import BaseAgent
from mcp_tools.tools import (
    web_search,
    search_legal_issues,
    search_founder_background,
    search_positive_signals,
    analyze_sentiment,
)


# ── Risk keyword definitions ───────────────────────────────
# Only fire if DIRECTLY about the company (proximity enforced)
RISK_KEYWORDS = {
    "critical": [
        "fraud", "ponzi", "embezzlement", "criminal charges", "indicted",
        "sec charges", "money laundering", "bribery conviction",
    ],
    "high": [
        "class action", "bankruptcy", "insolvency", "delisted",
        "data breach", "whistleblower lawsuit", "regulatory shutdown",
        "license revoked", "major fine",
    ],
    "medium": [
        "layoffs", "antitrust", "gdpr violation", "product recall",
        "accounting restatement", "ceo resignation", "acquisition blocked",
        "regulatory warning", "fined", "settlement",
    ],
    "low": [
        "competition", "market slowdown", "pricing pressure",
        "executive departure", "customer complaints",
    ],
}

# Positive signals that reduce overall risk score
POSITIVE_KEYWORDS = [
    "growth", "profit", "revenue increase", "expansion", "award",
    "partnership", "record", "milestone", "investment", "innovation",
    "market leader", "strong results", "profitable", "raised funding",
]

# How many words around keyword to check for company name
PROXIMITY_WINDOW = 120  # characters

# Minimum number of DIFFERENT sources needed per severity to confirm
MIN_SOURCES_FOR_SEVERITY = {
    "critical": 2,   # Need 2+ sources to call something CRITICAL
    "high": 2,       # Need 2+ sources for HIGH
    "medium": 1,     # 1 source ok for MEDIUM
    "low": 1,
}


class RiskAssessorAgent(BaseAgent):

    def __init__(self):
        super().__init__(agent_id="risk_assessor", timeout=40.0, max_retries=3)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self._log("Planning", f"Initiating balanced risk assessment for: {company}")
        company_lower = company.lower()
        results: Dict[str, Any] = {"flags": [], "risk_level": "minimal"}

        # ── Step 1: Balanced legal/news search ───────────
        self._log("Step 1/5", "Fetching balanced news and legal context")
        legal = await self._run_tool_with_retry(
            tool_fn=search_legal_issues,
            tool_name="search_legal_issues",
            params_description=f"company={company} (balanced queries)",
            fallback_fn=lambda: [],
            tool_args=(company,),
        )
        results["legal_results"] = legal or []

        # ── Step 2: Founder background ────────────────────
        self._log("Step 2/5", "Checking leadership background")
        founder = await self._run_tool_with_retry(
            tool_fn=search_founder_background,
            tool_name="search_founder_background",
            params_description=f"company={company}",
            fallback_fn=lambda: [],
            tool_args=(company,),
        )
        results["founder_results"] = founder or []

        # ── Step 3: Positive signals ──────────────────────
        self._log("Step 3/5", "Scanning for positive signals and achievements")
        positive = await self._run_tool_with_retry(
            tool_fn=search_positive_signals,
            tool_name="search_positive_signals",
            params_description=f"company={company}",
            fallback_fn=lambda: [],
            tool_args=(company,),
        )
        results["positive_results"] = positive or []

        # ── Step 4: Targeted check only if needed ─────────
        self._log("Step 4/5", "Running targeted risk verification")
        targeted = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search_targeted",
            params_description=f"'{company} legal regulatory issues'",
            fallback_fn=lambda: [],
            tool_args=(f"{company} regulatory compliance legal issues 2024 2025",),
            tool_kwargs={"max_results": 4},
        )
        results["targeted_results"] = targeted or []

        # ── Step 5: Extract flags with proximity + count ──
        self._log("Step 5/5", "Classifying risk with proximity check and source counting")
        flags = self._extract_flags_smart(company, results)
        positive_score = self._count_positive_signals(results)
        results["positive_score"] = positive_score
        results["flags"] = flags

        overall_level = self._calculate_risk_level_smart(flags, positive_score)
        results["risk_level"] = overall_level
        results["flag_count"] = len(flags)

        # ── A2A: Only send CONFIRMED critical flags ────────
        critical_flags = [f for f in flags if f["severity"] == "critical" and f.get("confirmed")]
        if critical_flags:
            most_critical = critical_flags[0]
            self._log(
                "A2A → financial_analyst",
                f"Confirmed CRITICAL flag: {most_critical['type']} ({most_critical['source_count']} sources)",
                status="warning",
            )
            await self.send_flag(
                recipient="financial_analyst",
                flag_type=most_critical["type"],
                detail=most_critical["detail"],
                severity="critical",
            )
        elif any(f["severity"] == "high" and f.get("confirmed") for f in flags):
            high_flag = next(f for f in flags if f["severity"] == "high" and f.get("confirmed"))
            await self.send_flag(
                recipient="financial_analyst",
                flag_type=high_flag["type"],
                detail=high_flag["detail"],
                severity="high",
            )

        results["summary"] = self._synthesise(company, flags, overall_level, positive_score)
        self._log("Complete", f"Risk assessment complete. Level: {overall_level.upper()}", status="success")
        return results

    def _keyword_near_company(self, text: str, keyword: str, company: str) -> bool:
        """
        SENTENCE-LEVEL PROXIMITY CHECK:
        Returns True only if the company name appears in the SAME SENTENCE
        as the risk keyword. This prevents false positives from articles
        that mention the company and a risk keyword in unrelated sentences.
        """
        company_lower = company.lower()
        text_lower = text.lower()

        # Split into sentences
        sentences = re.split(r'[.!?]\s+|\n', text_lower)

        for sentence in sentences:
            if keyword not in sentence:
                continue
            if company_lower not in sentence:
                continue

            # Both keyword and company are in the same sentence
            # Now check it's not a denial
            denial_patterns = [
                f"no {keyword}", f"denies {keyword}", f"not guilty",
                f"cleared of", f"acquitted", f"dismissed", f"unfounded",
                f"false {keyword}", f"no evidence of {keyword}",
                f"rejected {keyword}", f"without {keyword}",
            ]
            is_denial = any(d in sentence for d in denial_patterns)
            if not is_denial:
                return True

        return False

    def _extract_flags_smart(self, company: str, data: Dict) -> List[Dict]:
        """
        Smart flag extraction with:
        - Proximity check (company name near keyword)
        - Source counting (how many different articles mention it)
        - Confirmation threshold (need N sources per severity)
        - Denial detection (ignore "no fraud", "denies allegations")
        """
        # Collect all content sources
        all_sources = []
        for key in ("legal_results", "founder_results", "targeted_results"):
            for r in data.get(key, []):
                text = (r.get("title", "") + " " + r.get("content", "")).lower()
                all_sources.append({
                    "text": text,
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                })

        # Count how many DIFFERENT sources mention each keyword near the company
        keyword_hits: Dict[str, Dict] = {}  # keyword → {severity, sources: [url,...]}

        for source in all_sources:
            text = source["text"]
            for severity, keywords in RISK_KEYWORDS.items():
                for kw in keywords:
                    if self._keyword_near_company(text, kw, company):
                        if kw not in keyword_hits:
                            keyword_hits[kw] = {
                                "severity": severity,
                                "sources": [],
                                "titles": [],
                            }
                        if source["url"] not in keyword_hits[kw]["sources"]:
                            keyword_hits[kw]["sources"].append(source["url"])
                            keyword_hits[kw]["titles"].append(source["title"][:80])

        # Build flags with confirmation status
        flags = []
        for kw, hit_data in keyword_hits.items():
            severity = hit_data["severity"]
            source_count = len(hit_data["sources"])
            required = MIN_SOURCES_FOR_SEVERITY.get(severity, 1)
            confirmed = source_count >= required

            # Downgrade unconfirmed high/critical flags
            effective_severity = severity
            if not confirmed:
                downgrade = {"critical": "medium", "high": "medium", "medium": "low", "low": "low"}
                effective_severity = downgrade.get(severity, severity)
                self._log(
                    f"Flag downgraded: {kw}",
                    f"Only {source_count}/{required} sources — downgraded {severity}→{effective_severity}",
                    status="info",
                )

            flags.append({
                "type": kw.replace(" ", "_"),
                "severity": effective_severity,
                "original_severity": severity,
                "confirmed": confirmed,
                "source_count": source_count,
                "required_sources": required,
                "detail": f"Found in {source_count} source(s): {hit_data['titles'][0] if hit_data['titles'] else ''}",
                "keyword": kw,
            })

        # Sort by severity then source count
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        flags.sort(key=lambda f: (severity_order.get(f["severity"], 4), -f["source_count"]))
        return flags[:10]

    def _count_positive_signals(self, data: Dict) -> int:
        """Count positive signals from search results to balance risk score."""
        positive_count = 0
        for r in data.get("positive_results", []):
            text = (r.get("title", "") + " " + r.get("content", "")).lower()
            positive_count += sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        return positive_count

    def _calculate_risk_level_smart(self, flags: List[Dict], positive_score: int) -> str:
        """
        Smart risk calculation that considers:
        - Only CONFIRMED flags matter for high/critical
        - Positive signals can reduce the final level
        """
        confirmed_critical = [f for f in flags if f["severity"] == "critical" and f.get("confirmed")]
        confirmed_high = [f for f in flags if f["severity"] == "high" and f.get("confirmed")]
        any_medium = [f for f in flags if f["severity"] == "medium"]

        if confirmed_critical:
            # Strong positive signals can downgrade critical → high
            if positive_score >= 8:
                self._log("Risk moderated", f"Positive signals ({positive_score}) moderate CRITICAL → HIGH", status="info")
                return "high"
            return "critical"

        if confirmed_high:
            if positive_score >= 6:
                return "medium"
            return "high"

        if any_medium:
            if positive_score >= 4:
                return "low"
            return "medium"

        if flags:  # Only unconfirmed/low flags
            return "low"

        return "minimal"

    def _synthesise(self, company: str, flags: List[Dict], risk_level: str, positive_score: int) -> Dict:
        confirmed = [f for f in flags if f.get("confirmed")]
        unconfirmed = [f for f in flags if not f.get("confirmed")]

        risk_emoji = {
            "critical": "🔴", "high": "🟠", "medium": "🟡",
            "low": "🟢", "minimal": "✅"
        }

        return {
            "company": company,
            "overall_risk_level": risk_level,
            "risk_indicator": risk_emoji.get(risk_level, "⚪"),
            "confirmed_flags": len(confirmed),
            "unconfirmed_flags": len(unconfirmed),
            "positive_signals": positive_score,
            "top_risks": [
                f"{'✓' if f['confirmed'] else '?'} {f['severity'].upper()}: {f['keyword']} ({f['source_count']} sources)"
                for f in flags[:5]
            ],
            "recommendation": self._get_recommendation(risk_level),
        }

    def _get_recommendation(self, level: str) -> str:
        recs = {
            "critical": "AVOID — multiple confirmed critical red flags detected across independent sources",
            "high": "HIGH CAUTION — significant confirmed risks; deep due diligence strongly recommended",
            "medium": "PROCEED WITH CAUTION — moderate risks detected; standard due diligence recommended",
            "low": "LOW RISK — minor unconfirmed signals only; routine checks sufficient",
            "minimal": "CLEAN PROFILE — no significant risk signals found across public sources",
        }
        return recs.get(level, "Risk level undetermined")

    def _calculate_risk_level(self, flags):
        """Legacy method — kept for test compatibility."""
        return self._calculate_risk_level_smart(flags, 0)
