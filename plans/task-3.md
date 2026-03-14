# Task 3 Plan: The System Agent

## Overview

This task extends the agent from Task 2 with a `query_api` tool to interact with the deployed backend. The agent will answer two types of questions:
1. **Static system facts** - framework, ports, status codes (via `read_file` on source code)
2. **Data-dependent queries** - item counts, scores, analytics (via `query_api`)

## Tool Definitions

### 1. `query_api` Tool

**Purpose:** Send HTTP requests to the backend LMS API.

**Schema:**
```json
{
  "name": "query_api",
  "description": "Query the backend LMS API. Use for data-dependent questions like 'how many items', 'what is the completion rate', etc.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE)"
      },
      "path": {
        "type": "string",
        "description": "API path, e.g., '/items/', '/analytics/completion-rate'"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

**Implementation:**
- Read `LMS_API_KEY` from `.env.docker.secret` for authentication
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Use `httpx` to make the request
- Return JSON: `{"status_code": 200, "body": {...}}`

### 2. `read_file` Tool

**Purpose:** Read file contents from the project (wiki, source code, config files).

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project. Use for questions about source code, configuration, or documentation.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the file, e.g., 'wiki/backend.md', 'backend/app/main.py'"
      }
    },
    "required": ["path"]
  }
}
```

### 3. `list_files` Tool

**Purpose:** List files in a directory.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files in a directory. Use to discover API routers, find files, or explore the project structure.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the directory, e.g., 'backend/app/routers/', 'wiki/'"
      }
    },
    "required": ["path"]
  }
}
```

## System Prompt

The system prompt will guide the LLM to:
1. Choose the right tool based on question type
2. Use `query_api` for runtime data (database contents, API responses)
3. Use `read_file` for static facts (framework, configuration, source code)
4. Use `list_files` to discover project structure

**Draft:**
```
You are an intelligent assistant that answers questions about this software project.

You have access to these tools:
- read_file: Read a file from the project (wiki, source code, config)
- list_files: List files in a directory
- query_api: Query the running backend API for live data

Tool selection guide:
- For questions about live data (database contents, API responses, current state) → use query_api
- For questions about source code, framework, configuration → use read_file
- For questions about project structure or finding files → use list_files
- For questions about wiki documentation → use read_file on wiki/ files

Always explain your reasoning before calling a tool. After getting results, provide a clear answer.
```

## Configuration

The agent will read these environment variables:

| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint |
| `LLM_MODEL` | `.env.agent.secret` | Model to use |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication |
| `AGENT_API_BASE_URL` | env or default | Backend API base URL (default: `http://localhost:42002`) |

**Important:** The autochecker injects its own values. Never hardcode credentials.

## Agentic Loop

For Task 3, the loop is simple:
1. Parse user question
2. Ask LLM (with tools schema) for a response
3. If LLM calls a tool, execute it and return the result
4. Ask LLM again with the tool result
5. Return final answer

For Task 3, we can do a single iteration:
- If the LLM calls a tool, execute it and include the result in the answer
- Multi-step reasoning (Task 4+) will require a full loop

## Benchmark Questions Analysis

| # | Question | Tool(s) | Expected Answer |
|---|----------|---------|-----------------|
| 0 | Wiki: protect a branch | `read_file` | `branch`, `protect` |
| 1 | Wiki: SSH connection | `read_file` | `ssh` / `key` / `connect` |
| 2 | Web framework | `read_file` | `FastAPI` |
| 3 | API router modules | `list_files` | `items`, `interactions`, `analytics`, `pipeline` |
| 4 | Items in database | `query_api` | number > 0 |
| 5 | Status code without auth | `query_api` | `401` / `403` |
| 6 | /analytics/completion-rate error | `query_api`, `read_file` | `ZeroDivisionError` |
| 7 | /analytics/top-learners crash | `query_api`, `read_file` | `TypeError` / `None` |
| 8 | Request lifecycle | `read_file` | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency | `read_file` | `external_id` check, duplicates skipped |

## Implementation Steps

1. **Update `load_config()`** to read `LMS_API_KEY` and `AGENT_API_BASE_URL`
2. **Implement `query_api()`** function with authentication
3. **Implement `read_file()`** and `list_files()` functions
4. **Update `call_llm()`** to use function-calling schema
5. **Update system prompt** to guide tool selection
6. **Test manually** with sample questions
7. **Run `run_eval.py`** and iterate
8. **Document in `AGENT.md`**
9. **Add regression tests**

## Initial Score & Iteration Strategy

**Initial run:** Will run `uv run run_eval.py` after implementation.

**Iteration approach:**
1. Run eval, note first failure
2. Check which tool was (not) called
3. Fix tool description or implementation
4. Re-run until all pass

**Common issues to watch for:**
- LLM doesn't call tool → improve tool description
- Tool returns error → fix implementation
- Wrong arguments → clarify parameter descriptions
- Answer doesn't match keywords → adjust phrasing in system prompt

## Benchmark Results

**Final Score: 10/10 PASSED**

### Iterations Summary

1. **First run**: Agent hit max iterations (5) on question 1. Fixed by increasing max_iterations to 20.

2. **Second run (3/10)**: Questions 4-10 failed. Issues:
   - Q4: LLM read each router file individually instead of answering from list_files
   - Q6: Agent always sent auth header, couldn't test "without authentication"
   - Q9-10: LLM didn't provide detailed enough answers for reasoning questions

3. **Fixes applied:**
   - Added `skip_auth` parameter to `query_api` for Q5 (status code without auth)
   - Updated system prompt: "For 'list all X' questions: use list_files ONCE, then answer from file names"
   - Added guidance: "Configuration files like Dockerfile are in the project root"
   - Reduced temperature from 0.3 to 0.01 for more deterministic behavior
   - Added source tracking for eval compatibility

4. **Third run (8/10)**: Questions 8-9 (request lifecycle, ETL) failed. Issues:
   - LLM was reading wrong files for architecture questions
   - LLM output thinking statements ("Let me check...") as final answer

5. **Fixes applied:**
   - Added explicit file paths for architecture questions: "MUST read: docker-compose.yml, caddy/Caddyfile, Dockerfile, backend/app/main.py"
   - Added explicit rules: "NEVER output thinking statements like 'Let me check...', 'I need to...'"
   - Added "IMPORTANT: Always use tools to find answers. Do NOT answer from your own knowledge"

6. **Fourth run (6/10)**: Non-deterministic failures on bug diagnosis questions. The LLM sometimes answered without reading source code.

7. **Final fixes:**
   - Strengthened tool usage requirement in system prompt
   - Ran eval multiple times to verify consistency

8. **Final run (10/10)**: All questions passed consistently.

### Key Learnings

1. **Low temperature is critical**: `temperature=0.01` made tool calling consistent. Higher values caused random behavior.

2. **Explicit instructions matter**: The LLM needed explicit guidance to:
   - Not read every file when listing routers
   - Read specific files for architecture questions
   - Never output thinking statements

3. **Source field requirement**: The eval checks for a `source` string field. Had to track which files were read.

4. **Multi-step reasoning works**: With 20 iterations, the agent can trace request lifecycle through multiple files.

5. **Non-determinism**: Even with temperature=0.01, the LLM can behave differently between runs. Running the eval multiple times helps identify flaky behavior.

6. **Forcing tool usage**: The LLM sometimes answers from its own knowledge. Adding explicit rules to use tools fixed this.
