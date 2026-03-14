# Agent Documentation

## Overview

This agent is a CLI tool that answers questions by calling a Large Language Model (LLM) with **tool-calling capabilities**. The agent can use tools (`read_file`, `list_files`, `query_api`) to navigate the project wiki, read source code, and query the live backend API.

## Architecture

### Task 1 Architecture (Basic LLM Call)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──► │  agent.py   │ ──► │  LLM API    │ ──► │  JSON Out   │
│  (question) │     │  (parser)   │     │  (Qwen)     │     │  (stdout)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Task 2+3 Architecture (Agentic Loop with Tools)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Question  │ ──► │  agent.py   │ ──► │  LLM API    │
└─────────────┘     │  (loop)     │ ◄── │  (tools)    │
                    │             │ ──► │             │
                    │  ┌─────────┐│     └─────────────┘
                    │  │ Tools   ││──────────┘
                    │  │ - read  ││
                    │  │ - list  ││
                    │  │ - query ││
                    │  └─────────┘│
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  JSON Out   │
                    │  + tool_    │
                    │  calls log  │
                    └─────────────┘
```

## Components

### 1. Configuration Loader (`load_config`)

- Reads LLM environment variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
- Reads LMS environment variables: `LMS_API_KEY`, `AGENT_API_BASE_URL`
- First checks system environment variables (for injection by autochecker/tests)
- Falls back to `.env.agent.secret` and `.env.docker.secret` files if env vars not set
- Validates that all required variables are present
- Exits with error code 1 if any required variable is missing

### 2. Tools

The agent has three tools that the LLM can call:

#### `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required) - Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message if inaccessible.

**Security:** Validates path does not escape project root using `../` traversal.

#### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required) - Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries, or error message.

**Security:** Validates path does not escape project root.

#### `query_api` (Task 3)

**Purpose:** Call the deployed backend API to query live data or check system behavior.

**Parameters:**
- `method` (string, required) - HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string, required) - API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) - JSON request body for POST/PUT/PATCH requests

**Returns:** JSON string with `status_code` and `body`, or error message.

**Authentication:** Uses `LMS_API_KEY` from environment variables in `Authorization: Bearer <token>` header.

### 3. Path Security (`validate_path`)

**Threat Model:** Prevent the LLM from being tricked into accessing files outside the project directory.

**Implementation:**
1. Resolve the full absolute path using `Path.resolve()`
2. Check that resolved path starts with `PROJECT_ROOT`
3. Raise `SecurityError` if path escapes boundary

**Example:**
```python
# Valid: wiki/git-workflow.md → /project/wiki/git-workflow.md
# Rejected: ../../etc/passwd → /etc/passwd (outside project)
```

### 4. Agentic Loop (`run_agentic_loop`)

The agentic loop enables multi-step reasoning:

**Loop Structure:**
```
1. Build messages: [system prompt, user question]
2. Call LLM with all tool schemas
3. Parse response:
   - If tool_calls: execute tools, append results, go to step 2
   - If text answer: extract answer + source, output JSON, exit
4. Max 10 iterations (prevent infinite loops)
```

**Message Flow:**
```python
# Initial request
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question}
]

# After LLM returns tool_calls
messages.append(assistant_message_with_tool_calls)

# Execute tool, get result
result = execute_tool(tool_name, args, config)

# Append tool result
messages.append({
    "role": "tool",
    "tool_call_id": tool_call_id,
    "content": result
})

# Loop back to LLM
```

**Termination Conditions:**
1. LLM returns no tool calls → Final answer, exit
2. 10 tool calls reached → Stop, return partial results
3. Error in execution → Report to LLM, continue loop

### 5. System Prompt Strategy

The system prompt guides the LLM to use tools effectively:

**Tool Selection Guidance:**

| Use Case | Tools |
|----------|-------|
| Documentation questions | `list_files` + `read_file` in `wiki/` |
| Source code questions | `list_files` + `read_file` in `backend/`, `frontend/` |
| Configuration questions | `read_file` for `docker-compose.yml`, `Dockerfile` |
| Live data queries | `query_api` (e.g., "how many items") |
| HTTP status codes | `query_api` (e.g., "what status when unauthorized") |
| Bug diagnosis | `query_api` to reproduce, then `read_file` to examine |

**Section Anchor Format:**
- Convert header to lowercase
- Replace spaces with hyphens
- Remove special characters
- Example: `## Resolving Merge Conflicts` → `#resolving-merge-conflicts`

### 6. Output Formatter (`main`)

- Validates command-line arguments
- Runs the agentic loop
- Outputs JSON to stdout:
  ```json
  {
    "answer": "...",
    "source": "wiki/filename.md#section-anchor",  // Optional
    "tool_calls": [
      {"tool": "read_file", "args": {"path": "..."}, "result": "..."}
    ]
  }
  ```
- Sends all debug/logging output to stderr

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API endpoint
- Strong tool-calling capabilities

## Configuration

The agent reads all configuration from **environment variables**:

### LLM Configuration (`.env.agent.secret`)

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | API key for LLM authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model identifier to use |

### LMS Configuration (`.env.docker.secret`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `LMS_API_KEY` | Backend API key for `query_api` auth | - |
| `AGENT_API_BASE_URL` | Base URL for backend API | `http://localhost:42002` |

**Priority:** System environment variables take precedence over `.env.*.secret` files.

For local development:
```bash
cp .env.agent.example .env.agent.secret
cp .env.docker.example .env.docker.secret
```

## Usage

### Basic Usage

```bash
# Documentation question (uses read_file)
uv run agent.py "How do you resolve a merge conflict?"

# Source code question (uses read_file)
uv run agent.py "What framework does the backend use?"

# Live data question (uses query_api)
uv run agent.py "How many items are in the database?"

# HTTP status question (uses query_api)
uv run agent.py "What status code when requesting /items/ without auth?"
```

### Example Output

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, \"body\": \"[...]"}
  ]
}
```

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki/source reference (optional for API queries) |
| `tool_calls` | array | Log of all tool calls made during execution |

Each tool call entry has:
- `tool` - Tool name (`read_file`, `list_files`, or `query_api`)
- `args` - Arguments passed to the tool
- `result` - Tool output

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing environment variable | Error to stderr, exit 1 |
| Path traversal attempt | Returns error to LLM, continues loop |
| File not found | Returns error message to LLM |
| API authentication failure | Returns 401/403 status to LLM |
| HTTP error (4xx/5xx) | Returns status code and body to LLM |
| Connection failure | Error to stderr, exit 1 |
| Max tool calls reached | Returns partial results with warning |

## Dependencies

- `httpx` - HTTP client for API calls and LLM requests
- `python-dotenv` - Environment variable loading

## Testing

### Manual Testing

```bash
# Test read_file tool
uv run agent.py "How do you resolve a merge conflict?"

# Test list_files tool
uv run agent.py "What files are in the wiki directory?"

# Test query_api tool
uv run agent.py "How many items are in the database?"
```

### Automated Tests

```bash
uv run pytest tests/test_task1.py  # Task 1 tests
uv run pytest tests/test_task2.py  # Task 2 tests
uv run pytest tests/test_task3.py  # Task 3 tests
```

### Benchmark

```bash
uv run run_eval.py
```

Runs 10 questions across all classes (wiki lookup, system facts, data queries, bug diagnosis, reasoning).

## Troubleshooting

**"Missing required environment variable"**
- Ensure `.env.agent.secret` and `.env.docker.secret` exist with all required variables

**"HTTP error: 401"**
- Your `LLM_API_KEY` or `LMS_API_KEY` is invalid

**"Request failed: Connection refused"**
- Qwen Code API not running on VM (for LLM)
- Backend not running (for query_api)

**"Access denied - Path traversal detected"**
- The agent blocked an attempt to read files outside the project
- This is expected security behavior

**LLM keeps calling tools without answering**
- May hit 10 tool call limit
- Check system prompt is guiding LLM to provide final answer

**"ZeroDivisionError" in analytics**
- This is a known bug in the backend when querying labs with no data
- The agent should diagnose this by reading the source code

## Lessons Learned (Task 3)

Building the system agent required several iterations:

1. **Tool descriptions matter**: Initially the LLM would use `read_file` for API questions. Adding clear guidance ("Do NOT use for documentation questions") to `query_api` helped.

2. **Authentication is critical**: The `query_api` tool needs `LMS_API_KEY` to authenticate. Reading from both `.env.agent.secret` (LLM) and `.env.docker.secret` (LMS) was necessary.

3. **Environment variable injection**: The autochecker injects its own credentials, so the agent must read from environment variables, not hardcoded values.

4. **Error handling in tools**: When `query_api` fails, returning the error to the LLM (not raising an exception) allows the agent to recover and try a different approach.

5. **System prompt tuning**: The prompt needs to explicitly tell the LLM when to use each tool. A decision table (documentation → read_file, live data → query_api) works well.

6. **Source field flexibility**: For API queries, there's no wiki source, so `source` is now optional (can be empty string).

## Final Eval Score

After implementing `query_api` and tuning the system prompt, the agent should pass all 10 local benchmark questions in `run_eval.py`. The autochecker will run additional hidden questions to verify robustness.
