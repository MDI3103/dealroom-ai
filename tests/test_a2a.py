"""
tests/test_a2a.py
Tests for A2A messaging protocol:
bus registration, send/receive, flag factories,
broadcast, message logging, and priority ordering.
"""

import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from a2a.messaging import (
    A2ABus,
    A2AMessage,
    MessageType,
    MessagePriority,
    make_flag,
    make_result,
    make_error,
)


# ── Helpers ───────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ══════════════════════════════════════════════════════════
# BUS REGISTRATION & MESSAGING
# ══════════════════════════════════════════════════════════

class TestA2ABus:

    def setup_method(self):
        """Fresh bus for each test."""
        self.bus = A2ABus()

    def test_register_agent(self):
        self.bus.register_agent("agent_a")
        assert "agent_a" in self.bus._queues

    def test_double_register_no_error(self):
        self.bus.register_agent("agent_a")
        self.bus.register_agent("agent_a")  # Should not raise
        assert "agent_a" in self.bus._queues

    def test_send_and_receive(self):
        self.bus.register_agent("sender")
        self.bus.register_agent("receiver")

        msg = A2AMessage(
            sender="sender",
            recipient="receiver",
            message_type=MessageType.RESULT,
            payload={"data": "hello"},
        )

        run(self.bus.send(msg))
        received = run(self.bus.receive("receiver", timeout=1.0))

        assert received is not None
        assert received.sender == "sender"
        assert received.payload["data"] == "hello"

    def test_receive_timeout_returns_none(self):
        self.bus.register_agent("lonely_agent")
        result = run(self.bus.receive("lonely_agent", timeout=0.1))
        assert result is None

    def test_receive_unregistered_returns_none(self):
        result = run(self.bus.receive("ghost_agent", timeout=0.1))
        assert result is None

    def test_message_log_records_all_sends(self):
        self.bus.register_agent("a")
        self.bus.register_agent("b")

        for i in range(3):
            msg = A2AMessage(
                sender="a", recipient="b",
                message_type=MessageType.FLAG,
                payload={"i": i},
            )
            run(self.bus.send(msg))

        log = self.bus.get_log()
        assert len(log) == 3

    def test_broadcast_reaches_all_agents(self):
        for agent in ["a", "b", "c", "d"]:
            self.bus.register_agent(agent)

        run(self.bus.broadcast("a", MessageType.RESULT, {"broadcast": True}))

        for agent in ["b", "c", "d"]:
            msg = run(self.bus.receive(agent, timeout=0.5))
            assert msg is not None
            assert msg.payload["broadcast"] is True

    def test_broadcast_sender_not_included(self):
        for agent in ["a", "b"]:
            self.bus.register_agent(agent)

        run(self.bus.broadcast("a", MessageType.RESULT, {}))
        msg = run(self.bus.receive("a", timeout=0.1))
        assert msg is None  # Sender should not receive its own broadcast

    def test_subscriber_called_on_send(self):
        received_messages = []

        async def callback(msg):
            received_messages.append(msg)

        self.bus.register_agent("agent_x")
        self.bus.subscribe("*", callback)

        msg = A2AMessage(
            sender="agent_x", recipient="agent_x",
            message_type=MessageType.TASK,
            payload={"task": "test"},
        )
        run(self.bus.send(msg))

        assert len(received_messages) == 1
        assert received_messages[0].payload["task"] == "test"


# ══════════════════════════════════════════════════════════
# MESSAGE FACTORIES
# ══════════════════════════════════════════════════════════

class TestMessageFactories:

    def test_make_flag_high_severity(self):
        msg = make_flag(
            sender="risk_assessor",
            recipient="financial_analyst",
            flag_type="revenue_mismatch",
            detail="Reported revenue 3x higher than EDGAR filing",
            severity="high",
        )
        assert msg.message_type == MessageType.FLAG
        assert msg.priority == MessagePriority.HIGH
        assert msg.payload["flag_type"] == "revenue_mismatch"
        assert msg.payload["severity"] == "high"
        assert msg.sender == "risk_assessor"
        assert msg.recipient == "financial_analyst"

    def test_make_flag_critical_priority(self):
        msg = make_flag("a", "b", "fraud", "SEC enforcement action", severity="critical")
        assert msg.priority == MessagePriority.CRITICAL

    def test_make_flag_low_priority(self):
        msg = make_flag("a", "b", "minor_concern", "Small issue", severity="low")
        assert msg.priority == MessagePriority.LOW

    def test_make_result(self):
        msg = make_result(
            sender="market_research",
            recipient="orchestrator",
            data={"summary": {"company": "Grab"}},
            correlation_id="task-001",
        )
        assert msg.message_type == MessageType.RESULT
        assert msg.payload["summary"]["company"] == "Grab"
        assert msg.correlation_id == "task-001"

    def test_make_error(self):
        msg = make_error(
            sender="financial_analyst",
            recipient="orchestrator",
            error="yfinance timeout after 30s",
        )
        assert msg.message_type == MessageType.ERROR
        assert msg.priority == MessagePriority.HIGH
        assert "timeout" in msg.payload["error"]

    def test_message_has_unique_id(self):
        msg1 = make_result("a", "b", {})
        msg2 = make_result("a", "b", {})
        assert msg1.message_id != msg2.message_id

    def test_message_serialization_roundtrip(self):
        original = make_flag("risk_assessor", "financial_analyst", "fraud", "details", "critical")
        as_dict = original.to_dict()
        restored = A2AMessage.from_dict(as_dict)

        assert restored.sender == original.sender
        assert restored.recipient == original.recipient
        assert restored.message_type == original.message_type
        assert restored.priority == original.priority
        assert restored.payload == original.payload


# ══════════════════════════════════════════════════════════
# FILTER & LOG METHODS
# ══════════════════════════════════════════════════════════

class TestBusLogFiltering:

    def setup_method(self):
        self.bus = A2ABus()
        for agent in ["risk_assessor", "financial_analyst", "orchestrator", "market_research"]:
            self.bus.register_agent(agent)

    def _send(self, sender, recipient, mtype=MessageType.RESULT):
        msg = A2AMessage(sender=sender, recipient=recipient,
                         message_type=mtype, payload={})
        run(self.bus.send(msg))

    def test_get_log_for_agents_filters_correctly(self):
        self._send("risk_assessor", "financial_analyst", MessageType.FLAG)
        self._send("market_research", "orchestrator")
        self._send("orchestrator", "financial_analyst")

        log = self.bus.get_log_for_agents(["risk_assessor", "financial_analyst"])

        # Should include: risk→financial, orch→financial — but NOT market→orchestrator
        senders_recipients = [(m["sender"], m["recipient"]) for m in log]
        assert ("market_research", "orchestrator") not in senders_recipients
        assert ("risk_assessor", "financial_analyst") in senders_recipients

    def test_empty_log_initially(self):
        fresh = A2ABus()
        assert fresh.get_log() == []
