"""Real MCP stdio server exposing only the exercise's bounded read tools."""

import argparse
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from . import gateway


def create_server(database: Path) -> FastMCP:
    database = database.resolve(strict=True)
    # SQLite itself rejects writes, even if a tool accidentally attempts one.
    engine = create_engine(f"sqlite:///file:{database.as_posix()}?mode=ro&uri=true")
    server = FastMCP("Lesson 5 CDC Gateway", log_level="ERROR")
    annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=annotations)
    def list_entities() -> dict[str, Any]:
        """Discover the projection and change history available to agents."""
        return gateway.list_entities().as_dict()

    @server.tool(annotations=annotations)
    def get_record(entity: str, record_id: str, fields: list[str] | None = None) -> dict[str, Any]:
        """Read one record with only approved fields."""
        with Session(engine) as db:
            return gateway.get_record(db, entity, record_id, fields).as_dict()

    @server.tool(annotations=annotations)
    def search_records(
        entity: str, min_priority_score: int | None = None, limit: int = 5
    ) -> dict[str, Any]:
        """Search the bounded projection, capped at 25 results."""
        with Session(engine) as db:
            return gateway.search_records(db, entity, min_priority_score, limit).as_dict()

    @server.tool(annotations=annotations)
    def get_change_history(entity: str, record_id: str, limit: int = 10) -> dict[str, Any]:
        """Read CDC-derived history, newest first, capped at 25 results."""
        with Session(engine) as db:
            return gateway.get_change_history(db, entity, record_id, limit).as_dict()

    @server.tool(annotations=annotations)
    def get_freshness_status(
        entity: str, record_id: str, budget_seconds: float = 300
    ) -> dict[str, Any]:
        """Check freshness metadata for the retrieved projection."""
        with Session(engine) as db:
            return gateway.get_freshness_status(db, entity, record_id, budget_seconds).as_dict()

    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    create_server(parser.parse_args().database).run(transport="stdio")
