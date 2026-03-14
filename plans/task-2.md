# Task 2 Plan: The Documentation Agent

## Overview

This task extends the Task 1 agent with an **agentic loop** and **two tools** (`read_file`, `list_files`) that allow the LLM to navigate and read the project wiki to answer questions.

## Tool Schemas

### Design Approach

Tools will be defined as **function-calling schemas** in the OpenAI-compatible format. Each tool schema includes:
- `name`: The tool identifier
- `description`: What the tool does and when to use it
- `parameters`: JSON Schema defining the arguments

### Tool Definitions

#### 1. `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository. Use this to examine file contents.",
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
```

**Implementation:**
- Accept `path` parameter
- Validate path security (no `../` traversal outside project root)
- Read file using `Path.read_text()`
- Return contents as string, or error message if file doesn't exist

#### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
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
```

**Implementation:**
- Accept `path` parameter
- Validate path security
- Use `Path.iterdir()` to list entries
- Return newline-separated string of filenames

## Path Security

### Threat Model

The LLM might be tricked (via prompt injection or malicious user input) into accessing files outside the project directory using paths like:
- `../../etc/passwd`
- `../../../home/user/.ssh/id_rsa`
- `wiki/../../../etc/passwd`

### Security Strategy

**Validation Rules:**
1. Resolve the full absolute path using `Path.resolve()`
2. Check that the resolved path starts with the project root
3. Reject any path that escapes the project boundary

**Implementation:**
```python
PROJECT_ROOT = Path(__file__).parent.resolve()

def validate_path(relative_path: str) -> Path:
    """Validate and resolve a relative path, ensuring it stays within project root."""
    # Resolve to absolute path
    full_path = (PROJECT_ROOT / relative_path).resolve()
    
    # Check it's within project root
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise SecurityError(f"Path traversal detected: {relative_path}")
    
    return full_path
```

**Error Handling:**
- If path validation fails → return error message to LLM (not exception)
- LLM receives: `"Error: Access denied - path outside project directory"`
- This prevents information leakage while allowing the agent to recover

## Agentic Loop

### Loop Structure

```
┌─────────────────────────────────────────────────────────────┐
│  1. Build messages list with system prompt + user question  │
│  2. Send to LLM with tool schemas                           │
│  3. Parse response                                          │
│     - If tool_calls: execute tools, append results, loop    │
│     - If text answer: extract answer + source, output JSON  │
│  4. Max 10 iterations (prevent infinite loops)              │
└─────────────────────────────────────────────────────────────┘
```

### Message Flow

**Initial Request:**
```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_question}
]
```

**After Tool Call:**
```python
# LLM returns tool_calls
messages.append(assistant_message_with_tool_calls)

# Execute tool, get result
tool_result = execute_tool(tool_call)

# Append tool result as 'tool' role (or 'user' role for OpenAI compat)
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": tool_result
})

# Loop back to LLM
```

### Loop Termination Conditions

1. **LLM returns no tool calls** → Final answer, exit loop
2. **10 tool calls reached** → Stop, use current answer
3. **Error in tool execution** → Report error to LLM, continue loop

### System Prompt Strategy

The system prompt will instruct the LLM to:

1. Use `list_files` to discover wiki files when asked about documentation
2. Use `read_file` to examine specific files for answers
3. Extract the relevant section and create a source reference
4. Format the final answer with the source as `wiki/filename.md#section-anchor`

**Draft System Prompt:**
```
You are a documentation assistant for a software engineering lab.
You have access to two tools:
- list_files: List files in a directory
- read_file: Read the contents of a file

When asked a question about the project:
1. Use list_files to discover relevant wiki files
2. Use read_file to examine files that might contain the answer
3. Identify the specific section that answers the question
4. Provide your final answer with a source reference in the format:
   wiki/filename.md#section-anchor

Always be concise and accurate. If you cannot find the answer in the
wiki, say so honestly.
```

## Output Format

**JSON Schema:**
```json
{
  "answer": "string (required) - The final answer",
  "source": "string (required) - wiki path with section anchor",
  "tool_calls": [
    {
      "tool": "string - tool name",
      "args": "object - arguments passed",
      "result": "string - tool output"
    }
  ]
}
```

## Implementation Steps

1. **Define tool schemas** - JSON Schema for each tool
2. **Implement tool functions** - `read_file`, `list_files` with path validation
3. **Implement agentic loop** - Message management, tool execution, iteration limit
4. **Update output format** - Add `source` field, populate `tool_calls`
5. **Write system prompt** - Guide LLM to use tools effectively
6. **Test manually** - Verify tool discovery and answer extraction
7. **Write regression tests** - Test both tools with real questions

## Testing Strategy

**Test 1: `read_file` tool**
- Question: "How do you resolve a merge conflict?"
- Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

**Test 2: `list_files` tool**
- Question: "What files are in the wiki?"
- Expected: `list_files` in tool_calls

**Security Test (manual):**
- Verify `../../etc/passwd` is rejected
- Verify paths within project work correctly
