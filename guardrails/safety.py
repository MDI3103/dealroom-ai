"""
guardrails/safety.py — ADK Safety Guardrails
Covers the System Robustness criterion (20% of hackathon score).

Implements:
- Input validation & prompt injection detection
- Output schema enforcement per agent
- Rate limiting per MCP tool
- Destructive action prevention
- PII/sensitive data scrubbing in outputs
- Agent output quarantine on schema violation
"""

from __future__ import annotations

import re
import time
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ══════════════════════════════════════════════════════════
# INPUT GUARDRAILS
# ══════════════════════════════════════════════════════════

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|prior)\s+instructions",
    r"system\s*:",
    r"you\s+are\s+now",
    r"new\s+persona",
    r"<\s*script",
    r"```.*?```",
    r"DROP\s+TABLE",
    r"SELECT\s+\*\s+FROM",
    r"__import__",
    r"eval\s*\(",
    r"exec\s*\(",
    r"\|\s*bash",
    r"\/etc\/passwd",
    r"rm\s+-rf",
]

# Characters that are fine in company names
ALLOWED_COMPANY_CHARS = re.compile(r"^[a-zA-Z0-9\s\.\,\&\-\']+$")


@dataclass
class ValidationResult:
    valid: bool
    cleaned: str
    warnings: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None


def validate_company_input(raw_input: str) -> ValidationResult:
    """
    Full input validation pipeline for user-supplied company names.
    Returns ValidationResult with cleaned value or block reason.
    """
    warnings = []

    # 1. Null check
    if not raw_input or not raw_input.strip():
        return ValidationResult(False, "", blocked_reason="Input is empty.")

    cleaned = raw_input.strip()

    # 2. Length limit
    if len(cleaned) > 120:
        return ValidationResult(False, "", blocked_reason=f"Input too long ({len(cleaned)} chars, max 120).")

    # 3. Prompt injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return ValidationResult(
                False, "",
                blocked_reason=f"Blocked: suspicious pattern detected ('{pattern[:30]}...')."
            )

    # 4. Character allowlist — warn but don't block (some legit names have special chars)
    if not ALLOWED_COMPANY_CHARS.match(cleaned):
        warnings.append("Input contains unusual characters — proceeding with caution.")
        # Strip anything that's clearly malicious
        cleaned = re.sub(r"[<>{}[\]\\|`]", "", cleaned).strip()

    # 5. Minimum length
    if len(cleaned) < 2:
        return ValidationResult(False, "", blocked_reason="Company name too short (min 2 characters).")

    return ValidationResult(valid=True, cleaned=cleaned, warnings=warnings)


# ══════════════════════════════════════════════════════════
# OUTPUT SCHEMA GUARDRAILS
# ══════════════════════════════════════════════════════════

# Required keys per agent output — if missing, output is quarantined
AGENT_OUTPUT_SCHEMAS: Dict[str, Dict[str, type]] = {
    "market_research": {
        "overview": dict,
        "summary": dict,
    },
    "financial_analyst": {
        "financials": dict,
        "summary": dict,
    },
    "risk_assessor": {
        "flags": list,
        "risk_level": str,
        "summary": dict,
    },
    "sentiment_news": {
        "articles": list,
        "summary": dict,
    },
}

# PII patterns to scrub from outputs before they're shown to users
PII_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE REDACTED]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
    (re.compile(r"\b4[0-9]{12}(?:[0-9]{3})?\b"), "[CARD REDACTED]"),
]


@dataclass
class OutputValidationResult:
    valid: bool
    data: Dict[str, Any]
    violations: List[str] = field(default_factory=list)
    quarantined: bool = False


def validate_agent_output(agent_id: str, output: Dict[str, Any]) -> OutputValidationResult:
    """
    Validate agent output against its expected schema.
    Scrubs PII. Quarantines output if required keys are missing.
    """
    schema = AGENT_OUTPUT_SCHEMAS.get(agent_id, {})
    violations = []

    # Check required keys and types
    for key, expected_type in schema.items():
        if key not in output:
            violations.append(f"Missing required key: '{key}'")
        elif not isinstance(output[key], expected_type):
            violations.append(
                f"Key '{key}' has wrong type: expected {expected_type.__name__}, "
                f"got {type(output[key]).__name__}"
            )

    # Scrub PII from string values
    output = _scrub_pii(output)

    # Quarantine if critical violations
    quarantined = len(violations) > 0 and any(
        "Missing required key" in v for v in violations
    )

    return OutputValidationResult(
        valid=len(violations) == 0,
        data=output,
        violations=violations,
        quarantined=quarantined,
    )


def _scrub_pii(obj: Any) -> Any:
    """Recursively scrub PII from nested dicts/lists/strings."""
    if isinstance(obj, str):
        for pattern, replacement in PII_PATTERNS:
            obj = pattern.sub(replacement, obj)
        return obj
    elif isinstance(obj, dict):
        return {k: _scrub_pii(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_scrub_pii(item) for item in obj]
    return obj


# ══════════════════════════════════════════════════════════
# RATE LIMITER
# ══════════════════════════════════════════════════════════

class RateLimiter:
    """
    Token-bucket rate limiter for MCP tool calls.
    Prevents API abuse and runaway agent loops.
    """

    # Limits per tool (calls per minute)
    TOOL_LIMITS: Dict[str, int] = {
        "web_search": 20,
        "wikipedia_summary": 15,
        "crunchbase_lookup": 10,
        "yfinance_financials": 30,
        "yfinance_history": 30,
        "get_news": 10,
        "reddit_mentions": 5,
        "resolve_ticker": 20,
        "search_legal_issues": 10,
        "search_founder_background": 10,
        "default": 15,
    }

    def __init__(self):
        # Sliding window: tool_name → deque of call timestamps
        self._windows: Dict[str, deque] = defaultdict(lambda: deque())

    def check(self, tool_name: str) -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Call this before each MCP tool invocation.
        """
        limit = self.TOOL_LIMITS.get(tool_name, self.TOOL_LIMITS["default"])
        window = self._windows[tool_name]
        now = time.time()

        # Remove timestamps older than 60 seconds
        while window and window[0] < now - 60:
            window.popleft()

        if len(window) >= limit:
            wait = round(60 - (now - window[0]), 1)
            return False, f"Rate limit hit for {tool_name} ({limit}/min). Retry in {wait}s."

        window.append(now)
        return True, "ok"

    def get_stats(self) -> Dict[str, int]:
        """Return current call counts per tool (for the trace panel)."""
        now = time.time()
        stats = {}
        for tool, window in self._windows.items():
            recent = sum(1 for t in window if t > now - 60)
            stats[tool] = recent
        return stats


# ══════════════════════════════════════════════════════════
# DESTRUCTIVE ACTION PREVENTION
# ══════════════════════════════════════════════════════════

# Tool names that should NEVER be called by any agent
FORBIDDEN_TOOLS = {
    "delete_file",
    "drop_table",
    "send_email_without_approval",
    "execute_shell",
    "modify_system_config",
    "revoke_credentials",
}

# Maximum tokens an agent can send in a single Gemini call
MAX_PROMPT_TOKENS = 8000

# Maximum output size from any agent (bytes) — prevents runaway generation
MAX_OUTPUT_BYTES = 1_000_000  # 1MB


def check_tool_allowed(tool_name: str) -> Tuple[bool, str]:
    """
    ADK safety guardrail: verify a tool is not on the forbidden list
    before the agent calls it.
    """
    if tool_name.lower() in FORBIDDEN_TOOLS:
        return False, f"BLOCKED: Tool '{tool_name}' is on the forbidden list. Agents cannot take destructive actions."
    return True, "allowed"


def check_output_size(data: Any, agent_id: str) -> Tuple[bool, str]:
    """Ensure agent output doesn't exceed the size cap."""
    import json
    try:
        size = len(json.dumps(data).encode("utf-8"))
    except Exception:
        size = 0

    if size > MAX_OUTPUT_BYTES:
        return False, f"Agent {agent_id} output too large ({size:,} bytes > {MAX_OUTPUT_BYTES:,} limit). Truncating."
    return True, "ok"


# ══════════════════════════════════════════════════════════
# GUARDRAIL MIDDLEWARE — wraps BaseAgent._run_tool_with_retry
# ══════════════════════════════════════════════════════════

# Global rate limiter instance (shared across all agents)
rate_limiter = RateLimiter()


def apply_guardrails(tool_name: str, agent_id: str) -> Tuple[bool, str]:
    """
    Single entry-point guardrail check called before every MCP tool invocation.
    Returns (proceed: bool, reason: str).
    """
    # 1. Forbidden tool check
    allowed, reason = check_tool_allowed(tool_name)
    if not allowed:
        return False, reason

    # 2. Rate limit check
    within_limit, reason = rate_limiter.check(tool_name)
    if not within_limit:
        return False, reason

    return True, "ok"


# ══════════════════════════════════════════════════════════
# REPORT SAFETY CHECK
# ══════════════════════════════════════════════════════════

def sanitize_final_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final pass on the Gemini-generated report before it's shown to users.
    - Scrubs PII
    - Caps field lengths
    - Removes any internal error details that shouldn't be user-facing
    """
    report = _scrub_pii(report)

    # Cap long text fields
    for key in ("executive_summary", "recommendation", "company_overview", "market_opportunity"):
        if isinstance(report.get(key), str) and len(report[key]) > 1500:
            report[key] = report[key][:1500] + "... [truncated]"

    # Remove internal debug fields from user-facing output
    report.pop("_gemini_error", None)
    report.pop("_raw_prompt", None)

    # Validate investment verdict is one of the allowed values
    allowed_verdicts = {"BUY", "HOLD", "AVOID", "INSUFFICIENT DATA"}
    if report.get("investment_verdict") not in allowed_verdicts:
        report["investment_verdict"] = "INSUFFICIENT DATA"

    # Clamp confidence score
    score = report.get("confidence_score", 0)
    if isinstance(score, (int, float)):
        report["confidence_score"] = max(0, min(100, int(score)))

    return report
