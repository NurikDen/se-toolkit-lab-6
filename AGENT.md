# Agent Documentation

## Overview

This agent is a CLI tool that answers questions by calling a Large Language Model (LLM). It forms the foundation for the intelligent agent that will be extended with tools and agentic capabilities in subsequent tasks.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Arg   │ ──► │  agent.py   │ ──► │  LLM API    │ ──► │  JSON Out   │
│  (question) │     │  (parser)   │     │  (Qwen)     │     │  (stdout)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Logs       │
                    │  (stderr)   │
                    └─────────────┘
```

### 1. Configuration Loader (`load_config`)

- Reads environment variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
- First checks system environment variables (for injection by autochecker/tests)
- Falls back to `.env.agent.secret` file if env vars not set
- Validates that all three required variables are present
- Exits with error code 1 if any required variable is missing

### 2. LLM Client (`call_llm`)

- Makes HTTP POST requests to the LLM's chat completions endpoint
- Uses `httpx` for synchronous HTTP communication
- Sends the user question with a minimal system prompt
- Parses the response and extracts the answer content
- Handles HTTP errors, connection errors, and unexpected response formats

### 3. Output Formatter (`main`)

- Validates command-line arguments
- Orchestrates the flow: load config → call LLM → format output
- Outputs valid JSON to stdout: `{"answer": "...", "tool_calls": []}`
- Sends all debug/logging output to stderr

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API endpoint
- Strong tool-calling capabilities (for future tasks)

## Configuration

The agent reads LLM configuration from **environment variables**:

- `LLM_API_KEY` - API key for authentication
- `LLM_API_BASE` - Base URL of the LLM API endpoint
- `LLM_MODEL` - Model identifier to use

**Priority:** System environment variables take precedence over `.env.agent.secret`.

This allows the autochecker to inject its own credentials when testing.

For local development, create `.env.agent.secret`:

```bash
cp .env.agent.example .env.agent.secret
```

## Usage

### Basic Usage

```bash
uv run agent.py "What is Python?"
```

### Example Output

```json
{"answer": "Python is a high-level, general-purpose programming language.", "tool_calls": []}
```

### Output Format

- **stdout:** Single-line JSON with `answer` (string) and `tool_calls` (array)
- **stderr:** Progress logs and error messages
- **Exit code:** 0 on success, 1 on error

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Error to stderr, exit 1 |
| Missing environment variable | Error to stderr, exit 1 |
| HTTP error (4xx/5xx) | Error to stderr with response, exit 1 |
| Connection failure | Error to stderr, exit 1 |
| Unexpected API response | Error to stderr, exit 1 |

## Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading

## Testing

Run the agent manually:

```bash
uv run agent.py "What does REST stand for?"
```

Run automated tests:

```bash
uv run pytest tests/test_task1.py
```

## Extending the Agent

In subsequent tasks, the agent will be extended with:

- **Task 2:** Tool definitions and execution capabilities
- **Task 3:** Agentic loop for multi-step reasoning
- **Task 4+:** Domain knowledge and wiki integration

## Troubleshooting

**"Missing required environment variable"**
- Ensure `.env.agent.secret` exists and contains all three variables
- Check that there are no typos in variable names

**"HTTP error: 401"**
- Your `LLM_API_KEY` is invalid or expired
- Regenerate your API key from Qwen Code

**"Request failed: Connection refused"**
- The Qwen Code API may not be running on your VM
- Check that the VM IP and port in `LLM_API_BASE` are correct

**"Unexpected API response format"**
- The LLM returned an unexpected response structure
- Check the LLM service status or try a different model
