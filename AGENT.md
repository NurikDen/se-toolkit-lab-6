# Agent Documentation

## Overview

This agent is a CLI tool that answers questions by calling a Large Language Model (LLM) with **tool-calling capabilities**. The agent can use tools (`read_file`, `list_files`) to navigate the project wiki and find answers to documentation questions.

## Architecture

### Task 1 Architecture (Basic LLM Call)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──► │  agent.py   │ ──► │  LLM API    │ ──► │  JSON Out   │
│  (question) │     │  (parser)   │     │  (Qwen)     │     │  (stdout)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Task 2 Architecture (Agentic Loop with Tools)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Question  │ ──► │  agent.py   │ ──► │  LLM API    │
└─────────────┘     │  (loop)     │ ◄── │  (tools)    │
                    │             │ ──► │             │
                    │  ┌─────────┐│     └─────────────┘
                    │  │ Tools   ││──────────┘
                    │  │ - read  ││
                    │  │ - list  ││
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

- Reads environment variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
- First checks system environment variables (for injection by autochecker/tests)
- Falls back to `.env.agent.secret` file if env vars not set
- Validates that all three required variables are present
- Exits with error code 1 if any required variable is missing

### 2. Tools

The agent has two tools that the LLM can call:

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
2. Call LLM with tool schemas
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
result = execute_tool(tool_name, args)

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

**Key Instructions:**
1. Use `list_files` to discover wiki files (start with `wiki` directory)
2. Use `read_file` to examine specific files for answers
3. Identify the relevant section header
4. Create source reference in format: `wiki/filename.md#section-anchor`

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
    "source": "wiki/filename.md#section-anchor",
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

The agent reads LLM configuration from **environment variables**:

- `LLM_API_KEY` - API key for authentication
- `LLM_API_BASE` - Base URL of the LLM API endpoint
- `LLM_MODEL` - Model identifier to use

**Priority:** System environment variables take precedence over `.env.agent.secret`.

For local development, create `.env.agent.secret`:

```bash
cp .env.agent.example .env.agent.secret
```

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Example Output

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki reference in format `wiki/file.md#anchor` |
| `tool_calls` | array | Log of all tool calls made during execution |

Each tool call entry has:
- `tool` - Tool name (`read_file` or `list_files`)
- `args` - Arguments passed to the tool
- `result` - Tool output (truncated if large)

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing environment variable | Error to stderr, exit 1 |
| Path traversal attempt | Returns error to LLM, continues loop |
| File not found | Returns error message to LLM |
| HTTP error (4xx/5xx) | Error to stderr, exit 1 |
| Connection failure | Error to stderr, exit 1 |
| Max tool calls reached | Returns partial results with warning |

## Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading

## Testing

### Manual Testing

```bash
# Test read_file tool
uv run agent.py "How do you resolve a merge conflict?"

# Test list_files tool
uv run agent.py "What files are in the wiki directory?"
```

### Automated Tests

```bash
uv run pytest tests/test_task1.py  # Task 1 tests
uv run pytest tests/test_task2.py  # Task 2 tests
```

## Troubleshooting

**"Missing required environment variable"**
- Ensure `.env.agent.secret` exists with `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

**"HTTP error: 401"**
- Your `LLM_API_KEY` is invalid or expired

**"Request failed: Connection refused"**
- Qwen Code API not running on VM
- Check VM IP and port in `LLM_API_BASE`

**"Access denied - Path traversal detected"**
- The agent blocked an attempt to read files outside the project
- This is expected security behavior

**LLM keeps calling tools without answering**
- May hit 10 tool call limit
- Check system prompt is guiding LLM to provide final answer

**Source reference is `wiki/unknown.md`**
- No wiki files were read during the loop
- LLM may not have found relevant information
