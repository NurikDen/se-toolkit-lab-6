"""
Regression tests for agent.py (Task 1).

Tests verify that the agent:
1. Runs successfully with a question argument
2. Outputs valid JSON to stdout
3. Contains required fields: answer and tool_calls
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    # Path to agent.py in project root
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with a simple question using uv run
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is Python?"],
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

    # Check field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    # Check answer is non-empty
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Check tool_calls is empty (Task 1 doesn't implement tools yet)
    assert output["tool_calls"] == [], "'tool_calls' must be empty array for Task 1"
