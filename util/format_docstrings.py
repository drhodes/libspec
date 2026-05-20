#!/usr/bin/env python3
import sys
import os
import re
import tokenize
import textwrap

def wrap_list_item(indent, marker, text, max_len=79):
    first_indent = indent + marker
    sub_indent = " " * len(first_indent)
    
    wrapped_lines = textwrap.wrap(
        text,
        width=max_len,
        initial_indent=first_indent,
        subsequent_indent=sub_indent,
        break_long_words=False,
        break_on_hyphens=False
    )
    return "\n".join(wrapped_lines)

def wrap_paragraph(indent, text, max_len=79):
    wrapped_lines = textwrap.wrap(
        text,
        width=max_len,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False
    )
    return "\n".join(wrapped_lines)

def format_docstring(docstring_text, base_indent, max_len=79):
    quote_char = '"""' if docstring_text.startswith('"""') else "'''"
    
    content = docstring_text.strip()[3:-3].strip("\n")
    if not content:
        return f"{base_indent}{quote_char}{quote_char}"
        
    lines = content.splitlines()
    formatted_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            formatted_lines.append("")
            i += 1
            continue
            
        list_match = re.match(r"^(\s*)-\s+(.*)$", line)
        if list_match:
            indent = base_indent
            item_text = list_match.group(2)
            marker = "- "
            
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()
                if not next_stripped or re.match(r"^(\s*)-\s+", next_line):
                    break
                item_text += " " + next_stripped
                i += 1
                
            formatted_lines.append(wrap_list_item(indent, marker, item_text, max_len=max_len))
            i += 1
            continue
            
        if stripped.endswith(":") or len(line) < 40:
            lead_indent = base_indent if stripped != line else line[:line.find(stripped)]
            formatted_lines.append(lead_indent + stripped)
            i += 1
            continue
            
        paragraph_text = stripped
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()
            if not next_stripped or re.match(r"^(\s*)-\s+", next_line) or next_stripped.endswith(":"):
                break
            paragraph_text += " " + next_stripped
            i += 1
            
        formatted_lines.append(wrap_paragraph(base_indent, paragraph_text, max_len=max_len))
        i += 1
        
    res = f"{base_indent}{quote_char}\n"
    for l in formatted_lines:
        res += (l if l else "") + "\n"
    res += f"{base_indent}{quote_char}"
    return res

def format_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        from io import BytesIO
        tokens = list(tokenize.tokenize(BytesIO(content.encode("utf-8")).readline))
    except Exception:
        return
        
    docstrings = []
    for tok in tokens:
        if tok.type == tokenize.STRING:
            s = tok.string
            if s.startswith('"""') or s.startswith("'''"):
                docstrings.append((tok.start, tok.end, s))
                
    if not docstrings:
        return
        
    lines = content.splitlines()
    for start, end, s in reversed(docstrings):
        s_line, s_col = start[0] - 1, start[1]
        e_line, e_col = end[0] - 1, end[1]
        
        base_indent = lines[s_line][:s_col]
        
        formatted = format_docstring(s, base_indent, max_len=79)
        
        doc_lines = formatted.splitlines()
        prefix = lines[s_line][:s_col]
        suffix = lines[e_line][e_col:]
        
        doc_lines[0] = prefix + doc_lines[0].lstrip()
        doc_lines[-1] = doc_lines[-1].rstrip() + suffix
        
        lines[s_line:e_line + 1] = doc_lines
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if os.path.exists(arg):
            format_file(arg)
