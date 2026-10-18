"""Sprint 2 resumable investigation workflow (LangGraph + SQLite). See protocols/sprint02_workflow.md."""

import os

# LangGraph pulls in the LangSmith client. External tracing is not allowed (AGENTS.md): force it off.
for _name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
    os.environ[_name] = "false"
