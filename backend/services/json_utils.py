"""JSON parsing utilities for handling LLM responses with various formatting issues."""

import json
import re


def _fix_unquoted_keys(text: str) -> str:
    r"""
    Fix unquoted JSON keys by adding quotes around property names.
    E.g., converts: problem_statement: "value" → "problem_statement": "value"
    
    Only matches keys that come after { or , (not keys inside string values).
    
    Args:
        text: JSON text with potentially unquoted keys
        
    Returns:
        JSON text with quoted keys
    """
    # Match unquoted keys that come immediately after { or ,
    # Pattern: ({|,) followed by optional whitespace/newlines, then unquoted key, then :
    # This avoids matching keys inside string values
    text = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    
    return text


def _escape_unescaped_quotes(text: str) -> str:
    r"""
    Escape unescaped quotes inside JSON string values.
    Fixes cases like: "text "quoted" text" → "text \"quoted\" text"
    
    Strategy: Walk through character by character, tracking whether we're inside a string.
    When we find internal quotes (quotes not at string boundaries), escape them.
    """
    result = []
    i = 0
    
    while i < len(text):
        # Look for the pattern ": " which precedes a JSON value
        if i + 2 < len(text) and text[i:i+3] == '": ':
            result.append(text[i:i+3])
            i += 3
            
            # Skip whitespace
            while i < len(text) and text[i] in ' \t\n\r':
                result.append(text[i])
                i += 1
            
            # Now we should see an opening quote
            if i < len(text) and text[i] == '"':
                result.append('"')
                i += 1
                
                # Find the actual closing quote (which is followed by , } or ] )
                while i < len(text):
                    if text[i] == '\\' and i + 1 < len(text):
                        # Already escaped character, keep as-is
                        result.append(text[i])
                        result.append(text[i + 1])
                        i += 2
                    elif text[i] == '"':
                        # Found a quote - check if this closes the string
                        # It closes if followed by whitespace then comma/brace/bracket
                        j = i + 1
                        while j < len(text) and text[j] in ' \t\n\r':
                            j += 1
                        
                        if j < len(text) and text[j] in ',}]':
                            # This is the closing quote
                            result.append('"')
                            i += 1
                            break
                        else:
                            # This is an internal quote, escape it
                            result.append('\\')
                            result.append('"')
                            i += 1
                    else:
                        result.append(text[i])
                        i += 1
        else:
            result.append(text[i])
            i += 1
    
    return ''.join(result)


def clean_and_parse_json(text: str) -> dict:
    r"""
    Parse JSON from LLM response, handling:
    - Markdown code fences (```json and ```)
    - Invalid escape sequences (e.g., \n, \_, \( inside strings)
    - Unquoted JSON property names
    - Single-quoted strings (converts to double quotes)
    - Unescaped quotes inside string values
    
    Args:
        text: Raw text response from LLM
        
    Returns:
        Parsed JSON object as dict
        
    Raises:
        json.JSONDecodeError: If JSON parsing fails after cleanup
    """
    text = text.strip()
    
    # Remove markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        # Handle ```json or ``` prefix
        lines = text.split("\n")
        if lines[0].startswith("```"):
            # Remove first line (opening fence) and last line (closing fence)
            if len(lines) > 2:
                text = "\n".join(lines[1:-1])
            elif len(lines) > 1:
                text = lines[1]
    
    # Convert single-quoted property names to double-quoted: 'key': → "key":
    text = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', text)
    
    # Convert single-quoted values to double-quoted: : 'value' → : "value"
    # But be careful not to match single quotes inside double-quoted strings
    text = re.sub(r":\s*'([^']*)'(?=\s*[,}])", r': "\1"', text)
    
    # Fix unquoted JSON keys (after converting single quotes)
    text = _fix_unquoted_keys(text)
    
    # Fix unquoted string values (common when LLM returns unquoted enum/simple values)
    # Pattern: : (identifier) followed by , } or ]
    # Examples: :easy, -> :"easy", or :Medium} -> :"Medium"}
    text = re.sub(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*([,}\]])', r': "\1"\2', text)
    
    # Escape any unescaped quotes inside string values
    text = _escape_unescaped_quotes(text)
    
    # Fix invalid escape sequences
    # Replace backslashes NOT followed by valid JSON escape characters: " \ / b f n r t u
    # This fixes cases like: \n (inside a string, not end-of-line), \_, \(, etc.
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    
    # Replace raw newlines in strings with escaped newlines
    # This handles cases where the LLM includes actual newlines inside strings
    # We need to be careful to only do this for newlines inside quoted strings
    lines = text.split('\n')
    result_lines = []
    in_string = False
    escape_next = False
    
    for line in lines:
        if in_string and line:
            # We're continuing a multi-line string, add escape
            line = '\\n' + line
        
        # Track if we end this line still inside a string
        for char in line:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
        
        result_lines.append(line)
    
    text = ' '.join(result_lines)
    
    # Parse and return JSON
    return json.loads(text)
