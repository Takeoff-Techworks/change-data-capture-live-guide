"""A small, transparent, read-only course-local tool gateway.

Session 5 teaches MCP as a governed access layer over a CDC-maintained agent
data store and change history, not a way to hand an agent arbitrary SQL
access to the production/source tables. This package intentionally exposes a
tiny allowlist of read-only tools backed by `app.ai.context_store` and the
CDC-derived `PatientTimeline`, so callers can only ever see the same bounded,
authorized facts a human operator would.
"""
