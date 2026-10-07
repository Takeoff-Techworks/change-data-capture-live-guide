# Lessons 4 and 5 Shared Scripts

`cdc_lessons` belongs to the exercises and has no dependency on the web app.
Each notebook creates its own seeded SQLite database; either lesson can run first.
Lesson 4 uses memory; Lesson 5 uses a temporary file shared with its MCP process.

From the repository root, install `pip install -r exercises/shared/requirements.txt`.
For Lesson 4, create `exercises/shared/.env` from the example here and set the
Gemini or OpenAI API key (see `.env.example`). The LangChain agent is required. Lesson 5 runs offline; its final agent cell is optional and uses a key only if one is set.

Lesson 5 uses the official MCP Python SDK (v1 API, pinned below v2). Its stdio
server exposes five read-only tools over a SQLite connection opened in read-only
mode. Source mutations happen in the notebook, outside the MCP tool boundary.
Each example initializes a client session and closes the server on exit, including
when an example fails. The final notebook cell removes the exercise database.

To move the exercises elsewhere, keep `04-cdc-for-ai`, `05-mcp`, and `shared`
as sibling folders. No app installation, app database, or web server is needed.

## VS Code only offers MSSQL as a kernel

Lessons 4 and 5 use Python. In the Extensions view, install or update Microsoft's
**Python** (`ms-python.python`) and **Jupyter** (`ms-toolsai.jupyter`) extensions
in the environment where the notebook runs (the Codespace for Codespaces).
An old Jupyter extension can fail to activate after a VS Code update; if the
Jupyter output shows `onDidChangeNotebookCellExecutionState is not a function`,
update Jupyter before trying to select a kernel.

Run **Developer: Reload Window**, reopen the notebook, then choose
**Select Kernel > Select Another Kernel > Python Environments > .venv**.
If `.venv` is missing, run **Python: Select Interpreter > Enter interpreter path**
and choose `.venv/bin/python` (`.venv\Scripts\python.exe` on Windows).

To register a named kernel explicitly, run this from the repository root after
activating `.venv` and installing the shared requirements:

```bash
python -m ipykernel install --sys-prefix --name cdc-lessons --display-name "Python (CDC lessons)"
```

Then reload VS Code and look under **Select Another Kernel > Jupyter Kernels**.
See [VS Code's kernel selection guide](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management).

Run local checks with `python -m unittest discover -s exercises/shared`.
These execute both notebooks in isolated folders with app imports blocked,
including the LangChain retrieval tool and real MCP subprocess discovery, calls,
CDC updates, and denials. The live Gemini invocation is excluded.
