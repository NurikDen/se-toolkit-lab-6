#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM to answer questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    Logs to stderr
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def load_config() -> dict[str, str]:
    """Load configuration from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    load_dotenv(env_path)

    required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    config = {}

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"Error: Missing required environment variable: {var}", file=sys.stderr)
            print(f"Please ensure {env_path} is properly configured.", file=sys.stderr)
            sys.exit(1)
        config[var] = value

    return config


def call_llm(question: str, config: dict[str, str]) -> str:
    """Call the LLM API and return the answer."""
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
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer questions concisely and accurately.",
            },
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    print(f"Calling LLM at {endpoint}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            answer = data["choices"][0]["message"]["content"]
            print(f"LLM response received.", file=sys.stderr)
            return answer

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


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    config = load_config()
    answer = call_llm(question, config)

    result = {
        "answer": answer,
        "tool_calls": [],
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
