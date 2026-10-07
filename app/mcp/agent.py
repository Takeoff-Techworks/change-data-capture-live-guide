"""A tiny deterministic client that decides which allowlisted tool to call.

This stands in for a real MCP-connected agent: given a course-local
question, it picks a bounded read-only tool call, records the call for
teaching/audit purposes, and returns the tool result. It never invents a
tool name outside `app.mcp.gateway.ALLOWED_TOOLS`.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from . import gateway


@dataclass
class ToolCallLog:
    question: str
    tool: str
    arguments: dict[str, Any]
    allowed: bool
    evidence_ids: list[str]
    freshness: dict[str, Any] | None = None


@dataclass
class DeterministicMCPClient:
    """Answers a small set of course questions using only gateway tools."""

    default_budget_seconds: float = 300
    call_log: list[ToolCallLog] = field(default_factory=list)

    def ask(self, db: Session, question: str, patient_id: str | None = None) -> dict[str, Any]:
        question_lower = question.lower()
        if "history" in question_lower or "change" in question_lower:
            tool, arguments = "get_change_history", {"entity": "care_work_queue", "record_id": patient_id}
        elif "top" in question_lower or "highest priority" in question_lower:
            tool, arguments = "search_records", {
                "entity": "care_work_queue",
                "min_priority_score": 1,
                "limit": 5,
            }
        elif "fresh" in question_lower or "current" in question_lower or "stale" in question_lower:
            tool, arguments = "get_freshness_status", {
                "entity": "care_work_queue",
                "record_id": patient_id,
                "budget_seconds": self.default_budget_seconds,
            }
        else:
            tool, arguments = "get_record", {"entity": "care_work_queue", "record_id": patient_id}
        result = gateway.invoke_tool(db, tool, arguments)
        freshness = None
        if tool == "get_freshness_status" and result.allowed:
            freshness = result.data
        self.call_log.append(
            ToolCallLog(
                question=question,
                tool=tool,
                arguments=arguments,
                allowed=result.allowed,
                evidence_ids=result.evidence_ids,
                freshness=freshness,
            )
        )
        return result.as_dict()
