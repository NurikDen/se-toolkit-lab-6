# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

**Provider:** Qwen Code API (self-hosted on VM)

**Rationale:**
- Recommended by the task description
- 1000 free requests per day (sufficient for development and testing)
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API endpoint

**Model:** `qwen3-coder-plus`
- Strong tool-calling capabilities (needed for Tasks 2-3)
- Default model in `.env.agent.example`
- Good balance of performance and speed

## Environment Configuration

The agent will read configuration from `.env.agent.secret`:

| Variable | Purpose | Example |
|----------|---------|---------|
| `LLM_API_KEY` | Authenticates with Qwen Code API | API key from Qwen Code setup |
| `LLM_API_BASE` | Base URL for the API endpoint | `http://10.93.24.193:<port>/v1` |
| `LLM_MODEL` | Model identifier | `qwen3-coder-plus` |

## Agent Structure

### Input/Output Flow

```
CLI argument (question) → agent.py → LLM API → JSON response → stdout
                                              ↓
                                         stderr (logs)
```

### Components

1. **Environment Loading**
   - Use `python-dotenv` to load `.env.agent.secret`
   - Validate that all required variables are present

2. **LLM Client**
   - Use `openai` Python package (compatible with Qwen Code API)
   - Call `chat.completions.create()` with the user question
   - System prompt: minimal, focused on JSON output format

3. **Response Parsing**
   - Extract the LLM's answer from the completion
   - Format as required JSON: `{"answer": "...", "tool_calls": []}`
   - `tool_calls` is empty array (tools added in Task 2)

4. **Output Handling**
   - Valid JSON to stdout (single line)
   - All debug/progress logs to stderr using `print(..., file=sys.stderr)`
   - Exit code 0 on success

### Error Handling

- Missing environment variables → error message to stderr, exit code 1
- API connection failure → error message to stderr, exit code 1
- Invalid JSON from LLM → error message to stderr, exit code 1
- Timeout (>60 seconds) → let the subprocess timeout handle it

## Testing Strategy

**Test file:** `tests/test_task1.py`

Single regression test that:
1. Runs `agent.py "What is Python?"` as subprocess
2. Parses stdout as JSON
3. Asserts `answer` field exists and is non-empty string
4. Asserts `tool_calls` field exists and is a list

## Implementation Order

1. Create `.env.agent.secret` from example
2. Create `agent.py` with basic LLM call
3. Test manually with `uv run agent.py "..."`
4. Create regression test
5. Create `AGENT.md` documentation
6. Run full test suite
7. Git workflow: issue, branch, PR
