"""
A2A (Agent-to-Agent) Messaging Protocol
Implements Google's A2A standard for peer-to-peer agent communication.
Agents can send structured messages directly to each other without
routing through the orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageType(str, Enum):
    TASK = "task"
    RESULT = "result"
    FLAG = "flag"           # Risk flags / alerts
    QUERY = "query"         # One agent asking another a question
    ACK = "ack"             # Acknowledgement
    ERROR = "error"


@dataclass
class A2AMessage:
    sender: str
    recipient: str
    message_type: MessageType
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None  # Links replies to original message

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["message_type"] = self.message_type.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "A2AMessage":
        d["message_type"] = MessageType(d["message_type"])
        d["priority"] = MessagePriority(d["priority"])
        return cls(**d)


class A2ABus:
    """
    In-process message bus for A2A communication.
    Each agent registers itself and can send/receive messages.
    In production this would be backed by a message broker (Pub/Sub, Redis Streams).
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_log: List[A2AMessage] = []
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._loop_id: Optional[int] = None

    def reset(self):
        """
        Destroy all Queue objects and clear state.
        Must be called before each analysis run so queues are
        re-created inside the correct event loop.
        """
        self._queues = {}
        self._handlers = defaultdict(list)
        self._message_log = []
        self._subscribers = defaultdict(list)
        self._loop_id = None

    def _ensure_loop_match(self):
        """
        If the running event loop has changed since queues were created,
        recreate all queues in the new loop.  Silently fixes the
        'bound to a different event loop' error on repeated Streamlit runs.
        """
        try:
            current = id(asyncio.get_running_loop())
        except RuntimeError:
            return
        if self._loop_id is not None and self._loop_id != current:
            # New loop — recreate every queue so they bind to the right loop
            agent_ids = list(self._queues.keys())
            self._queues = {aid: asyncio.Queue() for aid in agent_ids}
            self._message_log = []
        self._loop_id = current

    def register_agent(self, agent_id: str):
        """Register an agent on the bus."""
        self._ensure_loop_match()
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()

    def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe to incoming messages for an agent."""
        self._subscribers[agent_id].append(callback)

    async def send(self, message: A2AMessage):
        """Send a message from one agent to another."""
        self._ensure_loop_match()
        self._message_log.append(message)

        if message.recipient not in self._queues:
            self.register_agent(message.recipient)

        await self._queues[message.recipient].put(message)

        # Notify subscribers (e.g. UI trace panel)
        for cb in self._subscribers.get("*", []):
            await cb(message)

    async def receive(self, agent_id: str, timeout: float = 5.0) -> Optional[A2AMessage]:
        """Receive the next message for an agent."""
        if agent_id not in self._queues:
            return None
        try:
            return await asyncio.wait_for(
                self._queues[agent_id].get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    async def broadcast(self, sender: str, message_type: MessageType, payload: Dict):
        """Send a message to all registered agents."""
        for agent_id in self._queues:
            if agent_id != sender:
                msg = A2AMessage(
                    sender=sender,
                    recipient=agent_id,
                    message_type=message_type,
                    payload=payload,
                    priority=MessagePriority.NORMAL,
                )
                await self.send(msg)

    def get_log(self) -> List[Dict]:
        """Return full message history for trace panel."""
        return [m.to_dict() for m in self._message_log]

    def get_log_for_agents(self, agent_ids: List[str]) -> List[Dict]:
        return [
            m.to_dict()
            for m in self._message_log
            if m.sender in agent_ids or m.recipient in agent_ids
        ]


# ── Pre-built message factories ────────────────────────────

def make_flag(sender: str, recipient: str, flag_type: str, detail: str,
              severity: str = "medium", correlation_id: str = None) -> A2AMessage:
    """Create a risk flag message (e.g. Risk Assessor → Financial Analyst)."""
    priority_map = {"low": MessagePriority.LOW, "medium": MessagePriority.NORMAL,
                    "high": MessagePriority.HIGH, "critical": MessagePriority.CRITICAL}
    return A2AMessage(
        sender=sender,
        recipient=recipient,
        message_type=MessageType.FLAG,
        payload={"flag_type": flag_type, "detail": detail, "severity": severity},
        priority=priority_map.get(severity, MessagePriority.NORMAL),
        correlation_id=correlation_id,
    )


def make_result(sender: str, recipient: str, data: Dict,
                correlation_id: str = None) -> A2AMessage:
    """Create a result message."""
    return A2AMessage(
        sender=sender,
        recipient=recipient,
        message_type=MessageType.RESULT,
        payload=data,
        correlation_id=correlation_id,
    )


def make_error(sender: str, recipient: str, error: str,
               correlation_id: str = None) -> A2AMessage:
    """Create an error notification message."""
    return A2AMessage(
        sender=sender,
        recipient=recipient,
        message_type=MessageType.ERROR,
        payload={"error": error},
        priority=MessagePriority.HIGH,
        correlation_id=correlation_id,
    )


# Singleton bus instance shared across all agents
bus = A2ABus()
