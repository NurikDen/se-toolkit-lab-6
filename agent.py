#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools to answer questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    Logs to stderr
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Project root for path security validation
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# System prompt for the system agent
SYSTEM_PROMPT = """You are a documentation and system assistant for a software engineering lab.
You have access to three tools:

1. list_files - List files and directories in a given path. Use this to discover what files exist.
2. read_file - Read the contents of a file. Use this to examine file contents for answers.
3. query_api - Call the live backend API. Use this to query live data or check system behavior.

When to use each tool:

**Use list_files and read_file for:**
- Documentation questions (files in wiki/ directory)
- Source code questions (files in backend/, frontend/, etc.)
- Configuration files (docker-compose.yml, Dockerfile, etc.)

**Use query_api for:**
- Live data queries (e.g., "how many items", "what is the completion rate")
- HTTP status code questions (e.g., "what status code when unauthorized")
- Testing API endpoints to see behavior
- Analytics queries

**For bug diagnosis:**
1. First use query_api to reproduce the error and get the error message
2. Note the error type and status code
3. Use read_file to examine the source code at the error location
4. Explain what went wrong based on the code

When answering:
- Be concise and accurate
- Cite sources when reading from files (format: path/to/file.md#section-anchor)
- For API queries, include the status code and relevant data in your answer
- If you cannot find the answer, say so honestly
"""


def load_config() -> dict[str, str]:
    """Load configuration from environment variables or .env files."""
    # Load LLM config from .env.agent.secret
    llm_env_path = Path(__file__).parent / ".env.agent.secret"
    load_dotenv(llm_env_path)
    
    # Load LMS config from .env.docker.secret
    lms_env_path = Path(__file__).parent / ".env.docker.secret"
    load_dotenv(lms_env_path, override=False)

    # LLM configuration (required)
    required_llm_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config = {}

    for var in required_llm_vars:
        value = os.getenv(var)
        if not value:
            print(f"Error: Missing required environment variable: {var}", file=sys.stderr)
            print(f"Please ensure {llm_env_path} is properly configured.", file=sys.stderr)
            sys.exit(1)
        config[var] = value

    # LMS API configuration (required for query_api)
    lms_api_key = os.getenv("LMS_API_KEY")
    if not lms_api_key:
        print(f"Error: Missing required environment variable: LMS_API_KEY", file=sys.stderr)
        print(f"Please ensure {lms_env_path} is properly configured.", file=sys.stderr)
        sys.exit(1)
    config["LMS_API_KEY"] = lms_api_key

    # Agent API base URL (optional, defaults to localhost)
    config["AGENT_API_BASE_URL"] = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

    return config


def validate_path(relative_path: str) -> Path:
    """
    Validate and resolve a relative path, ensuring it stays within project root.
    
    Raises SecurityError if path escapes project boundary.
    """
    # Resolve to absolute path
    full_path = (PROJECT_ROOT / relative_path).resolve()
    
    # Check it's within project root
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise SecurityError(f"Path traversal detected: {relative_path}")
    
    return full_path


class SecurityError(Exception):
    """Raised when a path security violation is detected."""
    pass


def read_file(path: str) -> str:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root (e.g., 'wiki/git-workflow.md')
    
    Returns:
        File contents as string, or error message if file doesn't exist or is inaccessible.
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.is_file():
            return f"Error: File not found: {path}"
        
        content = validated_path.read_text()
        print(f"  [read_file] Read {path} ({len(content)} bytes)", file=sys.stderr)
        return content
        
    except SecurityError as e:
        return f"Error: Access denied - {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root (e.g., 'wiki')
    
    Returns:
        Newline-separated listing of entries, or error message.
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.is_dir():
            return f"Error: Directory not found: {path}"
        
        entries = sorted([e.name for e in validated_path.iterdir()])
        result = "\n".join(entries)
        print(f"  [list_files] Listed {path} ({len(entries)} entries)", file=sys.stderr)
        return result
        
    except SecurityError as e:
        return f"Error: Access denied - {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: str | None = None, config: dict | None = None) -> str:
    """
    Call the deployed backend API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT requests
        config: Configuration dict with LMS_API_KEY and AGENT_API_BASE_URL
    
    Returns:
        JSON string with status_code and body, or error message
    """
    if config is None:
        config = {}
    
    api_key = config.get("LMS_API_KEY", "")
    base_url = config.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    # Validate method
    valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    if method.upper() not in valid_methods:
        return f"Error: Invalid HTTP method '{method}'. Valid methods: {', '.join(valid_methods)}"
    
    # Build URL
    endpoint = f"{base_url.rstrip('/')}{path}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    print(f"  [query_api] {method} {endpoint}", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            # Prepare request body if provided
            kwargs: dict[str, Any] = {"headers": headers}
            if body and method.upper() in ["POST", "PUT", "PATCH"]:
                kwargs["content"] = body
            
            response = client.request(method.upper(), endpoint, **kwargs)
            
            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            
            result_str = json.dumps(result)
            print(f"  [query_api] Status: {response.status_code}", file=sys.stderr)
            return result_str
            
    except httpx.HTTPStatusError as e:
        result = {
            "status_code": e.response.status_code,
            "body": e.response.text,
        }
        return json.dumps(result)
    except httpx.RequestError as e:
        return f"Error: Request failed - {e}"
    except Exception as e:
        return f"Error: API call failed - {e}"


# Global config reference for tools (set in run_agentic_loop)
_tool_config: dict[str, str] = {}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to examine file contents for answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a directory. Use this to discover what files exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the live backend API. Use this to query live data, check HTTP status codes, or test API endpoints. Do NOT use for documentation questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT/PATCH requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


def execute_tool(tool_name: str, args: dict[str, Any], config: dict | None = None) -> str:
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool
        config: Configuration dict (passed to query_api for auth)

    Returns:
        Tool result as string
    """
    if tool_name not in TOOL_FUNCTIONS:
        return f"Error: Unknown tool: {tool_name}"

    func = TOOL_FUNCTIONS[tool_name]

    # query_api needs config for authentication
    if tool_name == "query_api":
        method = args.get("method", "")
        path = args.get("path", "")
        body = args.get("body")
        if not method or not path:
            return "Error: Missing required arguments 'method' and/or 'path'"
        return func(method, path, body, config)
    
    # read_file and list_files need path argument
    path = args.get("path", "")
    if not path:
        return "Error: Missing required argument 'path'"

    return func(path)


def call_llm_with_tools(
    messages: list[dict[str, Any]],
    config: dict[str, str]
) -> dict[str, Any]:
    """
    Call the LLM API with tool support.
    
    Args:
        messages: List of message dicts for the conversation
        config: LLM configuration
    
    Returns:
        Parsed response dict with 'content' and optionally 'tool_calls'
    """
    api_key = config["LLM_API_KEY"]
    api_base = config["LLM_API_BASE"]
    model = config["LLM_MODEL"]

    endpoint = f"{api_base.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]["message"]
            result = {
                "content": choice.get("content", ""),
            }
            
            # Parse tool calls if present
            if "tool_calls" in choice and choice["tool_calls"]:
                result["tool_calls"] = choice["tool_calls"]
            
            return result

    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError) as e:
        print(f"Unexpected API response format: {e}", file=sys.stderr)
        sys.exit(1)


def extract_source_from_answer(answer: str, file_contents: dict[str, str]) -> str:
    """
    Extract a source reference from the answer based on files that were read.
    
    Args:
        answer: The LLM's answer text
        file_contents: Dict mapping file paths to their contents
    
    Returns:
        Source reference in format wiki/filename.md#section-anchor
    """
    # Try to find the most relevant file and section
    for file_path, content in file_contents.items():
        if not file_path.startswith("wiki/"):
            continue
            
        # Look for section headers in the content
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#"):
                # Extract header text
                header_text = line.lstrip("#").strip()
                # Create anchor
                anchor = header_text.lower().replace(" ", "-").replace(".", "")
                anchor = re.sub(r"[^a-z0-9-]", "", anchor)
                
                # Check if this section seems relevant (simple heuristic)
                if len(file_contents) == 1:  # If only one file was read, use it
                    return f"{file_path}#{anchor}"
    
    # Default: return first wiki file
    for file_path in file_contents.keys():
        if file_path.startswith("wiki/"):
            return file_path
    
    return "wiki/unknown.md"


def run_agentic_loop(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Run the agentic loop: call LLM, execute tools, repeat until answer.
    
    Args:
        question: User's question
        config: LLM configuration
    
    Returns:
        Result dict with answer, source, and tool_calls
    """
    # Initialize conversation
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    # Track all tool calls for output
    all_tool_calls = []
    # Track files that were read (for source extraction)
    files_read: dict[str, str] = {}
    
    tool_call_count = 0
    
    while tool_call_count < MAX_TOOL_CALLS:
        print(f"\n[Loop iteration {tool_call_count + 1}]", file=sys.stderr)
        
        # Call LLM
        print("Calling LLM...", file=sys.stderr)
        response = call_llm_with_tools(messages, config)
        
        # Check if LLM returned tool calls
        if "tool_calls" in response:
            tool_calls = response["tool_calls"]
            
            # Add assistant message with tool calls to conversation
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": tool_calls,
            })
            
            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                
                print(f"Executing tool: {tool_name}({args})", file=sys.stderr)

                # Execute tool (pass config for query_api authentication)
                result = execute_tool(tool_name, args, config)
                
                # Record tool call for output
                all_tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                })
                
                # Track files read
                if tool_name == "read_file" and not result.startswith("Error"):
                    files_read[args.get("path", "")] = result
                
                # Append tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "unknown"),
                    "content": result,
                })
            
            tool_call_count += len(tool_calls)
            
        else:
            # LLM returned final answer (no tool calls)
            print("LLM returned final answer", file=sys.stderr)
            final_answer = response.get("content", "No answer provided.")
            
            # Extract source
            source = extract_source_from_answer(final_answer, files_read)
            
            # If no files were read, source might be generic
            if not files_read:
                source = "wiki/unknown.md"
            
            return {
                "answer": final_answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }
    
    # Max iterations reached
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
    
    # Return whatever we have
    return {
        "answer": "Reached maximum tool call limit. Partial results may be available.",
        "source": list(files_read.keys())[0] + "#unknown" if files_read else "wiki/unknown.md",
        "tool_calls": all_tool_calls,
    }


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    config = load_config()
    result = run_agentic_loop(question, config)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
