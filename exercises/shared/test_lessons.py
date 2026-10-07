"""Check that either notebook works without the web application installed."""

import pathlib
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from uuid import uuid4

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
        pass  # compiled only; a live model call needs credentials
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
