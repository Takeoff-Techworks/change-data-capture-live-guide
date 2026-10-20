# Lessons 4 and 5 Shared Scripts

`cdc_lessons` belongs to the exercises and has no dependency on the web app.
Each notebook creates its own seeded SQLite database; either lesson can run first.
Lesson 4 uses memory; Lesson 5 uses a temporary file shared with its MCP process.

From the repository root, install `pip install -r exercises/shared/requirements.txt`.
For Lesson 4, create `exercises/shared/.env` from the example here and set the
Gemini or OpenAI API key (see `.env.example`). The LangChain agent is required. Lesson 5 runs offline; its final agent cell is optional and uses a key only if one is set.

The notebooks load `shared/.env` with `override=True`, so values in that file
replace settings already present in the kernel. After changing providers, rerun
the agent cell to reload the file; it prints the selected provider and file path.

Lesson 5 uses the official MCP Python SDK (v1 API, pinned below v2). Its stdio
server exposes five read-only tools over a SQLite connection opened in read-only
mode. Source mutations happen in the notebook, outside the MCP tool boundary.
Each example initializes a client session and closes the server on exit, including
when an example fails. The final notebook cell removes the exercise database.

To move the exercises elsewhere, keep `04-cdc-for-ai`, `05-mcp`, and `shared`
as sibling folders. No app installation, app database, or web server is needed.
