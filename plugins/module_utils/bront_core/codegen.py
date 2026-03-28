# bront.network - Code Generator
# Bront Language v3.5

"""
Code generator for Bront language.

Converts parsed directives into executable Python code.
Supports two output modes:
- Standalone: Full Python script with SSH execution
- Ansible: Code snippets for Ansible module integration
"""

import re
from typing import List, Dict, Optional, Any
from .parser import Directive, DirectiveType


class BrontCodeGenerator:
    """
    Generate Python code from parsed Bront directives.
    
    Usage:
        gen = BrontCodeGenerator(device_info, config)
        python_code = gen.generate(directives)
    """
    
    def __init__(self, device_info: Dict[str, Any], config: Dict[str, Any], 
                 mode: str = 'standalone'):
        """
        Initialize code generator.
        
        Args:
            device_info: Device connection info (host, username, password, port, hostname)
            config: Bront configuration (WORKDIR, LOGDIR, timestamp_subdirs)
            mode: Output mode - 'standalone' or 'ansible'
        """
        self.device_info = device_info
        self.config = config
        self.mode = mode
        self.hostname = device_info.get('hostname', 'DEVICE')
    
    def generate(self, directives: List[Directive], expanded_file: str = 'expanded.bront') -> str:
        """
        Generate Python code from directives.
        
        Args:
            directives: List of parsed Directive objects
            expanded_file: Path to expanded bront file (for logging)
            
        Returns:
            Generated Python code as string
        """
        if self.mode == 'standalone':
            return self._generate_standalone(directives, expanded_file)
        else:
            return self._generate_ansible(directives)
    
    def _generate_standalone(self, directives: List[Directive], expanded_file: str) -> str:
        """Generate standalone Python script."""
        code_lines = []
        
        # Imports and setup
        code_lines.extend(self._generate_imports())
        code_lines.extend(self._generate_config_setup())
        code_lines.extend(self._generate_runtime_setup(expanded_file))
        code_lines.extend(self._generate_helper_functions())
        code_lines.extend(self._generate_ssh_connection())
        
        # Process directives
        code_lines.append("prompt_list = []\n")
        code_lines.append("error_handlers = []  # List of (patterns_list, format_string, context_lines) tuples\n\n")
        
        for directive in directives:
            code_lines.extend(self._generate_directive_code(directive))
        
        # Cleanup and summary
        code_lines.extend(self._generate_cleanup())
        
        # Add flatten function at the beginning
        code_lines.insert(0, self._get_flatten_function())
        
        return ''.join(code_lines)
    
    def _generate_ansible(self, directives: List[Directive]) -> str:
        """Generate code for Ansible module integration."""
        # For Ansible mode, we generate code that uses the executor directly
        # rather than generating a full standalone script
        code_lines = []
        
        code_lines.append("# Ansible mode - use BrontExecutor\n")
        code_lines.append("from ansible_collections.bront.network.plugins.module_utils.bront_core import BrontExecutor\n\n")
        
        # Generate executor setup
        code_lines.append("executor = BrontExecutor(device_info, config, output_mode='ansible')\n")
        code_lines.append("result = executor.execute(directives)\n")
        
        return ''.join(code_lines)
    
    def _generate_imports(self) -> List[str]:
        """Generate import statements."""
        return [
            "import pexpect\n",
            "import re\n",
            "import subprocess\n",
            "import sys\n",
            "import os\n",
            "import signal\n",
            "import sqlite3\n",
            "from datetime import datetime\n",
            "import uuid\n",
            "from pathlib import Path\n\n",
        ]
    
    def _generate_config_setup(self) -> List[str]:
        """Generate configuration setup code."""
        return [
            "# Directory configuration\n",
            f"WORKDIR = r'{self.config.get('WORKDIR', 'bront_work')}'\n",
            f"LOGDIR = r'{self.config.get('LOGDIR', 'bront_logs')}'\n",
            f"timestamp_subdirs = {self.config.get('timestamp_subdirs', False)}\n\n",
        ]
    
    def _generate_runtime_setup(self, expanded_file: str) -> List[str]:
        """Generate runtime setup code."""
        import os
        return [
            "# SQLite database for queries\n",
            "db_conn = sqlite3.connect(':memory:')\n",
            "db_cursor = db_conn.cursor()\n",
            "loaded_tables = set()\n",
            "query_verbose = False  # Global flag for query verbosity\n\n",
            "buffer = ''\n",
            "prompts = {}\n",
            "responses = {}\n",
            "error_buffer = ''\n",
            f"device_name = '{self.hostname}'\n",
            "log_uuid = str(uuid.uuid4())[:8]\n",
            "log_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')\n",
            "run_id = f'{device_name}_{log_timestamp}_{log_uuid}'\n",
            "child = None  # Will be set after SSH connection\n\n",
            "# Create unique run directory in WORKDIR\n",
            "run_dir = os.path.join(WORKDIR, run_id)\n",
            "os.makedirs(run_dir, exist_ok=True)\n",
            "# Convert to absolute path\n",
            "run_dir = os.path.abspath(run_dir)\n",
            "print(f'Work directory: {run_dir}')\n\n",
            "# Configure log directory (BEFORE chdir so relative paths resolve correctly)\n",
            "if timestamp_subdirs:\n",
            "    log_subdir = datetime.now().strftime('%Y/%m/%d')\n",
            "    log_path = os.path.join(LOGDIR, log_subdir)\n",
            "else:\n",
            "    log_path = LOGDIR\n",
            "# Convert to absolute path BEFORE creating directory\n",
            "log_path = os.path.abspath(log_path)\n",
            "os.makedirs(log_path, exist_ok=True)\n",
            "print(f'Log directory: {log_path}')\n\n",
            "# Log file paths (absolute)\n",
            "error_log = os.path.join(log_path, f'{run_id}_error.log')\n",
            "output_log = os.path.join(log_path, f'{run_id}_output.log')\n",
            "bront_log = os.path.join(log_path, f'{run_id}_bront.log')\n\n",
            "# Copy expanded bront script to log directory (BEFORE chdir)\n",
            f"expanded_file = r'{os.path.abspath(expanded_file)}'\n",
            "with open(expanded_file, 'r') as src:\n",
            "    bront_content = src.read()\n",
            "with open(bront_log, 'w') as dst:\n",
            "    dst.write(bront_content)\n\n",
            "# NOW change to run directory for all file operations\n",
            "os.chdir(run_dir)\n",
            "# Save script copy to work directory (AFTER chdir)\n",
            "with open('script.bront', 'w') as dst:\n",
            "    dst.write(bront_content)\n\n",
        ]
    
    def _generate_helper_functions(self) -> List[str]:
        """Generate helper functions."""
        host_str = self.device_info['host']
        
        return [
            "# Signal handler for graceful interruption\n",
            "def signal_handler(signum, frame):\n",
            "    signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'\n",
            "    print(f'\\n\\n=== Script Interrupted ({signal_name}) ===')\n",
            "    if child and child.isalive():\n",
            "        try:\n",
            "            child.close(force=True)\n",
            "        except:\n",
            "            pass\n",
            "    print(f'Work dir:    {run_dir}')\n",
            "    print(f'Log dir:     {log_path}')\n",
            "    print(f'Script log:  {bront_log}')\n",
            "    print(f'Output log:  {output_log}')\n",
            "    if error_buffer:\n",
            "        print(f'Error log:   {error_log} (ERRORS DETECTED)')\n",
            "    else:\n",
            "        print(f'Error log:   {error_log} (no errors)')\n",
            "    sys.exit(1)\n\n",
            "# Register signal handlers\n",
            "signal.signal(signal.SIGINT, signal_handler)   # Ctrl-C\n",
            "signal.signal(signal.SIGTERM, signal_handler)  # kill command\n\n",
            self._get_bash_function(),
            self._get_load_txtdb_function(),
            self._get_check_errors_function(),
            self._get_log_output_function(),
        ]
    
    def _get_bash_function(self) -> str:
        """Generate bash helper function."""
        return """def bash(cmd):
    '''Execute bash command and return output'''
    import subprocess
    return subprocess.getoutput(cmd)

"""
    
    def _get_load_txtdb_function(self) -> str:
        """Generate txtdb loader function."""
        return """def load_txtdb_to_sqlite(table_name):
    '''Load .txtdb file into SQLite table'''
    global loaded_tables, query_verbose
    if table_name in loaded_tables:
        return  # Already loaded
    
    txtdb_file = f'{table_name}.txtdb'
    if not os.path.exists(txtdb_file):
        print(f'Warning: {txtdb_file} not found, skipping')
        return
    
    with open(txtdb_file, 'r') as f:
        lines = f.readlines()
    
    if not lines:
        return
    
    # Determine number of columns from first line
    first_line = lines[0].strip()
    fields = first_line.split('|')
    num_cols = len(fields)
    
    # Create column names: col1, col2, ..., original_line (last column)
    col_names = [f'col{i+1}' for i in range(num_cols-1)] + ['original_line']
    
    # Create table
    col_defs = ', '.join([f'{name} TEXT' for name in col_names])
    db_cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
    db_cursor.execute(f'CREATE TABLE {table_name} ({col_defs})')
    
    # Insert rows
    placeholders = ', '.join(['?' for _ in range(num_cols)])
    for line in lines:
        fields = line.strip().split('|')
        # Pad with empty strings if needed
        while len(fields) < num_cols:
            fields.append('')
        db_cursor.execute(f'INSERT INTO {table_name} VALUES ({placeholders})', fields[:num_cols])
    
    db_conn.commit()
    loaded_tables.add(table_name)
    if query_verbose:
        print(f'Loaded {len(lines)} rows into table {table_name}')

"""
    
    def _get_check_errors_function(self) -> str:
        """Generate error checking function."""
        return f"""def check_errors(output, device='{self.hostname}'):
    '''Check output against error patterns and report matches'''
    global error_buffer
    for patterns_list, format_string, context_lines in error_handlers:
        for pattern in patterns_list:
            match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
            if match:
                matched_text = match.group(0)
                
                # Extract context if specified
                if context_lines > 0:
                    lines = output.split('\\n')
                    # Find the line containing the match
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            start = max(0, i - context_lines)
                            end = min(len(lines), i + context_lines + 1)
                            context_block = '\\n'.join(lines[start:end])
                            matched_text = context_block
                            break
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Format the report string
                report = format_string
                report = report.replace('%s', matched_text)
                report = report.replace('%t', timestamp)
                report = report.replace('%d', device)
                report = report.replace('{{DEVICE}}', device)
                
                # Log to file and buffer
                log_entry = f"[{{timestamp}}] {{report}}\\n"
                error_buffer += log_entry
                with open(error_log, 'a') as err_f:
                    err_f.write(log_entry)
                break  # Only report first match per handler

"""
    
    def _get_log_output_function(self) -> str:
        """Generate output logging function."""
        return """def log_output(text):
    '''Write text to output log file'''
    with open(output_log, 'a') as out_f:
        out_f.write(text)

"""
    
    def _generate_ssh_connection(self) -> List[str]:
        """Generate SSH connection code."""
        host_str = self.device_info['host']
        return [
            f"child = pexpect.spawn('ssh', args=['{self.device_info['username']}@{host_str}', '-p', '{self.device_info['port']}'])\n",
            "child.logfile = sys.stdout.buffer\n",
            "child.expect('[Pp]assword:')\n",
            "child.logfile = None\n",
            f"child.sendline('{self.device_info['password']}')\n",
            "child.logfile = sys.stdout.buffer\n",
            "child.expect('#')\n\n",
        ]
    
    def _generate_directive_code(self, directive: Directive) -> List[str]:
        """Generate code for a single directive."""
        handlers = {
            DirectiveType.MARKER: self._gen_marker,
            DirectiveType.COMMENT: self._gen_comment,
            DirectiveType.PERMAPROMPT: self._gen_permaprompt,
            DirectiveType.PROMPT: self._gen_prompt,
            DirectiveType.ONERROR: self._gen_onerror,
            DirectiveType.REPORT: self._gen_report,
            DirectiveType.SAVE: self._gen_save,
            DirectiveType.RSAVE: self._gen_rsave,
            DirectiveType.INCLUDE: self._gen_include,
            DirectiveType.PY: self._gen_py,
            DirectiveType.QUERY: self._gen_query,
            DirectiveType.SILENT: self._gen_silent,
            DirectiveType.CLI_COMMAND: self._gen_cli_command,
        }
        
        handler = handlers.get(directive.type)
        if handler:
            return handler(directive)
        return []
    
    def _gen_marker(self, d: Directive) -> List[str]:
        """Handle internal markers."""
        if d.value == 'END_BEGIN_SECTION':
            return ["buffer = ''  # Clear init commands\n"]
        return []
    
    def _gen_comment(self, d: Directive) -> List[str]:
        """Comments are skipped in code generation."""
        return []
    
    def _gen_permaprompt(self, d: Directive) -> List[str]:
        """Generate @PERMAPROMPT code."""
        return [
            f"prompts['PERMAPROMPT'] = '{d.prompt_pattern}'\n",
            "prompt_list = prompts['PERMAPROMPT'].split('|')\n",
        ]
    
    def _gen_prompt(self, d: Directive) -> List[str]:
        """Generate @PROMPT/@RESPONSE code."""
        lines = []
        prompt = d.prompt_pattern
        response = d.response or ''
        
        lines.append(f"child.expect('{prompt}')\n")
        lines.append(f"child.sendline('{response}')\n")
        lines.append(f"log_output('{response}\\n')\n")
        lines.append("child.logfile = None\n")
        lines.append("try:\n")
        lines.append("    child.expect(prompt_list)\n")
        lines.append("    output = child.before.decode('utf-8')\n")
        lines.append("    matched_prompt = child.after.decode('utf-8')\n")
        lines.append(f"    cmd_to_strip = '{response}'\n")
        lines.append("    output_lines = output.split('\\n')\n")
        lines.append("    filtered_lines = [l for l in output_lines if l.strip() != cmd_to_strip]\n")
        lines.append("    output = '\\n'.join(filtered_lines)\n")
        lines.append("    print(output, end='', flush=True)\n")
        lines.append("    print(matched_prompt, end='', flush=True)\n")
        lines.append("    log_output(output + matched_prompt)\n")
        lines.append(f"    buffer += '{response}\\n' + output + matched_prompt + '\\n'\n")
        lines.append("    check_errors(output)\n")
        lines.append("except pexpect.EOF:\n")
        lines.append("    output = child.before.decode('utf-8') if child.before else ''\n")
        lines.append(f"    cmd_to_strip = '{response}'\n")
        lines.append("    output_lines = output.split('\\n')\n")
        lines.append("    filtered_lines = [l for l in output_lines if l.strip() != cmd_to_strip]\n")
        lines.append("    output = '\\n'.join(filtered_lines)\n")
        lines.append("    print(output, end='', flush=True)\n")
        lines.append("    log_output(output)\n")
        lines.append(f"    buffer += '{response}\\n' + output + '\\n'\n")
        lines.append("    pass\n")
        lines.append("except:\n")
        lines.append("    pass  # Other error\n")
        lines.append("child.logfile = sys.stdout.buffer\n")
        
        return lines
    
    def _gen_onerror(self, d: Directive) -> List[str]:
        """@ONERROR is handled with @REPORT."""
        return []
    
    def _gen_report(self, d: Directive) -> List[str]:
        """Generate @ONERROR/@REPORT handler registration."""
        patterns_repr = repr(d.error_patterns)
        format_repr = repr(d.format_string)
        return [f"error_handlers.append(({patterns_repr}, {format_repr}, {d.context_lines}))\n"]
    
    def _gen_save(self, d: Directive) -> List[str]:
        """Generate @SAVE code."""
        return self._gen_save_common(d, generate_txtdb=True)
    
    def _gen_rsave(self, d: Directive) -> List[str]:
        """Generate @RSAVE code."""
        return self._gen_save_common(d, generate_txtdb=False)
    
    def _gen_save_common(self, d: Directive, generate_txtdb: bool) -> List[str]:
        """Common code generation for @SAVE and @RSAVE."""
        lines = []
        filename = d.filename
        
        if d.normalize and d.normalize_pipeline:
            # Escape single quotes in pipeline
            pipeline = d.normalize_pipeline.replace("'", "\\'")
            
            lines.append("# NORMALIZE pipeline\n")
            lines.append("import tempfile\n")
            lines.append("with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:\n")
            lines.append("    tmp.write(buffer)\n")
            lines.append("    tmp_name = tmp.name\n")
            lines.append(f"normalized = bash(f'cat {{tmp_name}} | {pipeline}')\n")
            lines.append("import os\n")
            lines.append("os.unlink(tmp_name)\n")
            
            # Write file
            if '{' in filename and '}' in filename:
                var_match = re.search(r'\{(\w+)\}', filename)
                if var_match:
                    var_name = var_match.group(1)
                    lines.append(f"with open({var_name}, 'w') as f:\n")
                    lines.append("    f.write(normalized)\n")
                    if generate_txtdb:
                        lines.append("txtdb = flatten_to_brontpath(normalized)\n")
                        lines.append(f"with open(f'{{{var_name}}}.txtdb', 'w') as f:\n")
                        lines.append("    f.write(txtdb)\n")
            else:
                lines.append(f"with open('{filename}', 'w') as f:\n")
                lines.append("    f.write(normalized)\n")
                if generate_txtdb:
                    lines.append("txtdb = flatten_to_brontpath(normalized)\n")
                    lines.append(f"with open('{filename}.txtdb', 'w') as f:\n")
                    lines.append("    f.write(txtdb)\n")
        else:
            # No normalize
            if '{' in filename and '}' in filename:
                var_match = re.search(r'\{(\w+)\}', filename)
                if var_match:
                    var_name = var_match.group(1)
                    lines.append(f"with open({var_name}, 'w') as f:\n")
                    lines.append("    f.write(buffer)\n")
                    if generate_txtdb:
                        lines.append("txtdb = flatten_to_brontpath(buffer)\n")
                        lines.append(f"with open(f'{{{var_name}}}.txtdb', 'w') as f:\n")
                        lines.append("    f.write(txtdb)\n")
            else:
                lines.append(f"with open('{filename}', 'w') as f:\n")
                lines.append("    f.write(buffer)\n")
                if generate_txtdb:
                    lines.append("txtdb = flatten_to_brontpath(buffer)\n")
                    lines.append(f"with open('{filename}.txtdb', 'w') as f:\n")
                    lines.append("    f.write(txtdb)\n")
        
        lines.append("buffer = ''\n")
        return lines
    
    def _gen_include(self, d: Directive) -> List[str]:
        """Generate @INCLUDE code."""
        return [
            f"with open('{d.filename}', 'r') as incl:\n",
            "    buffer += incl.read()\n",
        ]
    
    def _gen_py(self, d: Directive) -> List[str]:
        """Generate @PY code."""
        lines = []
        if d.is_multiline:
            for py_line in d.python_code.split('\n'):
                lines.append(f"{py_line}\n")
        else:
            lines.append(f"{d.python_code}\n")
        return lines
    
    def _gen_query(self, d: Directive) -> List[str]:
        """Generate @QUERY code."""
        lines = []
        
        # Extract table names from query
        table_pattern = r'(?:FROM|JOIN)\s+(\w+)'
        tables = re.findall(table_pattern, d.sql_query, re.IGNORECASE)
        
        lines.append(f"query_verbose = {d.is_verbose}\n")
        for table in tables:
            lines.append(f"load_txtdb_to_sqlite('{table}')\n")
        
        if d.has_loop:
            lines.extend(self._gen_query_loop(d))
        else:
            lines.extend(self._gen_query_basic(d))
        
        return lines
    
    def _gen_query_basic(self, d: Directive) -> List[str]:
        """Generate basic @QUERY code (no loop)."""
        lines = []
        lines.append("# Execute query\n")
        lines.append("try:\n")
        lines.append(f"    results = db_cursor.execute('''{d.sql_query}''').fetchall()\n")
        lines.append("    if results:\n")
        lines.append("        # Get column names\n")
        lines.append("        col_names = [desc[0] for desc in db_cursor.description]\n")
        if d.is_verbose:
            lines.append("        # Print header\n")
            lines.append("        print('  '.join(col_names))\n")
            lines.append("        print('-' * (len('  '.join(col_names))))\n")
        lines.append("        # Print rows\n")
        lines.append("        for row in results:\n")
        lines.append("            print('  '.join(str(val) for val in row))\n")
        if d.is_verbose:
            lines.append("        print(f'\\n{len(results)} rows returned')\n")
        lines.append("    else:\n")
        lines.append("        print('No results')\n")
        lines.append("except Exception as e:\n")
        lines.append("    print(f'Query error: {e}')\n")
        return lines
    
    def _gen_query_loop(self, d: Directive) -> List[str]:
        """Generate @QUERY loop code."""
        lines = []
        lines.append("# Execute query with loop\n")
        lines.append("try:\n")
        lines.append(f"    results = db_cursor.execute('''{d.sql_query}''').fetchall()\n")
        lines.append("    col_names = [desc[0] for desc in db_cursor.description]\n")
        if d.is_verbose:
            lines.append("    print(f'Query returned {len(results)} rows')\n")
        lines.append("    for row_idx, row in enumerate(results, 1):\n")
        if d.is_verbose:
            lines.append("        print(f'\\n=== Row {row_idx}/{len(results)} ===')\n")
        lines.append("        # Create variables from row data\n")
        lines.append("        row_vars = {}\n")
        lines.append("        for col_idx, col_name in enumerate(col_names):\n")
        lines.append("            row_vars[col_name] = str(row[col_idx])\n")
        lines.append("            globals()[col_name] = str(row[col_idx])  # Make available as variable\n")
        if d.is_verbose:
            lines.append("            print(f'{col_name} = {row[col_idx]}')\n")
            lines.append("        print()\n")
        
        # Process loop body
        if d.loop_body:
            for loop_dir in d.loop_body:
                loop_code = self._gen_loop_body_directive(loop_dir)
                lines.extend(loop_code)
        
        if d.is_verbose:
            lines.append("    print(f'\\nProcessed {len(results)} rows')\n")
        lines.append("except Exception as e:\n")
        lines.append("    print(f'Query error: {e}')\n")
        return lines
    
    def _gen_loop_body_directive(self, d: Directive) -> List[str]:
        """Generate code for directive inside @QUERY loop."""
        lines = []
        indent = "        "  # Inside for loop
        
        if d.type == DirectiveType.COMMENT:
            return []
        
        if d.type == DirectiveType.PY:
            lines.append(f"{indent}{d.python_code}\n")
        
        elif d.type in (DirectiveType.SAVE, DirectiveType.RSAVE):
            is_rsave = d.type == DirectiveType.RSAVE
            filename_template = d.filename
            
            lines.append(f"{indent}# {d.raw_line.strip()}\n")
            lines.append(f"{indent}filename = f'{filename_template}'.format(**row_vars)\n")
            
            if d.normalize and d.normalize_pipeline:
                pipeline = d.normalize_pipeline.replace("'", "\\'")
                lines.append(f"{indent}import tempfile\n")
                lines.append(f"{indent}with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:\n")
                lines.append(f"{indent}    tmp.write(buffer)\n")
                lines.append(f"{indent}    tmp_name = tmp.name\n")
                lines.append(f"{indent}normalized = bash(f'cat {{tmp_name}} | {pipeline}')\n")
                lines.append(f"{indent}import os\n")
                lines.append(f"{indent}os.unlink(tmp_name)\n")
                
                lines.append(f"{indent}with open(filename, 'w') as f:\n")
                lines.append(f"{indent}    f.write(normalized)\n")
                if not is_rsave:
                    lines.append(f"{indent}txtdb = flatten_to_brontpath(normalized)\n")
                    lines.append(f"{indent}with open(f'{{filename}}.txtdb', 'w') as f:\n")
                    lines.append(f"{indent}    f.write(txtdb)\n")
            else:
                lines.append(f"{indent}with open(filename, 'w') as f:\n")
                lines.append(f"{indent}    f.write(buffer)\n")
                if not is_rsave:
                    lines.append(f"{indent}txtdb = flatten_to_brontpath(buffer)\n")
                    lines.append(f"{indent}with open(f'{{filename}}.txtdb', 'w') as f:\n")
                    lines.append(f"{indent}    f.write(txtdb)\n")
            
            lines.append(f"{indent}buffer = ''\n")
        
        elif d.type in (DirectiveType.CLI_COMMAND, DirectiveType.SILENT):
            is_silent = d.type == DirectiveType.SILENT
            cmd = d.silent_command if is_silent else d.value
            
            lines.append(f"{indent}cmd = f'{cmd}'.format(**row_vars)\n")
            if is_silent:
                lines.append(f"{indent}child.logfile = None\n")
            lines.append(f"{indent}child.sendline(cmd)\n")
            lines.append(f"{indent}log_output(cmd + '\\n')\n")
            if not is_silent:
                lines.append(f"{indent}child.logfile = None\n")
            lines.append(f"{indent}try:\n")
            lines.append(f"{indent}    child.expect(prompt_list)\n")
            lines.append(f"{indent}    output = child.before.decode('utf-8')\n")
            lines.append(f"{indent}    matched_prompt = child.after.decode('utf-8')\n")
            lines.append(f"{indent}    output_lines = output.split('\\n')\n")
            lines.append(f"{indent}    filtered_lines = [l for l in output_lines if l.strip() != cmd]\n")
            lines.append(f"{indent}    output = '\\n'.join(filtered_lines)\n")
            if not is_silent:
                lines.append(f"{indent}    print(output, end='', flush=True)\n")
                lines.append(f"{indent}    print(matched_prompt, end='', flush=True)\n")
            lines.append(f"{indent}    log_output(output + matched_prompt)\n")
            lines.append(f"{indent}    buffer += cmd + '\\n' + output + matched_prompt + '\\n'\n")
            lines.append(f"{indent}    check_errors(output)\n")
            lines.append(f"{indent}except pexpect.EOF:\n")
            lines.append(f"{indent}    output = child.before.decode('utf-8') if child.before else ''\n")
            lines.append(f"{indent}    filtered_lines = [l for l in output.split('\\n') if l.strip() != cmd]\n")
            lines.append(f"{indent}    output = '\\n'.join(filtered_lines)\n")
            if not is_silent:
                lines.append(f"{indent}    print(output, end='', flush=True)\n")
            lines.append(f"{indent}    log_output(output)\n")
            lines.append(f"{indent}    buffer += cmd + '\\n' + output + '\\n'\n")
            lines.append(f"{indent}except:\n")
            lines.append(f"{indent}    pass\n")
            lines.append(f"{indent}child.logfile = sys.stdout.buffer\n")
        
        return lines
    
    def _gen_silent(self, d: Directive) -> List[str]:
        """Generate @SILENT command code."""
        return self._gen_cli_common(d.silent_command, is_silent=True)
    
    def _gen_cli_command(self, d: Directive) -> List[str]:
        """Generate CLI command code."""
        return self._gen_cli_common(d.value, is_silent=False)
    
    def _gen_cli_common(self, command: str, is_silent: bool) -> List[str]:
        """Common code for CLI command execution."""
        lines = []
        
        if is_silent:
            lines.append("child.logfile = None\n")
        
        lines.append(f"child.sendline('{command}')\n")
        lines.append(f"log_output('{command}\\n')\n")
        
        if not is_silent:
            lines.append("child.logfile = None\n")
        
        lines.append("try:\n")
        lines.append("    child.expect(prompt_list)\n")
        lines.append("    output = child.before.decode('utf-8')\n")
        lines.append("    matched_prompt = child.after.decode('utf-8')\n")
        lines.append(f"    cmd_to_strip = '{command}'\n")
        lines.append("    output_lines = output.split('\\n')\n")
        lines.append("    filtered_lines = [l for l in output_lines if l.strip() != cmd_to_strip]\n")
        lines.append("    output = '\\n'.join(filtered_lines)\n")
        
        if not is_silent:
            lines.append("    print(output, end='', flush=True)\n")
            lines.append("    print(matched_prompt, end='', flush=True)\n")
        
        lines.append("    log_output(output + matched_prompt)\n")
        lines.append(f"    buffer += '{command}\\n' + output + matched_prompt + '\\n'\n")
        lines.append("    check_errors(output)\n")
        lines.append("except pexpect.EOF:\n")
        lines.append("    # Connection closed (e.g., exit command)\n")
        lines.append("    output = child.before.decode('utf-8') if child.before else ''\n")
        lines.append(f"    cmd_to_strip = '{command}'\n")
        lines.append("    output_lines = output.split('\\n')\n")
        lines.append("    filtered_lines = [l for l in output_lines if l.strip() != cmd_to_strip]\n")
        lines.append("    output = '\\n'.join(filtered_lines)\n")
        
        if not is_silent:
            lines.append("    print(output, end='', flush=True)\n")
        
        lines.append("    log_output(output)\n")
        lines.append(f"    buffer += '{command}\\n' + output + '\\n'\n")
        lines.append("    pass  # Connection closed, stop processing\n")
        lines.append("except:\n")
        lines.append("    pass  # Other error, continue\n")
        lines.append("child.logfile = sys.stdout.buffer\n")
        
        return lines
    
    def _generate_cleanup(self) -> List[str]:
        """Generate cleanup and summary code."""
        return [
            "\nchild.close()\n",
            "\n# Print summary of generated logs and directories\n",
            "print(f'\\n=== Session Complete ===')\n",
            "print(f'Work dir:    {run_dir}')\n",
            "print(f'Log dir:     {log_path}')\n",
            "print(f'Script log:  {bront_log}')\n",
            "print(f'Output log:  {output_log}')\n",
            "if error_buffer:\n",
            "    print(f'Error log:   {error_log} (ERRORS DETECTED)')\n",
            "    print(f'\\n=== ERROR DETAILS ===')\n",
            "    print(error_buffer)\n",
            "else:\n",
            "    print(f'Error log:   {error_log} (no errors)')\n",
        ]
    
    def _get_flatten_function(self) -> str:
        """Get the flatten_to_brontpath function code."""
        return """
def flatten_to_brontpath(output, prefix=''):
    lines = output.strip().split('\\n')
    brontpaths = []
    current_prefix = prefix
    
    for line in lines:
        is_indented = len(line) > 0 and line[0] in (' ', '\\t')
        stripped_line = re.sub(r'^\\s*', '', line)
        
        if stripped_line:
            words = re.split(r'\\s+', stripped_line)
            path = '|'.join(words)
            
            if is_indented:
                full_path = f"{current_prefix}|{path}" if current_prefix else path
            else:
                full_path = f"{prefix}|{path}" if prefix else path
                current_prefix = full_path
            
            full_path += f"|{line}"
            brontpaths.append(full_path)
    
    return '\\n'.join(brontpaths)
"""
