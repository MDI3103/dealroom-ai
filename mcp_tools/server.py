"""
a2a/server.py — A2A Protocol Server (FastAPI)
Exposes DealRoom AI agents as A2A-compliant HTTP endpoints.

Implements the Google A2A spec:
- GET  /.well-known/agent.json     → Agent card discovery
- POST /tasks/send                 → Submit a task to an agent
- GET  /tasks/{task_id}            → Poll task status
- POST /tasks/{task_id}/cancel     → Cancel a running task
- GET  /tasks/{task_id}/events     → SSE streaming of task events

In production, each agent would run as its own A2A server on a separate port.
For the hackathon, all agents are served from a single FastAPI app.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# Import the agent card from ADK config
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adk_config import AGENT_CARD
from orchestrator.orchestrator_agent import OrchestratorAgent
from a2a.messaging import bus

app = FastAPI(
    title="DealRoom AI — A2A Server",
    description="A2A-compliant multi-agent due diligence API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task store (use Redis in production)
_tasks: Dict[str, Dict] = {}
_task_events: Dict[str, list] = {}


# ── Pydantic models ───────────────────────────────────────

class TaskInput(BaseModel):
    id: Optional[str] = None
    message: Dict[str, Any]   # A2A message object
    sessionId: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    status: Dict[str, Any]
    artifacts: list = []


# ── A2A Endpoints ─────────────────────────────────────────

@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A agent discovery — returns the agent card."""
    return JSONResponse(content=AGENT_CARD)


@app.post("/tasks/send")
async def send_task(task_input: TaskInput) -> TaskResponse:
    """
    Submit a task to DealRoom AI.
    Extracts company name from the A2A message and starts analysis.
    """
    task_id = task_input.id or str(uuid.uuid4())

    # Extract text from A2A message
    msg = task_input.message
    parts = msg.get("parts", [])
    text = " ".join(
        p.get("text", "") for p in parts if p.get("type") == "text"
    ).strip()

    if not text:
        raise HTTPException(status_code=400, detail="No text content in message.")

    # Extract company name (strip common prefixes)
    company = text
    for prefix in ["analyse ", "analyze ", "research ", "due diligence on ", "check "]:
        if company.lower().startswith(prefix):
            company = company[len(prefix):]
            break

    # Register task
    _tasks[task_id] = {
        "id": task_id,
        "status": {"state": "submitted", "timestamp": time.time()},
        "company": company,
        "result": None,
    }
    _task_events[task_id] = []

    # Run analysis in background
    asyncio.create_task(_run_analysis(task_id, company))

    return TaskResponse(
        id=task_id,
        status={"state": "submitted", "message": f"Analysis of '{company}' started."},
    )


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> Dict:
    """Poll task status and results."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    task = _tasks[task_id]

    response = {
        "id": task_id,
        "status": task["status"],
        "artifacts": [],
    }

    if task.get("result"):
        report = task["result"].get("report", {})
        response["artifacts"] = [
            {
                "name": "due_diligence_report",
                "parts": [
                    {
                        "type": "data",
                        "data": report,
                        "mimeType": "application/json",
                    }
                ],
            }
        ]

    return response


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    _tasks[task_id]["status"] = {"state": "canceled", "timestamp": time.time()}
    return {"id": task_id, "status": {"state": "canceled"}}


@app.get("/tasks/{task_id}/events")
async def task_events(task_id: str):
    """
    SSE stream of task events for real-time progress updates.
    Clients can subscribe to watch agent traces as they happen.
    """
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    async def event_generator() -> AsyncGenerator[str, None]:
        sent_count = 0
        while True:
            events = _task_events.get(task_id, [])
            # Send any new events
            while sent_count < len(events):
                event = events[sent_count]
                yield f"data: {json.dumps(event)}\n\n"
                sent_count += 1

            # Check if task is complete
            task = _tasks.get(task_id, {})
            if task.get("status", {}).get("state") in ("completed", "failed", "canceled"):
                yield f"data: {json.dumps({'type': 'done', 'state': task['status']['state']})}\n\n"
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DealRoom AI A2A Server", "version": "1.0.0"}


# ── Background task runner ────────────────────────────────

async def _run_analysis(task_id: str, company: str):
    """Run the orchestrator and update task state with streaming events."""

    def on_trace(entry: dict):
        """Called by orchestrator on each trace event — stream to SSE."""
        _task_events[task_id].append({"type": "trace", **entry})
        _tasks[task_id]["status"] = {
            "state": "working",
            "message": f"{entry.get('agent', '?')}: {entry.get('step', '')}",
            "timestamp": time.time(),
        }

    _tasks[task_id]["status"] = {"state": "working", "timestamp": time.time()}

    try:
        orchestrator = OrchestratorAgent(trace_callback=on_trace)
        result = await orchestrator.analyse(company)
        _tasks[task_id]["result"] = result
        _tasks[task_id]["status"] = {
            "state": "completed",
            "timestamp": time.time(),
            "duration": result.get("duration_seconds"),
        }
    except Exception as e:
        _tasks[task_id]["status"] = {
            "state": "failed",
            "timestamp": time.time(),
            "error": str(e),
        }
        _task_events[task_id].append({"type": "error", "error": str(e)})


# ── Run server ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(__import__("os").getenv("ORCHESTRATOR_PORT", "8000"))
    print(f"Starting DealRoom AI A2A Server on port {port}")
    print(f"Agent card: http://localhost:{port}/.well-known/agent.json")
    uvicorn.run(app, host="0.0.0.0", port=port)
