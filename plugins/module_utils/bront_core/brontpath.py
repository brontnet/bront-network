# bront.network - BrontPath Format Utilities
# Bront Language v3.6

"""
BrontPath format conversion utilities.

BrontPath format:
    hierarchy_words|line_words|original_line

For non-indented lines:
    word1|word2|...|original_line

For indented lines (with parent context):
    parent_word1|parent_word2|line_word1|line_word2|...|original_line

Features:
- Preserves original indentation in final field
- Hierarchical paths for indented lines (parent words prepended)
- Each word separated by pipe
- Queryable with SQL via txtdb files

Example:
    Input:
        Build Information:
         Built By     : deenayak
    
    Output:
        Build|Information:|Build Information:
        Build|Information:|Built|By|:|deenayak| Built By     : deenayak
"""

import re
from typing import List, Tuple


def get_indent_level(line: str) -> int:
    """Return the number of leading spaces/tabs (tabs count as 1)."""
    count = 0
    for ch in line:
        if ch == ' ':
            count += 1
        elif ch == '\t':
            count += 1
        else:
            break
    return count


def flatten_to_brontpath(output: str, prefix: str = '') -> str:
    """
    Convert CLI output to BrontPath format.
    
    Each line becomes:
        [hierarchy_words|]line_words|original_line
    
    Indented lines inherit hierarchy from parent lines.
    
    Args:
        output: Raw CLI output text
        prefix: Optional prefix to prepend to all paths
        
    Returns:
        BrontPath formatted string with one path per line
    """
    lines = output.strip().split('\n')
    brontpaths = []
    
    # Stack of (indent_level, words_list) for tracking hierarchy
    hierarchy_stack: List[Tuple[int, List[str]]] = []
    
    for line in lines:
        if not line.strip():
            continue  # Skip empty lines
            
        indent = get_indent_level(line)
        content = line.strip()
        words = content.split()
        
        # Pop stack entries that are at same or deeper indent level
        while hierarchy_stack and hierarchy_stack[-1][0] >= indent:
            hierarchy_stack.pop()
        
        # Build path components
        path_parts = []
        
        # Add optional global prefix
        if prefix:
            path_parts.append(prefix)
        
        # Add hierarchy prefix from stack (parent words)
        for _, parent_words in hierarchy_stack:
            path_parts.extend(parent_words)
        
        # Add current line's words
        path_parts.extend(words)
        
        # Add original line as final field
        path_parts.append(line)
        
        # Join with pipes
        brontpath_line = '|'.join(path_parts)
        brontpaths.append(brontpath_line)
        
        # Push this line onto stack as potential parent for indented lines
        # Only non-indented or less-indented lines become parents
        hierarchy_stack.append((indent, words))
    
    return '\n'.join(brontpaths)


def parse_brontpath_line(line: str) -> dict:
    """
    Parse a single BrontPath line into components.
    
    Args:
        line: Single BrontPath formatted line
        
    Returns:
        Dictionary with 'path' (list of words) and 'original' (original line)
    """
    if not line:
        return {'path': [], 'original': ''}
    
    parts = line.split('|')
    if len(parts) < 2:
        return {'path': [], 'original': line}
    
    return {
        'path': parts[:-1],
        'original': parts[-1]
    }


def reconstruct_from_brontpath(brontpath_content: str) -> str:
    """
    Reconstruct original output from BrontPath format.
    
    This is a lossless operation - the original indentation is preserved.
    
    Args:
        brontpath_content: BrontPath formatted content
        
    Returns:
        Reconstructed original output
    """
    lines = []
    for line in brontpath_content.strip().split('\n'):
        if line:
            parsed = parse_brontpath_line(line)
            lines.append(parsed['original'])
    return '\n'.join(lines)


def search_brontpath(brontpath_content: str, pattern: str, 
                     case_sensitive: bool = False) -> List[str]:
    """
    Search BrontPath content for lines matching a pattern.
    
    Searches the path components (not original line) for matches.
    
    Args:
        brontpath_content: BrontPath formatted content
        pattern: Search pattern (substring match)
        case_sensitive: Whether search is case-sensitive
        
    Returns:
        List of matching original lines
    """
    matches = []
    search_pattern = pattern if case_sensitive else pattern.lower()
    
    for line in brontpath_content.strip().split('\n'):
        if line:
            # Get path portion (everything except last field)
            parts = line.split('|')
            if len(parts) >= 2:
                path_str = '|'.join(parts[:-1])
                compare_str = path_str if case_sensitive else path_str.lower()
                
                if search_pattern in compare_str:
                    matches.append(parts[-1])  # Return original line
    
    return matches
