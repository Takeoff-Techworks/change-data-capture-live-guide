"""Check that either notebook works without the web application installed."""

import ast
import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv

EXERCISES = pathlib.Path(__file__).resolve().parents[1]


@contextmanager
def isolated_folder():
    root = EXERCISES / f".lesson-check-{uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        assert root.resolve().parent == EXERCISES
        shutil.rmtree(root)


RUN_NOTEBOOK = r"""
import ast
import importlib.abc
import io
import json
import pathlib
import sys

class NotebookStderr(io.TextIOBase):
    def fileno(self):
        raise io.UnsupportedOperation("fileno")

    def write(self, value):
        return sys.__stderr__.write(value)

    def flush(self):
        sys.__stderr__.flush()

# Install before importing MCP: its default errlog captures stderr at import time.
sys.stderr = NotebookStderr()

class RejectApp(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app" or fullname.startswith("app."):
            raise AssertionError(f"Unexpected application dependency: {fullname}")

sys.meta_path.insert(0, RejectApp())
notebook = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
namespace = {"__name__": "__main__"}
for cell in notebook["cells"]:
    if cell["cell_type"] != "code":
        continue
    source = "".join(cell["source"])
    compiled = compile(source, cell["id"], "exec")
    if cell["id"] == "langchain-agent-example":
        # Validate the real tool locally; a live Gemini call needs credentials.
        tree = ast.parse(source)
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        exec(compile(tree, cell["id"], "exec"), namespace)
        result = namespace["retrieve_patient_context"].invoke({
            "patient_id": "p2", "question": "What is the current priority?"
        })
        assert result["authoritative"] and result["evidence_ids"]
        assert len(json.dumps(result)) < 1000
        missing = namespace["retrieve_patient_context"].invoke({
            "patient_id": "missing", "question": "What is the current priority?"
        })
        assert not missing["authoritative"]
        assert missing["answer"] == "Withheld: refresh required."
    elif cell["id"] == "llm-agent-optional":
        # Run the real agent graph and MCP tools, replacing only the paid model.
        import os
        from unittest.mock import patch
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langchain_core.messages import AIMessage, ToolMessage

        tool_arguments = {
            "list_entities": {},
            "get_record": {"entity": "care_work_queue", "record_id": "p4"},
            "search_records": {"entity": "care_work_queue", "limit": 2},
            "get_change_history": {"entity": "care_work_queue", "record_id": "p4"},
            "get_freshness_status": {"entity": "care_work_queue", "record_id": "p4"},
        }

        class OfflineToolModel(FakeMessagesListChatModel):
            received_tools: list[ToolMessage] = []

            def bind_tools(self, tools, **kwargs):
                assert {tool.name for tool in tools} == set(tool_arguments)
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                self.received_tools.extend(msg for msg in messages if isinstance(msg, ToolMessage))
                return super()._generate(messages, stop, run_manager, **kwargs)

        for provider in ("openai", "gemini"):
            offline_model = OfflineToolModel(responses=[
                AIMessage(content="", tool_calls=[
                    {"name": name, "args": arguments, "id": name}
                    for name, arguments in tool_arguments.items()
                ]),
                AIMessage(content="Current record retrieved with evidence."),
                AIMessage(content="", tool_calls=[{
                    "name": "get_record", "id": "denied-field",
                    "args": {"entity": "care_work_queue", "record_id": "p4",
                             "fields": ["birth_year"]},
                }]),
                AIMessage(content="The requested field is denied."),
                AIMessage(content="", tool_calls=[{
                    "name": "delete_record", "args": {}, "id": "denied-write",
                }]),
                AIMessage(content="No delete tool is available."),
            ])
            with (
                patch.dict(os.environ, {
                    "LLM_PROVIDER": provider,
                    "OPENAI_API_KEY": "offline-test-key",
                    "GOOGLE_API_KEY": "offline-test-key",
                }),
                patch("langchain_openai.ChatOpenAI", return_value=offline_model),
                patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=offline_model),
            ):
                exec(compiled, namespace)
            results = offline_model.received_tools
            assert len(results) == 7, results
            for message in results[:5]:
                result = json.loads(message.content)
                assert result["allowed"] and result["evidence_ids"], result
            denied = json.loads(results[5].content)
            assert not denied["allowed"] and "birth_year" in denied["denial_reason"]
            assert results[6].name == "delete_record" and results[6].status == "error"
    else:
        exec(compiled, namespace)

from cdc_lessons.models import CareWorkQueue, RawCDCEvent
from cdc_lessons.runtime import create_lesson_db, update_task
from sqlalchemy import select

first, second = create_lesson_db(), create_lesson_db()
try:
    update_task(first, "task1", status="completed")
    assert first.get(CareWorkQueue, "p2").open_task_count == 0
    assert second.get(CareWorkQueue, "p2").open_task_count == 1
    events = list(first.scalars(select(RawCDCEvent)))
    change = json.loads(events[-1].payload_json)
    assert change["before"]["status"] == "open"
    assert change["after"]["status"] == "completed"
finally:
    first.close()
    second.close()
assert not any(name == "app" or name.startswith("app.") for name in sys.modules)
"""


class StandaloneLessonsTest(unittest.TestCase):
    def test_agent_cells_reload_shared_provider_settings(self):
        for folder, cell_id in (
            ("04-cdc-for-ai", "langchain-agent-example"),
            ("05-mcp", "llm-agent-optional"),
        ):
            notebook = json.loads(next((EXERCISES / folder).glob("*.ipynb")).read_text(
                encoding="utf-8"
            ))
            cell = next(cell for cell in notebook["cells"] if cell["id"] == cell_id)
            tree = ast.parse("".join(cell["source"]))
            # Execute configuration up to model selection, without making API calls.
            provider_index = next(
                i for i, node in enumerate(tree.body)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "provider"
                        for target in node.targets)
            )
            tree.body = [node for node in tree.body[:provider_index + 1]
                         if not isinstance(node, ast.FunctionDef)]
            config = compile(tree, cell_id, "exec")
            with self.subTest(lesson=folder), isolated_folder() as shared, patch.dict(
                os.environ, {"LLM_PROVIDER": "gemini", "OPENAI_MODEL": "stale-model"}
            ):
                namespace = {"os": os, "load_dotenv": load_dotenv, "_SHARED": shared}
                for provider in ("openai", "gemini", "openai"):
                    (shared / ".env").write_text(
                        f"LLM_PROVIDER=' {provider.upper()} '\nOPENAI_MODEL=updated-model\n",
                        encoding="utf-8",
                    )
                    exec(config, namespace)  # noqa: S102 - execute repository notebook cells
                    self.assertEqual(namespace["provider"], provider)
                    self.assertEqual(os.environ["OPENAI_MODEL"], "updated-model")

    def test_notebooks_without_app(self):
        for folder in ("04-cdc-for-ai", "05-mcp"):
            for launch_from in ("root", "lesson"):
                with (
                    self.subTest(lesson=folder, launch_from=launch_from),
                    isolated_folder() as temp,
                ):
                    root = pathlib.Path(temp)
                    shared = root / "shared"
                    shutil.copytree(
                        EXERCISES / "shared" / "cdc_lessons",
                        shared / "cdc_lessons",
                        ignore=shutil.ignore_patterns("__pycache__"),
                    )
                    lesson = root / folder
                    lesson.mkdir()
                    source = next((EXERCISES / folder).glob("*.ipynb"))
                    notebook = lesson / source.name
                    shutil.copy2(source, notebook)
                    result = subprocess.run(
                        [sys.executable, "-c", RUN_NOTEBOOK, str(notebook)],
                        cwd=root if launch_from == "root" else lesson,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
