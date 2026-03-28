# bront.network - Bront Parser
# Bront Language v3.5

"""
Parser for Bront language scripts.

Converts .bront files into a list of directive objects that can be
processed by the code generator or executed directly.

Supports all v3.6 directives:
- @PERMAPROMPT, @PROMPT
- @ONPROMPT, @RESPONSE
- @ONERROR, @REPORT  
- @SAVE, @RSAVE (with NORMALIZE)
- @INCLUDE
- @PY (single and multiline)
- @QUERY (basic and loop)
- @SILENT
- @DRYRUN
- @DIAGNOSTICS
- ## comments
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Any, Union
from enum import Enum, auto


class DirectiveType(Enum):
    """Types of Bront directives."""
    PERMAPROMPT = auto()
    PROMPT = auto()
    ONPROMPT = auto()
    ONERROR = auto()
    REPORT = auto()
    SAVE = auto()
    RSAVE = auto()
    INCLUDE = auto()
    DRYRUN = auto()
    DIAGNOSTICS = auto()
    PY = auto()
    PYBLOCK = auto()  # @PY with block (if/for/while)
    QUERY = auto()
    SILENT = auto()
    CLI_COMMAND = auto()
    COMMENT = auto()
    MARKER = auto()  # Internal markers like ## END_BEGIN_SECTION


@dataclass
class Directive:
    """Parsed directive with all relevant attributes."""
    type: DirectiveType
    line_number: int
    raw_line: str
    
    # Common attributes
    value: Optional[str] = None
    
    # @PERMAPROMPT, @PROMPT
    prompt_pattern: Optional[str] = None
    response: Optional[str] = None
    
    # @ONERROR, @REPORT
    error_patterns: Optional[List[str]] = None
    format_string: Optional[str] = None
    context_lines: int = 0
    severity: Optional[str] = None  # high, medium, low, info
    
    # @SAVE, @RSAVE
    filename: Optional[str] = None
    normalize: bool = False
    normalize_pipeline: Optional[str] = None
    
    # @PY
    python_code: Optional[str] = None
    is_multiline: bool = False
    
    # @PYBLOCK (if/for/while)
    py_condition: Optional[str] = None  # The condition/iterator expression
    py_block_type: Optional[str] = None  # 'if', 'for', 'while', 'elif', 'else'
    body: Optional[List['Directive']] = None  # Block body directives
    else_body: Optional[List['Directive']] = None  # For if/elif else clause
    
    # @QUERY
    sql_query: Optional[str] = None
    is_verbose: bool = False
    has_loop: bool = False
    loop_body: Optional[List['Directive']] = None
    
    # @SILENT
    silent_command: Optional[str] = None
    
    # @INCLUDE
    include_path: Optional[str] = None
    
    # @DRYRUN
    dryrun_commands: Optional[List[str]] = None  # For block syntax
    dryrun_command: Optional[str] = None  # For single command syntax


class BrontParser:
    """
    Parser for Bront language scripts.
    
    Usage:
        parser = BrontParser()
        directives = parser.parse_file('script.bront')
        # or
        directives = parser.parse_string(bront_content)
    """
    
    def __init__(self, hostname: str = 'DEVICE', base_dir: str = None):
        """
        Initialize parser.
        
        Args:
            hostname: Device hostname for prompt placeholder substitution
            base_dir: Base directory for resolving @INCLUDE paths
        """
        self.hostname = hostname
        self.base_dir = base_dir or os.getcwd()
        self.lines: List[str] = []
        self.current_line: int = 0
        self.directives: List[Directive] = []
        self.pending_onerror: Optional[Directive] = None
        self.included_files: set = set()  # Track included files to detect circular includes
    
    def parse_file(self, filepath: str) -> List[Directive]:
        """
        Parse a .bront file.
        
        Args:
            filepath: Path to .bront file
            
        Returns:
            List of parsed Directive objects
        """
        filepath = os.path.abspath(filepath)
        
        # Check for circular include
        if filepath in self.included_files:
            raise ValueError(f"Circular include detected: {filepath}")
        self.included_files.add(filepath)
        
        # Set base_dir to file's directory for relative includes
        self.base_dir = os.path.dirname(filepath)
        
        with open(filepath, 'r') as f:
            content = f.read()
        return self.parse_string(content, filepath)
    
    def parse_string(self, content: str, source_file: str = None) -> List[Directive]:
        """
        Parse Bront content from string.
        
        Args:
            content: Bront script content
            source_file: Optional source file path for error messages
            
        Returns:
            List of parsed Directive objects
        """
        self.lines = content.split('\n')
        self.current_line = 0
        self.directives = []
        self.pending_onerror = None
        
        result = self._parse_block(base_indent=-1)
        
        # Check for unpaired @ONERROR
        if self.pending_onerror is not None:
            raise ValueError(f"@ONERROR at line {self.pending_onerror.line_number} must be followed by @REPORT")
        
        return result
    
    def _get_indent(self, line: str) -> int:
        """Get indentation level (number of leading spaces)."""
        return len(line) - len(line.lstrip())
    
    def _parse_block(self, base_indent: int) -> List[Directive]:
        """
        Parse a block of directives at given indentation level.
        
        Args:
            base_indent: The indentation level of the block opener (-1 for top level)
            
        Returns:
            List of directives in this block
        """
        directives = []
        
        while self.current_line < len(self.lines):
            line = self.lines[self.current_line].rstrip('\n')
            stripped = line.strip()
            
            # Empty lines → send newline to device (e.g., NX-OS needs this)
            if not stripped:
                self.current_line += 1
                directives.append(Directive(
                    type=DirectiveType.CLI_COMMAND,
                    line_number=self.current_line,
                    raw_line='',
                    value=''
                ))
                continue
            
            # Check indentation
            indent = self._get_indent(line)
            
            # If we're in a block and indentation is <= base, block ends
            if base_indent >= 0 and indent <= base_indent:
                break
            
            # Parse the line
            directive = self._parse_line(stripped, line, self.current_line + 1)
            
            if directive:
                # Handle @INCLUDE by parsing included file inline
                if directive.type == DirectiveType.INCLUDE:
                    included_directives = self._process_include(directive)
                    directives.extend(included_directives)
                # Handle @PY block (if/for/while ending with :)
                elif directive.type == DirectiveType.PYBLOCK:
                    # Parse the body at deeper indentation
                    self.current_line += 1
                    directive.body = self._parse_block(indent)
                    directives.append(directive)
                    continue  # Don't increment current_line again
                else:
                    directives.append(directive)
            
            self.current_line += 1
        
        return directives
    
    def _parse_line(self, stripped: str, raw: str, line_num: int) -> Optional[Directive]:
        """Parse a single line into a Directive."""
        
        # Comments (require ##)
        if stripped.startswith('##'):
            # Check for special marker
            if stripped == '## END_BEGIN_SECTION':
                return Directive(
                    type=DirectiveType.MARKER,
                    line_number=line_num,
                    raw_line=raw,
                    value='END_BEGIN_SECTION'
                )
            return Directive(
                type=DirectiveType.COMMENT,
                line_number=line_num,
                raw_line=raw,
                value=stripped[2:].strip()
            )
        
        # @PERMAPROMPT
        if stripped.startswith('@PERMAPROMPT'):
            pattern = stripped[12:].strip().strip('"')
            pattern = self._substitute_prompt_placeholders(pattern)
            return Directive(
                type=DirectiveType.PERMAPROMPT,
                line_number=line_num,
                raw_line=raw,
                prompt_pattern=pattern
            )
        
        # @PROMPT (followed by response on next line)
        if stripped.startswith('@PROMPT'):
            pattern = stripped[7:].strip().strip('"')
            # Get response from next line
            self.current_line += 1
            if self.current_line < len(self.lines):
                response = self.lines[self.current_line].strip().strip('"')
            else:
                response = ''
            return Directive(
                type=DirectiveType.PROMPT,
                line_number=line_num,
                raw_line=raw,
                prompt_pattern=pattern,
                response=response
            )
        
        # @ONPROMPT (global watcher, paired with @RESPONSE on next line)
        if stripped.startswith('@ONPROMPT'):
            pattern = stripped[9:].strip().strip('"')
            # Get @RESPONSE from next line
            self.current_line += 1
            response = ''
            if self.current_line < len(self.lines):
                resp_line = self.lines[self.current_line].strip()
                if resp_line.startswith('@RESPONSE'):
                    response = resp_line[9:].strip().strip('"')
                else:
                    # Not a @RESPONSE line - error in script
                    response = resp_line.strip('"')
            return Directive(
                type=DirectiveType.ONPROMPT,
                line_number=line_num,
                raw_line=raw,
                prompt_pattern=pattern,
                response=response
            )
        
        # @ONERROR
        if stripped.startswith('@ONERROR'):
            pattern_match = re.search(r'@ONERROR\s+"([^"]+)"', stripped)
            if pattern_match:
                patterns_str = pattern_match.group(1)
                patterns = [p.strip() for p in patterns_str.split('|')]
                
                # Check for CONTEXT parameter
                context_match = re.search(r'CONTEXT=(\d+)', stripped, re.IGNORECASE)
                context_lines = int(context_match.group(1)) if context_match else 0
                
                directive = Directive(
                    type=DirectiveType.ONERROR,
                    line_number=line_num,
                    raw_line=raw,
                    error_patterns=patterns,
                    context_lines=context_lines
                )
                self.pending_onerror = directive
                return directive
            else:
                raise ValueError(f"@ONERROR at line {line_num} requires quoted pattern string")
        
        # @REPORT
        if stripped.startswith('@REPORT'):
            if self.pending_onerror is None:
                raise ValueError(f"@REPORT at line {line_num} must follow @ONERROR")
            
            format_match = re.search(r'@REPORT\s+"([^"]+)"', stripped)
            if format_match:
                format_string = format_match.group(1)
                
                # Check for CONTEXT parameter on @REPORT line
                context_match = re.search(r'CONTEXT=(\d+)', stripped, re.IGNORECASE)
                context_lines = int(context_match.group(1)) if context_match else 0
                
                # Check for SEVERITY parameter
                severity_match = re.search(r'SEVERITY=(\w+)', stripped, re.IGNORECASE)
                severity = severity_match.group(1).lower() if severity_match else 'high'
                if severity not in ('high', 'medium', 'low', 'info'):
                    severity = 'high'
                
                directive = Directive(
                    type=DirectiveType.REPORT,
                    line_number=line_num,
                    raw_line=raw,
                    format_string=format_string,
                    error_patterns=self.pending_onerror.error_patterns,
                    context_lines=context_lines,
                    severity=severity
                )
                self.pending_onerror = None
                return directive
            else:
                raise ValueError(f"@REPORT at line {line_num} requires quoted format string")
        
        # @RSAVE
        if stripped.startswith('@RSAVE'):
            return self._parse_save_directive(stripped, raw, line_num, is_raw=True)
        
        # @SAVE
        if stripped.startswith('@SAVE'):
            return self._parse_save_directive(stripped, raw, line_num, is_raw=False)
        
        # @INCLUDE
        if stripped.startswith('@INCLUDE'):
            parts = stripped.split()
            if len(parts) < 2:
                raise ValueError(f"@INCLUDE at line {line_num} requires filename")
            return Directive(
                type=DirectiveType.INCLUDE,
                line_number=line_num,
                raw_line=raw,
                filename=parts[1]
            )
        
        # @DIAGNOSTICS (global flag - no arguments)
        if stripped.startswith('@DIAGNOSTICS'):
            return Directive(
                type=DirectiveType.DIAGNOSTICS,
                line_number=line_num,
                raw_line=raw
            )
        
        # @DRYRUN
        if stripped.startswith('@DRYRUN'):
            return self._parse_dryrun_directive(stripped, raw, line_num)
        
        # @PY
        if stripped.startswith('@PY'):
            return self._parse_py_directive(stripped, raw, line_num)
        
        # @QUERY
        if stripped.startswith('@QUERY'):
            return self._parse_query_directive(stripped, raw, line_num)
        
        # @SILENT
        if stripped.startswith('@SILENT'):
            command = stripped[7:].strip()
            return Directive(
                type=DirectiveType.SILENT,
                line_number=line_num,
                raw_line=raw,
                silent_command=command
            )
        
        # CLI command (default)
        return Directive(
            type=DirectiveType.CLI_COMMAND,
            line_number=line_num,
            raw_line=raw,
            value=stripped
        )
    
    def _parse_dryrun_directive(self, stripped: str, raw: str, line_num: int) -> Directive:
        """Parse @DRYRUN directive - single command or block."""
        rest = stripped[7:].strip()  # Remove '@DRYRUN'
        
        # Block syntax: @DRYRUN {
        if rest == '{':
            commands = []
            self.current_line += 1
            while self.current_line < len(self.lines):
                block_line = self.lines[self.current_line].rstrip('\n')
                block_stripped = block_line.strip()
                
                if block_stripped == '}':
                    break
                
                if block_stripped:
                    commands.append(block_stripped)
                
                self.current_line += 1
            
            return Directive(
                type=DirectiveType.DRYRUN,
                line_number=line_num,
                raw_line=raw,
                dryrun_commands=commands
            )
        
        # Single command syntax: @DRYRUN command
        elif rest:
            return Directive(
                type=DirectiveType.DRYRUN,
                line_number=line_num,
                raw_line=raw,
                dryrun_command=rest
            )
        else:
            raise ValueError(f"@DRYRUN at line {line_num} requires command or block")
    
    def _parse_save_directive(self, stripped: str, raw: str, line_num: int, is_raw: bool) -> Directive:
        """Parse @SAVE or @RSAVE directive."""
        directive_name = '@RSAVE' if is_raw else '@SAVE'
        offset = 6 if is_raw else 5
        
        parts = stripped.split()
        if len(parts) < 2:
            raise ValueError(f"{directive_name} at line {line_num} requires filename")
        
        filename = parts[1]
        has_normalize = 'NORMALIZE' in stripped.upper()
        has_multiline = '@@@' in stripped
        
        pipeline = None
        if has_normalize:
            if has_multiline:
                # Collect multiline pipeline
                pipeline_lines = []
                self.current_line += 1
                while self.current_line < len(self.lines):
                    block_line = self.lines[self.current_line].rstrip('\n')
                    if block_line.strip() == '@@@':
                        break
                    if block_line.strip():
                        pipeline_lines.append(block_line.strip())
                    self.current_line += 1
                pipeline = ' '.join(pipeline_lines)
            else:
                # Single line pipeline
                normalize_idx = stripped.upper().find('NORMALIZE')
                pipeline = stripped[normalize_idx + 9:].strip()
        
        return Directive(
            type=DirectiveType.RSAVE if is_raw else DirectiveType.SAVE,
            line_number=line_num,
            raw_line=raw,
            filename=filename,
            normalize=has_normalize,
            normalize_pipeline=pipeline
        )
    
    def _parse_py_directive(self, stripped: str, raw: str, line_num: int) -> Directive:
        """Parse @PY directive (single, multiline, or block)."""
        if '@@@' in stripped:
            # Multiline block
            py_lines = []
            self.current_line += 1
            while self.current_line < len(self.lines):
                block_line = self.lines[self.current_line].rstrip('\n')
                if block_line.strip() == '@@@':
                    break
                py_lines.append(block_line)
                self.current_line += 1
            
            return Directive(
                type=DirectiveType.PY,
                line_number=line_num,
                raw_line=raw,
                python_code='\n'.join(py_lines),
                is_multiline=True
            )
        else:
            # Single line - check if it's a block opener (if/for/while/elif/else ending with :)
            code = stripped[3:].strip()
            
            # Check for block openers
            block_match = re.match(r'^(if|for|while|elif)\s+(.+):$', code)
            else_match = re.match(r'^else\s*:$', code)
            
            if block_match:
                block_type = block_match.group(1)
                condition = block_match.group(2)
                return Directive(
                    type=DirectiveType.PYBLOCK,
                    line_number=line_num,
                    raw_line=raw,
                    py_block_type=block_type,
                    py_condition=condition,
                    body=[]  # Will be filled by _parse_block
                )
            elif else_match:
                return Directive(
                    type=DirectiveType.PYBLOCK,
                    line_number=line_num,
                    raw_line=raw,
                    py_block_type='else',
                    py_condition=None,
                    body=[]  # Will be filled by _parse_block
                )
            else:
                # Regular single line @PY
                return Directive(
                    type=DirectiveType.PY,
                    line_number=line_num,
                    raw_line=raw,
                    python_code=code,
                    is_multiline=False
                )
    
    def _parse_query_directive(self, stripped: str, raw: str, line_num: int) -> Directive:
        """Parse @QUERY directive (basic or loop)."""
        query_part = stripped[6:].strip()  # Remove '@QUERY'
        
        has_loop = '@@@' in query_part
        is_verbose = 'VERBOSE' in query_part.upper()
        
        # Remove VERBOSE keyword
        if is_verbose:
            query_part = re.sub(r'\bVERBOSE\b', '', query_part, flags=re.IGNORECASE).strip()
        
        if has_loop:
            # Query with loop body
            query = query_part.replace('@@@', '').strip()
            
            # Collect loop body
            loop_directives = []
            self.current_line += 1
            while self.current_line < len(self.lines):
                block_line = self.lines[self.current_line].rstrip('\n')
                if block_line.strip() == '@@@':
                    break
                
                # Parse loop body line as directive
                if block_line.strip():
                    loop_dir = self._parse_line(block_line.strip(), block_line, self.current_line + 1)
                    if loop_dir:
                        loop_directives.append(loop_dir)
                
                self.current_line += 1
            
            return Directive(
                type=DirectiveType.QUERY,
                line_number=line_num,
                raw_line=raw,
                sql_query=query,
                is_verbose=is_verbose,
                has_loop=True,
                loop_body=loop_directives
            )
        else:
            # Basic query
            return Directive(
                type=DirectiveType.QUERY,
                line_number=line_num,
                raw_line=raw,
                sql_query=query_part,
                is_verbose=is_verbose,
                has_loop=False
            )
    
    def _substitute_prompt_placeholders(self, prompt: str) -> str:
        """Substitute prompt placeholders with device info."""
        device_pt = self.hostname[:8]
        device_pr = self.hostname[-4:] if len(self.hostname) >= 4 else self.hostname
        prompt = prompt.replace('$DEVICEPT', device_pt)
        prompt = prompt.replace('$DEVICEPR', device_pr)
        prompt = prompt.replace('$DEVICE', self.hostname)
        return prompt
    
    def _process_include(self, directive: Directive) -> List[Directive]:
        """
        Process @INCLUDE directive by parsing the included file.
        
        Args:
            directive: The @INCLUDE directive
            
        Returns:
            List of directives from included file
        """
        include_path = directive.filename
        
        # Resolve relative path from base_dir
        if not os.path.isabs(include_path):
            include_path = os.path.join(self.base_dir, include_path)
        include_path = os.path.abspath(include_path)
        
        # Check file exists
        if not os.path.exists(include_path):
            raise ValueError(f"@INCLUDE file not found: {include_path} (line {directive.line_number})")
        
        # Check for circular include
        if include_path in self.included_files:
            raise ValueError(f"Circular include detected: {include_path} (line {directive.line_number})")
        
        self.included_files.add(include_path)
        
        # Save current parser state
        saved_lines = self.lines
        saved_current_line = self.current_line
        saved_base_dir = self.base_dir
        
        # Parse included file
        self.base_dir = os.path.dirname(include_path)
        with open(include_path, 'r') as f:
            content = f.read()
        
        included_directives = []
        self.lines = content.split('\n')
        self.current_line = 0
        
        while self.current_line < len(self.lines):
            line = self.lines[self.current_line].rstrip('\n')
            stripped = line.strip()
            
            if not stripped:
                self.current_line += 1
                continue
            
            inc_directive = self._parse_line(stripped, line, self.current_line + 1)
            if inc_directive:
                # Handle nested @INCLUDE
                if inc_directive.type == DirectiveType.INCLUDE:
                    nested = self._process_include(inc_directive)
                    included_directives.extend(nested)
                else:
                    included_directives.append(inc_directive)
            
            self.current_line += 1
        
        # Restore parser state
        self.lines = saved_lines
        self.current_line = saved_current_line
        self.base_dir = saved_base_dir
        
        return included_directives
