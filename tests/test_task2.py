"""
Regression tests for agent.py (Task 2) - Documentation Agent.

Tests verify that the agent:
1. Uses tools (read_file, list_files) to answer questions
2. Returns correct source references
3. Populates tool_calls with execution details
"""

import json
import subprocess
import sys
from pathlib import Path


def test_read_file_tool_usage():
    """
    Test that agent uses read_file tool when asked about documentation.
    
    Question: "How do you resolve a merge conflict?"
    Expected: 
    - read_file in tool_calls
    - wiki/git-workflow.md in source
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How do you resolve a merge conflict?"],
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
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls is populated (agent should use tools)
    assert len(output["tool_calls"]) > 0, "tool_calls should not be empty - agent should use tools"

    # Check that read_file was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "read_file" in tool_names, f"read_file not found in tool_calls. Tools used: {tool_names}"

    # Check source references wiki/git-workflow.md
    source = output["source"]
    assert "wiki/git-workflow.md" in source, f"Expected 'wiki/git-workflow.md' in source, got: {source}"


def test_list_files_tool_usage():
    """
    Test that agent uses list_files tool when asked about directory contents.
    
    Question: "What files are in the wiki?"
    Expected:
    - list_files in tool_calls
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What files are in the wiki?"],
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
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check tool_calls is populated
    assert len(output["tool_calls"]) > 0, "tool_calls should not be empty - agent should use tools"

    # Check that list_files was used
    tool_names = [call.get("tool", "") for call in output["tool_calls"]]
    assert "list_files" in tool_names, f"list_files not found in tool_calls. Tools used: {tool_names}"


def test_tool_call_structure():
    """
    Test that tool_calls have the correct structure.
    
    Each tool call should have:
    - tool: string (tool name)
    - args: dict (arguments)
    - result: string (tool output)
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is in the wiki directory?"],
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

    # Check tool_calls structure
    assert len(output["tool_calls"]) > 0, "tool_calls should not be empty"

    for i, call in enumerate(output["tool_calls"]):
        assert "tool" in call, f"tool_calls[{i}] missing 'tool' field"
        assert "args" in call, f"tool_calls[{i}] missing 'args' field"
        assert "result" in call, f"tool_calls[{i}] missing 'result' field"
        
        assert isinstance(call["tool"], str), f"tool_calls[{i}]['tool'] must be string"
        assert isinstance(call["args"], dict), f"tool_calls[{i}]['args'] must be dict"
        assert isinstance(call["result"], str), f"tool_calls[{i}]['result'] must be string"
