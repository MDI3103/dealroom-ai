"""
tests/test_agent_recovery.py
Tests for agent-level recovery mechanisms:
retry logic, fallback chains, timeout handling,
dead-agent partial results, and trace emission.
"""

import asyncio
import time
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, AgentStatus, AgentResult, TraceEntry


# ── Concrete test agent ───────────────────────────────────

class EchoAgent(BaseAgent):
    """Minimal concrete agent for testing base class behaviour."""

    def __init__(self, timeout=10.0):
        super().__init__(agent_id="echo_agent", timeout=timeout, max_retries=3)
        self.execute_called = 0

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self.execute_called += 1
        return {"company": company, "result": "ok"}


class FailingAgent(BaseAgent):
    """Agent that always raises an exception."""

    def __init__(self):
        super().__init__(agent_id="failing_agent", timeout=10.0, max_retries=2)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        raise ValueError("Simulated agent failure")


class SlowAgent(BaseAgent):
    """Agent that sleeps longer than the timeout."""

    def __init__(self):
        super().__init__(agent_id="slow_agent", timeout=0.2, max_retries=1)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        await asyncio.sleep(5.0)  # Much longer than timeout
        return {}


# ── Helpers ───────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ══════════════════════════════════════════════════════════
# BASIC AGENT EXECUTION
# ══════════════════════════════════════════════════════════

class TestBaseAgentExecution:

    def test_successful_run_returns_result(self):
        agent = EchoAgent()
        result = run(agent.run("Grab"))

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.agent_id == "echo_agent"
        assert result.data["company"] == "Grab"
        assert result.error is None

    def test_failed_agent_returns_failure_result(self):
        agent = FailingAgent()
        result = run(agent.run("Grab"))

        assert result.success is False
        assert result.error is not None
        assert "Simulated agent failure" in result.error

    def test_timed_out_agent_returns_failure(self):
        agent = SlowAgent()
        result = run(agent.run("Grab"))

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower() or "timeout" in result.error.lower()

    def test_duration_is_recorded(self):
        agent = EchoAgent()
        result = run(agent.run("Grab"))
        assert result.duration_seconds >= 0

    def test_trace_is_populated(self):
        agent = EchoAgent()
        result = run(agent.run("Grab"))
        assert len(result.trace) > 0

    def test_trace_has_start_entry(self):
        agent = EchoAgent()
        result = run(agent.run("Grab"))
        steps = [t.step for t in result.trace]
        assert any("started" in s.lower() for s in steps)

    def test_agent_status_resets_per_run(self):
        agent = EchoAgent()
        run(agent.run("Grab"))
        assert agent.status == AgentStatus.DONE
        run(agent.run("Notion"))  # Second run
        assert agent.status == AgentStatus.DONE


# ══════════════════════════════════════════════════════════
# TOOL RETRY LOGIC
# ══════════════════════════════════════════════════════════

class TestToolRetry:

    def test_successful_tool_call(self):
        agent = EchoAgent()
        call_count = 0

        def fake_tool(x):
            nonlocal call_count
            call_count += 1
            return {"data": x}

        result = run(agent._run_tool_with_retry(
            tool_fn=fake_tool,
            tool_name="fake_tool",
            params_description="x=test",
            fallback_fn=None,
            "test_input",
        ))

        assert result == {"data": "test_input"}
        assert call_count == 1

    def test_retries_on_failure_then_succeeds(self):
        agent = EchoAgent()
        call_count = 0

        def flaky_tool():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return {"success": True}

        result = run(agent._run_tool_with_retry(
            tool_fn=flaky_tool,
            tool_name="flaky_tool",
            params_description="",
            fallback_fn=None,
        ))

        assert result == {"success": True}
        assert call_count == 2

    def test_fallback_used_after_all_retries_fail(self):
        agent = EchoAgent()
        agent.max_retries = 2

        def always_fails():
            raise RuntimeError("Always fails")

        def fallback():
            return {"fallback": True}

        result = run(agent._run_tool_with_retry(
            tool_fn=always_fails,
            tool_name="always_fails",
            params_description="",
            fallback_fn=fallback,
        ))

        assert result == {"fallback": True}

    def test_returns_none_when_all_fail_no_fallback(self):
        agent = EchoAgent()
        agent.max_retries = 2

        def always_fails():
            raise RuntimeError("Always fails")

        result = run(agent._run_tool_with_retry(
            tool_fn=always_fails,
            tool_name="always_fails",
            params_description="",
            fallback_fn=None,
        ))

        assert result is None

    def test_trace_records_tool_call(self):
        agent = EchoAgent()

        def simple_tool():
            return "result"

        run(agent._run_tool_with_retry(
            tool_fn=simple_tool,
            tool_name="my_tool",
            params_description="no params",
            fallback_fn=None,
        ))

        tool_steps = [t for t in agent._trace if t.tool_name == "my_tool"]
        assert len(tool_steps) > 0

    def test_trace_records_warnings_on_retry(self):
        agent = EchoAgent()
        agent.max_retries = 3

        attempts = [0]

        def sometimes_fails():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("fail")
            return "ok"

        run(agent._run_tool_with_retry(
            tool_fn=sometimes_fails,
            tool_name="sometimes_fails",
            params_description="",
            fallback_fn=None,
        ))

        warning_entries = [t for t in agent._trace if t.status == "warning"]
        assert len(warning_entries) >= 2  # One warning per failure attempt


# ══════════════════════════════════════════════════════════
# TRACE LOGGING
# ══════════════════════════════════════════════════════════

class TestTraceLogging:

    def test_log_creates_trace_entry(self):
        agent = EchoAgent()
        agent._log("Test Step", "Some detail", status="info")

        assert len(agent._trace) == 1
        entry = agent._trace[0]
        assert entry.step == "Test Step"
        assert entry.detail == "Some detail"
        assert entry.status == "info"
        assert entry.agent_id == "echo_agent"

    def test_warn_creates_warning_entry(self):
        agent = EchoAgent()
        agent._warn("Warning step", "Warning detail")
        assert agent._trace[-1].status == "warning"

    def test_error_creates_error_entry(self):
        agent = EchoAgent()
        agent._error("Error step", "Error detail")
        assert agent._trace[-1].status == "error"

    def test_tool_call_creates_tool_call_entry(self):
        agent = EchoAgent()
        agent._tool_call("my_tool", "param=value")
        entry = agent._trace[-1]
        assert entry.status == "tool_call"
        assert entry.tool_name == "my_tool"

    def test_trace_cleared_on_new_run(self):
        agent = EchoAgent()
        run(agent.run("Company A"))
        first_trace_len = len(agent._trace)

        run(agent.run("Company B"))
        # Trace should be fresh (not appended to previous)
        assert agent._trace[0].detail == "Analysing: Company B"


# ══════════════════════════════════════════════════════════
# A2A INTEGRATION IN AGENTS
# ══════════════════════════════════════════════════════════

class TestAgentA2A:

    def test_agent_registers_on_bus(self):
        from a2a.messaging import bus
        agent = EchoAgent()
        assert "echo_agent" in bus._queues

    def test_send_flag_adds_trace_entry(self):
        agent = EchoAgent()
        run(agent.send_flag("orchestrator", "test_flag", "test detail", "medium"))

        a2a_entries = [t for t in agent._trace if "A2A" in t.step]
        assert len(a2a_entries) == 1
        assert "orchestrator" in a2a_entries[0].step

    def test_check_inbox_empty_returns_none(self):
        agent = EchoAgent()
        msg = run(agent.check_inbox())
        assert msg is None
