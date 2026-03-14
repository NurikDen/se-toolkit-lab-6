# Agent Documentation

## Overview

This agent is a CLI tool that answers questions about the software project by calling a Large Language Model (LLM) with tool-calling capabilities. The agent can read files, list directories, and query the backend API to provide accurate answers based on both static source code and live system data.

## Architecture

### Task 1 Architecture (Basic LLM Call)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──► │  agent.py   │ ──► │  LLM API    │ ──► │ Tool Calls  │
│  (question) │     │ (agentic    │     │  (Qwen)     │     │ (read_file, │
└─────────────┘     │   loop)     │     └─────────────┘     │ list_files, │
                    └─────────────┘           │             │ query_api)  │
                           │                  │             └─────────────┘
                           │                  ▼                    │
                           │           ┌─────────────┐             │
                           │           │ Tool Result │ ◄───────────┘
                           │           └─────────────┘
                           │                  │
                           ▼                  ▼
                    ┌─────────────────────────────────┐
                    │  Final Answer + Tool Call Log   │
                    │  JSON to stdout                 │
                    └─────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  JSON Out   │
                    │  + tool_    │
                    │  calls log  │
                    └─────────────┘
```

### Agentic Loop

The agent uses an iterative loop to answer questions:

1. **Parse Question**: Receive the user's question from CLI arguments
2. **Call LLM**: Send the question to the LLM with a system prompt and tool schemas
3. **Check for Tool Calls**: If the LLM requests tool calls, execute them
4. **Add Results to History**: Append tool results to the conversation
5. **Repeat**: Call the LLM again with the updated conversation
6. **Return Answer**: When the LLM provides a final answer, output JSON and exit

The loop runs for up to 20 iterations to prevent infinite loops while allowing multi-step reasoning.

## Tools

### 1. `query_api`

**Purpose:** Query the backend LMS API for live data.

**Parameters:**
- `method` (required): HTTP method (GET, POST, PUT, DELETE)
- `path` (required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate?lab=lab-06`)
- `body` (optional): JSON request body for POST/PUT requests
- `skip_auth` (optional): If true, omit the Authorization header (useful for testing auth requirements)

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` via the `Authorization: Bearer <key>` header.

**Returns:** JSON object with `status_code` and `body` fields.

**Use cases:**
- "How many items are in the database?" → `GET /items/`
- "What status code without auth?" → `GET /items/` with `skip_auth=true`
- "What's the completion rate?" → `GET /analytics/completion-rate?lab=lab-06`

### 2. `read_file`

**Purpose:** Read a file from the project (wiki, source code, configuration).

**Parameters:**
- `path` (required): Relative path from project root (e.g., `wiki/backend.md`, `backend/app/main.py`)

**Returns:** JSON object with `content` and `path` fields, or `error` if file not found.

**Use cases:**
- "What framework does the backend use?" → Read `backend/app/main.py`
- "How to protect a branch?" → Read `wiki/github.md`
- "Explain the request lifecycle" → Read `docker-compose.yml`, `Dockerfile`

### 3. `list_files`

**Purpose:** List files in a directory.

**Parameters:**
- `path` (required): Relative path to directory (e.g., `backend/app/routers/`, `wiki/`)

**Returns:** JSON object with `files` (sorted list) and `path` fields.

**Use cases:**
- "List all API routers" → `list_files backend/app/routers/`
- "What wiki files exist?" → `list_files wiki/`

## System Prompt

The system prompt guides the LLM's tool selection:

```
Tool selection guide:
- For LIVE DATA (database, API responses) → use query_api
- For SOURCE CODE (framework, configuration) → use read_file
- For PROJECT STRUCTURE (what files exist) → use list_files
- For WIKI DOCUMENTATION → use read_file on wiki/ files

Important:
- For "list all X" questions: use list_files ONCE, then answer from file names
- Don't re-read the same file if truncated
- Configuration files (Dockerfile, docker-compose.yml) are in project root
```

## Configuration

The agent reads all configuration from environment variables:

| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint URL |
| `LLM_MODEL` | `.env.agent.secret` | Model identifier |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication |
| `AGENT_API_BASE_URL` | env or default | Backend API base URL (default: `http://localhost:42002`) |

**Priority:** System environment variables take precedence over `.env.*` files. This allows the autochecker to inject its own credentials.

## Output Format

**stdout:** Single-line JSON:
```json
{
  "answer": "The backend uses FastAPI...",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "backend/app/main.py"},
      "result": "{\"content\": \"...\", \"path\": \"backend/app/main.py\"}"
    }
  ],
  "source": "backend/app/main.py"
}
```

**stderr:** Progress logs and debug information.

**Exit code:** 0 on success, 1 on error.

## Benchmark Results

The agent passes all 10 local evaluation questions:

| # | Question | Tools Used | Status |
|---|----------|------------|--------|
| 0 | Wiki: protect a branch | `read_file` | ✓ |
| 1 | Wiki: SSH connection | `read_file` | ✓ |
| 2 | Web framework | `read_file` | ✓ |
| 3 | API router modules | `list_files` | ✓ |
| 4 | Items in database | `query_api` | ✓ |
| 5 | Status code without auth | `query_api` (skip_auth) | ✓ |
| 6 | /analytics/completion-rate error | `query_api`, `read_file` | ✓ |
| 7 | /analytics/top-learners crash | `query_api`, `read_file` | ✓ |
| 8 | Request lifecycle | `read_file` | ✓ |
| 9 | ETL idempotency | `read_file` | ✓ |

## Lessons Learned

### Tool Design

1. **Clear descriptions matter**: Initially, the LLM would read every router file individually for "list all routers" questions. Adding explicit guidance ("use list_files ONCE, then answer from file names") fixed this.

2. **Low temperature for determinism**: Setting `temperature=0.01` makes tool calling more consistent. Higher temperatures caused the LLM to sometimes skip steps or loop.

3. **Source tracking**: The eval checks for a `source` field. Tracking which files were read and including the first one in the output was necessary for passing.

4. **Forcing tool usage**: The LLM sometimes answers from its own knowledge instead of using tools. Adding "IMPORTANT: Always use tools to find answers. Do NOT answer from your own knowledge" to the system prompt fixed this.

### Agentic Loop

1. **Iteration limits**: Started with 5 iterations, increased to 20 for complex multi-step questions (like tracing request lifecycle through multiple files).

2. **Message history**: Keeping the full conversation history (including tool results) is essential for multi-turn reasoning.

3. **Error handling**: Gracefully handling file-not-found and API errors prevents crashes and lets the LLM adapt.

### Answer Quality

1. **No thinking statements**: The LLM would output partial thoughts like "Let me check..." as the final answer. Adding explicit rules ("NEVER output thinking statements like 'Let me check...', 'I need to...'") fixed this.

2. **Specific file paths for architecture questions**: For the request lifecycle question, explicitly listing the files to read (docker-compose.yml, caddy/Caddyfile, Dockerfile, backend/app/main.py) in the system prompt ensured the LLM reads the right files.

3. **Non-determinism**: Even with temperature=0.01, the LLM can behave differently between runs. Running the eval multiple times helps identify flaky behavior.

### Authentication

1. **Two keys**: `LMS_API_KEY` (backend) and `LLM_API_KEY` (LLM provider) serve different purposes. Mixing them up causes confusing failures.

2. **Skip auth for testing**: The `skip_auth` parameter was necessary for question 5, which asks what happens without authentication.

### Iteration Summary

The development went through several iterations:

1. **First run**: Agent hit max iterations on early questions. Fixed by increasing max_iterations to 20.

2. **Second run**: Questions about architecture (request lifecycle) failed because the LLM was reading wrong files. Fixed by adding explicit file paths to the system prompt.

3. **Third run**: Questions about bugs failed because the LLM wasn't reading source code. Fixed by improving tool descriptions.

4. **Fourth run**: Final answers contained thinking statements. Fixed by adding explicit rules against outputting partial thoughts.

5. **Final run**: All 10/10 questions passed consistently.

## Future Improvements

1. **Parallel tool calls**: Currently, tool calls are executed sequentially. Parallel execution would speed up multi-file analysis.

2. **Content summarization**: For large files, summarizing content instead of truncating might help the LLM find relevant sections.

3. **Caching**: Caching file contents and API responses would reduce redundant calls in multi-turn conversations.

## Troubleshooting

**"Missing LMS_API_KEY"**: Ensure `.env.docker.secret` exists with `LMS_API_KEY=my-secret-api-key`.

**Agent times out**: Check that the LLM API (`LLM_API_BASE`) is accessible. The qwen-code-oai-proxy container must be running.

**401 on API calls**: Verify `LMS_API_KEY` matches the backend's expected key.

**LLM doesn't call tools**: The system prompt might need adjustment. Check that tool descriptions are clear.

**Wrong tool called**: Improve the tool selection guide in the system prompt with more specific examples.
