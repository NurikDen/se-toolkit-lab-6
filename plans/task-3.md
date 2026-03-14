# Task 3 Plan: The System Agent

## Overview

This task extends the Task 2 agent with a `query_api` tool that can query the deployed backend API. The agent will answer two new kinds of questions:
1. **Static system facts** - framework, ports, status codes
2. **Data-dependent queries** - item count, scores, analytics

## Tool Schema: `query_api`

### Definition

```json
{
  "name": "query_api",
  "description": "Call the deployed backend API. Use this to query live data or check system behavior.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, etc.)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
      },
      "path": {
        "type": "string",
        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
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

### Implementation

```python
def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    """
    Call the deployed backend API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        body: Optional JSON request body
    
    Returns:
        JSON string with status_code and body, or error message
    """
```

## Authentication

### LMS_API_KEY

- Read from environment variable `LMS_API_KEY`
- Loaded from `.env.docker.secret` for local development
- Autochecker will inject its own value during evaluation
- Used in `Authorization: Bearer <LMS_API_KEY>` header

### Configuration Priority

Environment variables take precedence over `.env.docker.secret` file:
1. Check `os.getenv("LMS_API_KEY")` first
2. Fall back to loading from `.env.docker.secret`

## Environment Variables

| Variable | Purpose | Default | Source |
|----------|---------|---------|--------|
| `LLM_API_KEY` | LLM provider authentication | - | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | - | `.env.agent.secret` |
| `LLM_MODEL` | Model identifier | - | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API authentication | - | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Backend API base URL | `http://localhost:42002` | `.env.docker.secret` or default |

## System Prompt Update

The system prompt needs to guide the LLM to choose the right tool:

**Decision logic:**
- **Wiki/documentation questions** → `list_files` + `read_file` in `wiki/`
- **Source code questions** → `list_files` + `read_file` in `backend/`, `frontend/`, etc.
- **Live data questions** → `query_api` (e.g., "how many items", "what status code")
- **System behavior questions** → `query_api` (e.g., "what framework", test endpoints)
- **Bug diagnosis** → `query_api` to reproduce error, then `read_file` to examine source

**Updated prompt strategy:**
```
You are a documentation and system assistant. You have three tools:

1. list_files - Discover what files exist in a directory
2. read_file - Read file contents (use for wiki docs and source code)
3. query_api - Call the live backend API (use for live data and system behavior)

When to use each tool:
- Use list_files/read_file for: documentation questions, code structure, configuration
- Use query_api for: database queries, HTTP status codes, live analytics, testing endpoints

For bug diagnosis:
1. First use query_api to reproduce the error
2. Note the error message and status code
3. Use read_file to examine the source code at the error location
```

## Agentic Loop

The loop structure remains the same as Task 2:
1. Send question + all tool schemas to LLM
2. If LLM returns tool_calls → execute tools, append results, loop
3. If LLM returns text answer → output JSON, exit
4. Max 10 tool calls

## Output Format

Same as Task 2, but `source` is now optional:

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",  // Optional - may be empty for system questions
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}
```

## Benchmark Strategy

### run_eval.py Questions

| # | Question Type | Expected Tool | Strategy |
|---|---------------|---------------|----------|
| 0-1 | Wiki lookup | `read_file` | Search wiki/ directory |
| 2-3 | Source code | `read_file`, `list_files` | Search backend/ directory |
| 4-7 | Live data/API | `query_api` | Call appropriate endpoints |
| 8-9 | Complex reasoning | `read_file` + reasoning | Read config files, explain |

### Iteration Process

1. Run `uv run run_eval.py`
2. Identify failing questions
3. Debug using the feedback table:
   - Wrong tool → improve tool descriptions
   - Wrong arguments → clarify parameter descriptions
   - Error in tool → fix implementation
   - Timeout → reduce iterations or optimize
4. Re-run until all 10 pass

## Implementation Steps

1. **Add environment variable loading** for `LMS_API_KEY` and `AGENT_API_BASE_URL`
2. **Implement `query_api` tool** with authentication
3. **Add tool schema** to TOOLS list
4. **Update system prompt** with tool selection guidance
5. **Run benchmark** with `run_eval.py`
6. **Debug and iterate** based on failures
7. **Update AGENT.md** with architecture and lessons learned
8. **Write 2 regression tests** for Task 3
9. **Commit and create PR**

## Testing Strategy

**Test 1: Source code question**
- Question: "What framework does the backend use?"
- Expected: `read_file` in tool_calls, answer contains "FastAPI"

**Test 2: API data question**
- Question: "How many items are in the database?"
- Expected: `query_api` in tool_calls, answer contains a number

## Potential Challenges

| Challenge | Mitigation |
|-----------|------------|
| LLM calls wrong tool | Improve tool descriptions in schema |
| API authentication fails | Verify LMS_API_KEY is loaded correctly |
| Agent loops infinitely | Ensure max 10 tool calls limit works |
| Answer format doesn't match keywords | Adjust system prompt for precise phrasing |
| LLM returns null content | Handle `content: null` in response parsing |

## Success Criteria

- All 10 `run_eval.py` questions pass
- `query_api` authenticates correctly with `LMS_API_KEY`
- Agent chooses appropriate tools for each question type
- 2 new regression tests pass
- Autochecker bot benchmark passes

## Implementation Status

### Completed

1. ✅ Created `plans/task-3.md` with implementation plan
2. ✅ Added `query_api` tool with authentication
3. ✅ Updated `load_config` to read `LMS_API_KEY` and `AGENT_API_BASE_URL`
4. ✅ Added `query_api` schema to TOOLS list
5. ✅ Updated system prompt with tool selection guidance
6. ✅ Updated `execute_tool` to pass config to `query_api`
7. ✅ Updated `AGENT.md` with Task 3 documentation
8. ✅ Created `tests/test_task3.py` with 3 regression tests

### Benchmark Results

**Initial run:** 0/10 passed

**Failure reason:** `Connection refused` - LLM API not reachable

The Qwen Code API needs to be running on the VM for the agent to work. Once the API is set up:

1. Run `uv run run_eval.py` to test all 10 questions
2. Debug failures using the feedback hints
3. Iterate until all questions pass

### Next Steps

1. Set up Qwen Code API on VM (see `wiki/qwen.md`)
2. Start backend services (`docker compose up`)
3. Run `run_eval.py` and fix any issues
4. Commit changes and create PR for Task 3
