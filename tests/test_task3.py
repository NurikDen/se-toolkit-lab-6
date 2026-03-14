"""
Regression tests for agent.py (Task 3).

Tests verify that the agent:
1. Uses the correct tools for different question types
2. Outputs valid JSON with tool_calls populated
3. Includes source field for file-based answers
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_uses_read_file_for_code_questions():
    """Test that agent uses read_file tool for source code questions."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with a source code question
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What Python web framework does this project's backend use?"],
        capture_output=True,
        text=True,
        timeout=120,
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

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that read_file was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected agent to call at least one tool"
    
    tools_used = [tc.get("tool") for tc in tool_calls]
    assert "read_file" in tools_used, f"Expected 'read_file' in tool calls, got: {tools_used}"

    # Check answer mentions FastAPI
    answer = output.get("answer", "").lower()
    assert "fastapi" in answer, f"Answer should mention FastAPI: {output['answer']}"


def test_agent_uses_query_api_for_data_questions():
    """Test that agent uses query_api tool for database questions."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with a data question
    result = subprocess.run(
        ["uv", "run", str(agent_path), "How many items are currently stored in the database?"],
        capture_output=True,
        text=True,
        timeout=120,
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

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check that query_api was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected agent to call at least one tool"
    
    tools_used = [tc.get("tool") for tc in tool_calls]
    assert "query_api" in tools_used, f"Expected 'query_api' in tool calls, got: {tools_used}"

    # Check answer contains a number
    answer = output.get("answer", "")
    import re
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, f"Answer should contain a number: {answer}"
