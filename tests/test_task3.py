"""
Regression tests for agent.py (Task 3) - System Agent.

Tests verify that the agent:
1. Uses query_api tool for live data questions
2. Uses read_file tool for source code questions
3. Handles API authentication correctly
"""

import json
import subprocess
import sys
from pathlib import Path


def test_read_file_for_source_code_question():
    """
    Test that agent uses read_file tool when asked about source code.
    
    Question: "What framework does the backend use?"
    Expected:
    - read_file in tool_calls
    - answer contains "FastAPI"
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What framework does the backend use?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Print stderr for debugging
    print(f"stderr: {result.stderr}", file=sys.stderr)

    # Check exit code
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls is populated
    assert len(output["tool_calls"]) > 0, "tool_calls should not be empty - agent should use tools"

    # Check that read_file was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "read_file" in tool_names, f"read_file not found in tool_calls. Tools used: {tool_names}"

    # Check answer mentions FastAPI
    answer = output["answer"].lower()
    assert "fastapi" in answer, f"Expected 'FastAPI' in answer, got: {output['answer']}"


def test_query_api_for_data_question():
    """
    Test that agent uses query_api tool when asked about live data.
    
    Question: "How many items are in the database?"
    Expected:
    - query_api in tool_calls
    - answer contains a number
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Print stderr for debugging
    print(f"stderr: {result.stderr}", file=sys.stderr)

    # Check exit code
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls is populated
    assert len(output["tool_calls"]) > 0, "tool_calls should not be empty - agent should use tools"

    # Check that query_api was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "query_api" in tool_names, f"query_api not found in tool_calls. Tools used: {tool_names}"

    # Check answer contains a number (the item count)
    import re
    answer = output["answer"]
    numbers = re.findall(r'\d+', answer)
    assert len(numbers) > 0, f"Expected a number in answer, got: {answer}"


def test_query_api_structure():
    """
    Test that query_api tool calls have the correct structure.
    
    Each query_api call should have:
    - tool: "query_api"
    - args: dict with "method" and "path"
    - result: string with status_code
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What HTTP status code when requesting /items/ without auth?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Print stderr for debugging
    print(f"stderr: {result.stderr}", file=sys.stderr)

    # Check exit code
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nstdout: {result.stdout}")

    # Find query_api calls
    query_api_calls = [c for c in output["tool_calls"] if c.get("tool") == "query_api"]
    assert len(query_api_calls) > 0, "No query_api calls found in tool_calls"

    # Check structure of each query_api call
    for i, call in enumerate(query_api_calls):
        assert "tool" in call, f"query_api_calls[{i}] missing 'tool' field"
        assert "args" in call, f"query_api_calls[{i}] missing 'args' field"
        assert "result" in call, f"query_api_calls[{i}] missing 'result' field"
        
        assert call["tool"] == "query_api", f"Expected tool 'query_api', got '{call['tool']}'"
        assert isinstance(call["args"], dict), f"query_api_calls[{i}]['args'] must be dict"
        assert "method" in call["args"], f"query_api_calls[{i}]['args'] missing 'method'"
        assert "path" in call["args"], f"query_api_calls[{i}]['args'] missing 'path'"
        assert isinstance(call["result"], str), f"query_api_calls[{i}]['result'] must be string"
