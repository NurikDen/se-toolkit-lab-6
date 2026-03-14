#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM to answer questions using tools.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": [...]}
    Logs to stderr
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    """Load configuration from environment and .env files."""
    # Try to load from .env.agent.secret first
    env_path = Path(__file__).parent / ".env.agent.secret"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Also try .env.docker.secret for LMS_API_KEY
    docker_env_path = Path(__file__).parent / ".env.docker.secret"
    if docker_env_path.exists():
        load_dotenv(docker_env_path)
    
    # LLM configuration (required)
    llm_config = {}
    for var in ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]:
        value = os.getenv(var)
        if not value:
            print(f"Error: Missing required environment variable: {var}", file=sys.stderr)
            print(f"Please ensure .env.agent.secret is properly configured.", file=sys.stderr)
            sys.exit(1)
        llm_config[var] = value
    
    # Backend API configuration
    lms_api_key = os.getenv("LMS_API_KEY")
    if not lms_api_key:
        print("Error: Missing LMS_API_KEY environment variable", file=sys.stderr)
        print("Please ensure .env.docker.secret is properly configured.", file=sys.stderr)
        sys.exit(1)
    
    agent_api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    return {
        **llm_config,
        "LMS_API_KEY": lms_api_key,
        "AGENT_API_BASE_URL": agent_api_base_url,
    }


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def query_api(method: str, path: str, body: str | None = None, skip_auth: bool = False, config: dict | None = None) -> dict:
    """
    Query the backend LMS API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT requests
        skip_auth: If True, don't send the Authorization header (for testing auth requirements)
        config: Configuration dict with LMS_API_KEY and AGENT_API_BASE_URL
    
    Returns:
        Dict with status_code and body
    """
    if config is None:
        config = load_config()
    
    api_key = config["LMS_API_KEY"]
    base_url = config["AGENT_API_BASE_URL"].rstrip("/")
    
    url = f"{base_url}{path}"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # Only add auth if not skipping
    if not skip_auth:
        headers["Authorization"] = f"Bearer {api_key}"
    
    print(f"  [query_api] {method} {url}", file=sys.stderr)
    if skip_auth:
        print(f"  [query_api] Skipping authentication", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                data = json.loads(body) if body else {}
                response = client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                data = json.loads(body) if body else {}
                response = client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return {"status_code": 400, "body": {"error": f"Unknown method: {method}"}}
            
            result = {
                "status_code": response.status_code,
                "body": response.json() if response.content else None,
            }
            print(f"  [query_api] Response: {response.status_code}", file=sys.stderr)
            return result
            
    except httpx.HTTPStatusError as e:
        print(f"  [query_api] HTTP error: {e.response.status_code}", file=sys.stderr)
        return {"status_code": e.response.status_code, "body": {"error": str(e)}}
    except httpx.RequestError as e:
        print(f"  [query_api] Request failed: {e}", file=sys.stderr)
        return {"status_code": 0, "body": {"error": str(e)}}
    except json.JSONDecodeError as e:
        print(f"  [query_api] JSON decode error: {e}", file=sys.stderr)
        return {"status_code": response.status_code, "body": {"raw": response.text}}


def read_file(path: str) -> dict:
    """
    Read a file from the project.
    
    Args:
        path: Relative path to the file (e.g., 'wiki/backend.md', 'backend/app/main.py')
    
    Returns:
        Dict with content or error
    """
    base_path = Path(__file__).parent
    file_path = base_path / path
    
    print(f"  [read_file] Reading: {path}", file=sys.stderr)
    
    if not file_path.exists():
        print(f"  [read_file] File not found: {path}", file=sys.stderr)
        return {"error": f"File not found: {path}"}
    
    try:
        content = file_path.read_text()
        # Truncate if too large (LLM context limits)
        max_chars = 10000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n... [truncated]"
        print(f"  [read_file] Read {len(content)} chars", file=sys.stderr)
        return {"content": content, "path": path}
    except Exception as e:
        print(f"  [read_file] Error: {e}", file=sys.stderr)
        return {"error": str(e)}


def list_files(path: str) -> dict:
    """
    List files in a directory.
    
    Args:
        path: Relative path to the directory (e.g., 'backend/app/routers/', 'wiki/')
    
    Returns:
        Dict with list of files or error
    """
    base_path = Path(__file__).parent
    dir_path = base_path / path
    
    print(f"  [list_files] Listing: {path}", file=sys.stderr)
    
    if not dir_path.exists():
        print(f"  [list_files] Directory not found: {path}", file=sys.stderr)
        return {"error": f"Directory not found: {path}"}
    
    if not dir_path.is_dir():
        print(f"  [list_files] Not a directory: {path}", file=sys.stderr)
        return {"error": f"Not a directory: {path}"}
    
    try:
        files = []
        for item in dir_path.iterdir():
            if item.is_file():
                files.append(item.name)
            elif item.is_dir():
                files.append(f"{item.name}/")
        
        result = {"files": sorted(files), "path": path}
        print(f"  [list_files] Found {len(files)} items", file=sys.stderr)
        return result
    except Exception as e:
        print(f"  [list_files] Error: {e}", file=sys.stderr)
        return {"error": str(e)}


# -----------------------------------------------------------------------------
# Tool definitions for LLM function calling
# -----------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend LMS API for live data. Use for questions about database contents, API responses, current system state, or runtime behavior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method: GET, POST, PUT, or DELETE"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path, e.g., '/items/', '/analytics/completion-rate?lab=lab-06'"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests"
                    },
                    "skip_auth": {
                        "type": "boolean",
                        "description": "If true, don't send the Authorization header. Use this to test what happens without authentication."
                    }
                },
                "required": ["method", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project. Use for questions about source code, configuration files, documentation in the wiki, or any static file content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from project root, e.g., 'wiki/backend.md', 'backend/app/main.py', 'docker-compose.yml'"
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
            "description": "List files in a directory. Use to discover project structure, find API routers, or explore what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the directory from project root, e.g., 'backend/app/routers/', 'wiki/', 'plans/'"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

TOOL_FUNCTIONS = {
    "query_api": query_api,
    "read_file": read_file,
    "list_files": list_files,
}

# -----------------------------------------------------------------------------
# LLM Client
# -----------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an intelligent assistant that answers questions about this software project.

You have access to these tools:
- read_file: Read a file from the project (wiki documentation, source code, configuration files)
- list_files: List files in a directory (useful for discovering API routers or exploring structure)
- query_api: Query the running backend API for live data (database contents, API responses)

Tool selection guide:
- For questions about LIVE DATA (database contents, API responses, current state, status codes) → use query_api
- For questions about SOURCE CODE (what framework, how it works, configuration) → use read_file
- For questions about PROJECT STRUCTURE (what files exist, what routers are there) → use list_files
- For questions about WIKI DOCUMENTATION (SSH setup, branch protection, git workflow) → use read_file on wiki/ files

Important tips:
- For "list all X" questions about files in a directory: use list_files ONCE, then answer from the file names. Do NOT read each file individually.
- When listing files in a directory, use the results to answer directly if possible
- When searching for a topic in a large file, read the file once and search for keywords in the content
- If a file is truncated, use the content you have - don't re-read the same file
- For wiki questions, first list wiki files to find the right one, then read it
- For API queries, always include the full path with leading slash
- Configuration files like Dockerfile, docker-compose.yml are in the project root
- Base your answer on the tool results, not assumptions

Answer concisely but completely. Cite your sources when relevant. For reasoning questions about architecture or data flow, provide a detailed explanation tracing the full path."""


def call_llm(question: str, config: dict[str, Any], messages: list | None = None) -> dict:
    """
    Call the LLM API with function calling support.
    
    Args:
        question: User's question
        config: Configuration dict
        messages: Optional message history for multi-turn conversations
    
    Returns:
        Dict with 'answer', 'tool_calls', and optionally 'needs_followup'
    """
    api_key = config["LLM_API_KEY"]
    api_base = config["LLM_API_BASE"]
    model = config["LLM_MODEL"]
    
    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Build messages
    if messages is None:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
    
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.1,  # Very low temperature for deterministic tool calling
    }
    
    print(f"Calling LLM at {endpoint}...", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            message = data["choices"][0]["message"]
            
            # Check for tool calls
            tool_calls = message.get("tool_calls")
            
            if tool_calls:
                # LLM wants to call tools
                print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)
                return {
                    "type": "tool_call",
                    "tool_calls": tool_calls,
                    "message": message,
                }
            else:
                # LLM provided a direct answer
                answer = message.get("content") or ""
                print(f"LLM provided direct answer", file=sys.stderr)
                return {
                    "type": "answer",
                    "answer": answer,
                }
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        return {"type": "error", "error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return {"type": "error", "error": f"Request failed: {e}"}
    except (KeyError, IndexError) as e:
        print(f"Unexpected API response format: {e}", file=sys.stderr)
        return {"type": "error", "error": f"Unexpected response format: {e}"}


def execute_tool_call(tool_call: dict, config: dict) -> dict:
    """Execute a single tool call and return the result."""
    function = tool_call["function"]
    name = function["name"]
    arguments = json.loads(function["arguments"])
    
    print(f"Executing tool: {name}({arguments})", file=sys.stderr)
    
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    
    tool_func = TOOL_FUNCTIONS[name]
    
    # Special handling for query_api which needs config
    if name == "query_api":
        result = tool_func(**arguments, config=config)
    else:
        result = tool_func(**arguments)
    
    return result


# -----------------------------------------------------------------------------
# Main Agent Loop
# -----------------------------------------------------------------------------

def run_agent(question: str, config: dict, max_iterations: int = 20) -> dict:
    """
    Run the agentic loop.
    
    Args:
        question: User's question
        config: Configuration dict
        max_iterations: Maximum tool call iterations to prevent infinite loops
    
    Returns:
        Dict with 'answer', 'tool_calls', and 'source' list
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    all_tool_calls = []
    sources = set()  # Track files that were read
    
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)
        
        result = call_llm(question, config, messages)
        
        if result["type"] == "error":
            return {"answer": f"Error: {result['error']}", "tool_calls": all_tool_calls}
        
        if result["type"] == "answer":
            # LLM provided final answer
            source_str = list(sources)[0] if sources else ""
            return {
                "answer": result["answer"],
                "tool_calls": all_tool_calls,
                "source": source_str,
            }
        
        if result["type"] == "tool_call":
            # Execute tool calls
            tool_calls = result["tool_calls"]
            
            for tool_call in tool_calls:
                # Record the tool call for output
                tool_call_record = {
                    "tool": tool_call["function"]["name"],
                    "args": json.loads(tool_call["function"]["arguments"]),
                }
                
                # Track sources (files that were read)
                if tool_call["function"]["name"] == "read_file":
                    args = json.loads(tool_call["function"]["arguments"])
                    sources.add(args.get("path", ""))
                
                # Execute the tool
                tool_result = execute_tool_call(tool_call, config)
                tool_call_record["result"] = json.dumps(tool_result, default=str)
                all_tool_calls.append(tool_call_record)
                
                # Add assistant message with tool call to history
                messages.append({
                    "role": "assistant",
                    "content": result["message"].get("content"),
                    "tool_calls": [tool_call],
                })
                
                # Add tool result to history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "unknown"),
                    "content": json.dumps(tool_result, default=str),
                })
    
    # Max iterations reached without final answer
    source_str = list(sources)[0] if sources else ""
    return {
        "answer": "I was unable to complete the analysis within the maximum iterations.",
        "tool_calls": all_tool_calls,
        "source": source_str,
    }


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)
    
    config = load_config()
    result = run_agent(question, config)
    
    # Output JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
