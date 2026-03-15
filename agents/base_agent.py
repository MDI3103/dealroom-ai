"""
Base Agent — shared recovery, retry, and reasoning trace logic.
All specialist agents inherit from this class.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
    )
    _TENACITY_AVAILABLE = True
except ImportError:
    _TENACITY_AVAILABLE = False

from a2a.messaging import A2ABus, A2AMessage, make_error, bus
from guardrails.safety import apply_guardrails, validate_agent_output, check_output_size


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
    RECOVERED = "recovered"
    DONE = "done"


@dataclass
class TraceEntry:
    agent_id: str
    step: str
    detail: str
    status: str = "info"       # info | success | warning | error | tool_call
    timestamp: float = field(default_factory=time.time)
    duration_ms: Optional[float] = None
    tool_name: Optional[str] = None
    tool_result_preview: Optional[str] = None


@dataclass
class AgentResult:
    agent_id: str
    success: bool
    data: Dict[str, Any]
    trace: List[TraceEntry]
    error: Optional[str] = None
    recovered: bool = False
    duration_seconds: float = 0.0


class BaseAgent(ABC):
    """
    Abstract base for all DealRoom AI agents.
    Provides:
    - Retry with exponential backoff (tenacity)
    - Fallback chain execution
    - Reasoning trace collection
    - A2A message handling
    - Timeout enforcement
    - Dead-agent recovery signalling
    """

    def __init__(self, agent_id: str, timeout: float = 30.0, max_retries: int = 3):
        self.agent_id = agent_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.status = AgentStatus.IDLE
        self._trace: List[TraceEntry] = []
        self._a2a_bus: A2ABus = bus
        self._a2a_bus.register_agent(agent_id)

    # ── Tracing ───────────────────────────────────────────

    def _log(self, step: str, detail: str, status: str = "info",
             tool_name: str = None, tool_result_preview: str = None,
             duration_ms: float = None):
        entry = TraceEntry(
            agent_id=self.agent_id,
            step=step,
            detail=detail,
            status=status,
            tool_name=tool_name,
            tool_result_preview=tool_result_preview,
            duration_ms=duration_ms,
        )
        self._trace.append(entry)
        return entry

    def _tool_call(self, tool_name: str, params: str) -> TraceEntry:
        return self._log(
            step=f"Calling tool: {tool_name}",
            detail=f"Params: {params}",
            status="tool_call",
            tool_name=tool_name,
        )

    def _tool_result(self, tool_name: str, result_preview: str, duration_ms: float = None):
        return self._log(
            step=f"Tool result: {tool_name}",
            detail=result_preview,
            status="success",
            tool_name=tool_name,
            tool_result_preview=result_preview,
            duration_ms=duration_ms,
        )

    def _warn(self, step: str, detail: str):
        return self._log(step, detail, status="warning")

    def _error(self, step: str, detail: str):
        return self._log(step, detail, status="error")

    # ── A2A ──────────────────────────────────────────────

    async def send_flag(self, recipient: str, flag_type: str, detail: str, severity: str = "high"):
        """Send a risk flag to another agent via A2A."""
        from a2a.messaging import make_flag
        msg = make_flag(self.agent_id, recipient, flag_type, detail, severity)
        await self._a2a_bus.send(msg)
        self._log(
            step=f"A2A → {recipient}",
            detail=f"[{severity.upper()}] {flag_type}: {detail}",
            status="warning",
        )

    async def send_result_to(self, recipient: str, data: Dict, correlation_id: str = None):
        from a2a.messaging import make_result
        msg = make_result(self.agent_id, recipient, data, correlation_id)
        await self._a2a_bus.send(msg)

    async def check_inbox(self) -> Optional[A2AMessage]:
        """Non-blocking check for incoming A2A messages."""
        return await self._a2a_bus.receive(self.agent_id, timeout=0.1)

    # ── Tool execution with retry ─────────────────────────

    async def _run_tool_with_retry(
        self,
        tool_fn: Callable,
        tool_name: str,
        params_description: str,
        fallback_fn: Optional[Callable] = None,
        tool_args: tuple = (),
        tool_kwargs: dict = None,
    ) -> Any:
        """
        Execute a tool with exponential backoff retry.
        Falls back to fallback_fn if all retries fail.
        """
        if tool_kwargs is None:
            tool_kwargs = {}
        t0 = time.time()
        self._tool_call(tool_name, params_description)

        # ── Guardrail check before calling any MCP tool ──
        allowed, reason = apply_guardrails(tool_name, self.agent_id)
        if not allowed:
            self._warn(f"Guardrail blocked {tool_name}", reason)
            if fallback_fn:
                self._log(f"Guardrail fallback", f"Using fallback due to block: {reason}", status="warning")
                try:
                    return await asyncio.get_running_loop().run_in_executor(None, fallback_fn)
                except Exception:
                    pass
            return None

        for attempt in range(1, self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(tool_fn):
                    result = await asyncio.wait_for(
                        tool_fn(*tool_args, **tool_kwargs), timeout=self.timeout
                    )
                else:
                    result = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: tool_fn(*tool_args, **tool_kwargs)
                    )

                duration_ms = (time.time() - t0) * 1000
                preview = str(result)[:200] if result else "empty"
                self._tool_result(tool_name, preview, duration_ms)
                return result

            except asyncio.TimeoutError:
                self._warn(
                    f"Timeout on {tool_name} (attempt {attempt}/{self.max_retries})",
                    f"Exceeded {self.timeout}s — retrying with backoff",
                )
            except Exception as e:
                self._warn(
                    f"Error on {tool_name} (attempt {attempt}/{self.max_retries})",
                    str(e),
                )

            if attempt < self.max_retries:
                wait = 2 ** attempt
                await asyncio.sleep(wait)

        # All retries failed — try fallback
        if fallback_fn:
            self._warn(
                f"All retries failed for {tool_name}",
                "Activating fallback strategy",
            )
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, fallback_fn
                )
                self._log(
                    f"Fallback succeeded for {tool_name}",
                    str(result)[:200],
                    status="success",
                )
                return result
            except Exception as fe:
                self._error(f"Fallback also failed for {tool_name}", str(fe))

        self._error(f"{tool_name} failed after {self.max_retries} attempts", "Returning None")
        return None

    # ── Main run interface ────────────────────────────────

    async def run(self, company: str, **kwargs) -> AgentResult:
        """
        Entry point. Wraps _execute with timeout enforcement
        and dead-agent recovery signalling.
        """
        self.status = AgentStatus.RUNNING
        self._trace = []
        t0 = time.time()

        self._log(f"Agent {self.agent_id} started", f"Analysing: {company}", status="info")

        try:
            data = await asyncio.wait_for(
                self._execute(company, **kwargs), timeout=self.timeout
            )
            self.status = AgentStatus.DONE
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                data=data,
                trace=self._trace,
                duration_seconds=time.time() - t0,
            )

        except asyncio.TimeoutError:
            self.status = AgentStatus.FAILED
            self._error("Agent timed out", f"Exceeded {self.timeout}s limit")
            await self._a2a_bus.send(
                make_error("orchestrator", self.agent_id,
                           f"{self.agent_id} timed out after {self.timeout}s")
            )
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                data=self._partial_data(),
                trace=self._trace,
                error=f"Agent timed out after {self.timeout}s",
                duration_seconds=time.time() - t0,
            )

        except Exception as e:
            self.status = AgentStatus.FAILED
            self._error("Unhandled agent error", traceback.format_exc())
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                data=self._partial_data(),
                trace=self._trace,
                error=str(e),
                duration_seconds=time.time() - t0,
            )

    @abstractmethod
    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        """Subclasses implement their core logic here."""
        ...

    def _partial_data(self) -> Dict:
        """Return whatever partial data was collected before failure."""
        return {"partial": True, "agent_id": self.agent_id}
