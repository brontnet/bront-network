# bront.network - Bront Executor
# Bront Language v3.6

"""
Runtime executor for Bront language.

Executes parsed directives directly without generating intermediate Python.
Used primarily by Ansible module for direct execution.

For standalone mode, use the code generator to produce a Python script.

**Phase 1 Refactoring**: Now uses driver pattern for multi-backend support.
Supports pexpect (default), netmiko, and scrapli drivers.
"""

import os
import re
import signal
import sqlite3
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

from .parser import Directive, DirectiveType
from .brontpath import flatten_to_brontpath
from .drivers import get_driver, DriverFactory
from .drivers.base import BaseDriver


class BrontExecutor:
    """
    Execute Bront directives directly.
    
    This executor runs parsed directives without generating intermediate
    Python code. It's used primarily by the Ansible module.
    
    Usage:
        executor = BrontExecutor(device_info, config, output_mode='ansible')
        result = executor.execute(directives)
    """
    
    def __init__(self, device_info: Dict[str, Any], config: Dict[str, Any],
                 output_mode: str = 'ansible', dry_run: bool = False,
                 driver_name: Optional[str] = None, script_vars: Optional[Dict[str, Any]] = None,
                 run_id: Optional[str] = None):
        """
        Initialize executor.
        
        Args:
            device_info: Device connection info
            config: Bront configuration
            output_mode: 'console' for stdout output, 'ansible' for structured return
            dry_run: If True, @DRYRUN commands are echoed instead of executed
            driver_name: Optional driver selection ('pexpect', 'netmiko', 'scrapli')
            script_vars: Optional custom variables to make available in @PY
            run_id: Optional shared run ID for unified directory structure across devices
        """
        self.device_info = device_info
        self.config = config
        self.output_mode = output_mode
        self.dry_run = dry_run
        self.hostname = device_info.get('hostname', 'DEVICE')
        self.script_vars = script_vars or {}
        self.run_id = run_id
        
        # Create connection driver
        self.driver: BaseDriver = get_driver(
            device_info, config, output_mode, driver_name
        )
        
        # Runtime state
        self.buffer = ''
        self.error_buffer = ''
        self.prompt_list = []
        self.error_handlers = []
        self.onprompt_handlers = []  # Global @ONPROMPT/@RESPONSE pairs
        self.output_log_path = None
        self.error_log_path = None
        
        # SQLite for @QUERY
        self.db_conn = sqlite3.connect(':memory:')
        self.db_cursor = self.db_conn.cursor()
        self.loaded_tables = set()
        self.query_verbose = False
        
        # @DIAGNOSTICS mode - timestamps for each command
        self.diagnostics_enabled = False
        
        # Results for Ansible
        self.results = {
            'changed': False,
            'output': '',
            'errors': [],
            'findings': [],
        }
        
        # Full output accumulator (never cleared, unlike buffer)
        self.full_output = ''
        
        # Persistent namespace for @PY execution
        def safe_bash(cmd):
            """Safe bash execution that handles I/O errors."""
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    stdin=subprocess.DEVNULL  # Prevent stdin issues
                )
                return result.stdout.strip()
            except Exception as e:
                # Return error message instead of crashing
                return f"[bash error: {str(e)}]"
        
        self.py_globals = {
            'bash': safe_bash,
            'device_name': self.hostname,
            'hostname': self.hostname,
            'host': self.device_info.get('host', ''),
            're': re,  # Make re module available
            'send': self._py_send,  # Send command to device
            'expect': self._py_expect,  # Wait for pattern
            'report': self._py_report,  # Emit structured finding
            'driver': self.driver,  # Direct access to driver for advanced usage
            'enable_password': self.device_info.get('enable_password', 
                                                     self.device_info.get('password', '')),
        }
        
        # Add custom script variables to py_globals
        if self.script_vars:
            self.py_globals.update(self.script_vars)
        
        # In ansible mode, capture print to buffer instead of stdout
        if self.output_mode == 'ansible':
            self.py_globals['print'] = lambda *args, **kwargs: self._capture_print(*args, **kwargs)
        
        # Setup directories
        self._setup_directories()
    
    def _setup_directories(self):
        """Setup work and log directories.
        
        If run_id is provided, uses unified directory structure:
            workdir/run_id/hostname/     (device work files)
            logdir/run_id/               (all device logs)
        
        If no run_id, uses legacy per-device structure:
            workdir/hostname_timestamp_uuid/
            logdir/[timestamp_subdirs/]
        """
        try:
            workdir = self.config.get('WORKDIR', os.path.join(os.getcwd(), 'bront_work'))
            logdir = self.config.get('LOGDIR', os.path.join(os.getcwd(), 'bront_logs'))
            timestamp_subdirs = self.config.get('timestamp_subdirs', False)
            
            if self.run_id:
                # Unified directory structure under run_id
                self.run_dir = os.path.join(workdir, self.run_id, self.hostname)
                os.makedirs(self.run_dir, exist_ok=True)
                self.run_dir = os.path.abspath(self.run_dir)
                
                # Logs under run_id
                self.log_path = os.path.join(logdir, self.run_id)
                self.log_path = os.path.abspath(self.log_path)
                os.makedirs(self.log_path, exist_ok=True)
                
                # Findings directory at run level (shared across devices)
                self.findings_dir = os.path.join(workdir, self.run_id)
                os.makedirs(self.findings_dir, exist_ok=True)
                self.findings_dir = os.path.abspath(self.findings_dir)
                
                # Log file paths use hostname prefix (no uuid needed)
                self.error_log_path = os.path.join(self.log_path, f'{self.hostname}_error.log')
                self.output_log_path = os.path.join(self.log_path, f'{self.hostname}_output.log')
                self.bront_log_path = os.path.join(self.log_path, f'{self.hostname}_bront.log')
            else:
                # Legacy per-device structure
                log_uuid = str(uuid.uuid4())[:8]
                log_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.run_id = f'{self.hostname}_{log_timestamp}_{log_uuid}'
                self.findings_dir = None
                
                # Create run directory
                self.run_dir = os.path.join(workdir, self.run_id)
                os.makedirs(self.run_dir, exist_ok=True)
                self.run_dir = os.path.abspath(self.run_dir)
                
                # Create log directory
                if timestamp_subdirs:
                    log_subdir = datetime.now().strftime('%Y/%m/%d')
                    self.log_path = os.path.join(logdir, log_subdir)
                else:
                    self.log_path = logdir
                self.log_path = os.path.abspath(self.log_path)
                os.makedirs(self.log_path, exist_ok=True)
                
                # Log file paths
                self.error_log_path = os.path.join(self.log_path, f'{self.run_id}_error.log')
                self.output_log_path = os.path.join(self.log_path, f'{self.run_id}_output.log')
                self.bront_log_path = os.path.join(self.log_path, f'{self.run_id}_bront.log')
        except (OSError, IOError) as e:
            # Directory setup failed - use /tmp fallback
            import tempfile
            if not self.run_id:
                self.run_id = f'{self.hostname}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            self.findings_dir = None
            self.run_dir = tempfile.mkdtemp(prefix=f'bront_{self.run_id}_{self.hostname}_')
            self.log_path = self.run_dir
            self.error_log_path = os.path.join(self.log_path, f'{self.hostname}_error.log')
            self.output_log_path = os.path.join(self.log_path, f'{self.hostname}_output.log')
            self.bront_log_path = os.path.join(self.log_path, f'{self.hostname}_bront.log')
    
    def execute(self, directives: List[Directive]) -> Dict[str, Any]:
        """
        Execute a list of directives.
        
        Args:
            directives: List of parsed Directive objects
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Extract @PERMAPROMPT if present and set on driver before connecting
            for directive in directives:
                if directive.type == DirectiveType.PERMAPROMPT:
                    prompt_patterns = directive.prompt_pattern.split('|')
                    if hasattr(self.driver, 'set_prompt_patterns'):
                        self.driver.set_prompt_patterns(prompt_patterns)
                    break  # Use first @PERMAPROMPT found
            
            # Connect to device using driver
            self.driver.connect()
            
            # Capture connection buffer (login banner, etc.)
            connection_output = self.driver.get_buffer()
            if connection_output:
                connection_output = connection_output.replace('\r', '')
                self.buffer += connection_output
                self.full_output += connection_output
            
            # Change to run directory
            original_dir = os.getcwd()
            os.chdir(self.run_dir)
            
            # Execute directives
            for directive in directives:
                self._execute_directive(directive)
            
            # Cleanup
            self.driver.disconnect()
            
            os.chdir(original_dir)
            
            # Finalize results - read full output from log file
            if self.output_log_path and os.path.exists(self.output_log_path):
                with open(self.output_log_path, 'r') as f:
                    self.results['output'] = f.read()
            else:
                self.results['output'] = self.full_output
            
            # Add run metadata
            self.results['run_id'] = self.run_id
            self.results['device'] = self.hostname
            
            # Write per-device findings file
            if self.findings_dir and self.results['findings']:
                self._write_device_findings()
            
        except Exception as e:
            self.results['failed'] = True
            self.results['msg'] = str(e)
            if self.driver.is_alive():
                self.driver.disconnect()
        
        return self.results
    
    def _py_send(self, command: str, silent: bool = False):
        """Send command to device (for use in @PY blocks)."""
        # For pexpect driver, use raw methods for maximum control
        if self.driver.driver_name == 'pexpect':
            self.driver.raw_sendline(command)
        else:
            # For other drivers, use standard send_command
            self.driver.send_command(command, expect_prompt=False)
        
        if not silent:
            self._log_output(command + '\n')
    
    def _py_expect(self, pattern: str):
        """Wait for pattern and capture output (for use in @PY blocks)."""
        before, match = self.driver.expect_pattern(pattern)
        
        # Add to buffers
        output = before + match
        self.buffer += output
        self.full_output += output
        self._log_output(output)
        
        # Update buffer in py_globals
        self.py_globals['buffer'] = self.buffer

    def _py_report(self, message: str, severity: str = 'high', detail: dict = None):
        """
        Emit a structured finding from @PY code.
        
        Usage in @PY blocks:
            report("Disk space low", severity="high")
            report(f"Free space {hdspace}kB on {device_name}", severity="medium", 
                   detail={"metric": "disk_free", "value": hdspace})
        
        Args:
            message: Finding description
            severity: high, medium, low, or info (default: high)
            detail: Optional dict with additional context
        """
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        finding = {
            'run_id': self.run_id,
            'device': self.hostname,
            'source': 'py',
            'severity': severity,
            'command': '@PY',
            'finding': message,
            'detail': detail or {},
            'timestamp': timestamp,
        }
        self.results['findings'].append(finding)
        
        # Also log to error buffer and error log (same as @REPORT)
        log_entry = f"[{timestamp}] [{severity.upper()}] {message}\n"
        self.error_buffer += log_entry
        self.results['errors'].append(message)
        
        if self.error_log_path:
            try:
                with open(self.error_log_path, 'a') as f:
                    f.write(log_entry)
            except (OSError, IOError):
                pass
        
        # Print in console mode
        if self.output_mode == 'console':
            print(f"  [FINDING/{severity.upper()}] {message}")

    
    def _execute_directive(self, directive: Directive):
        """Execute a single directive."""
        handlers = {
            DirectiveType.MARKER: self._exec_marker,
            DirectiveType.PERMAPROMPT: self._exec_permaprompt,
            DirectiveType.PROMPT: self._exec_prompt,
            DirectiveType.ONPROMPT: self._exec_onprompt,
            DirectiveType.REPORT: self._exec_report,
            DirectiveType.SAVE: self._exec_save,
            DirectiveType.RSAVE: self._exec_rsave,
            DirectiveType.INCLUDE: self._exec_include,
            DirectiveType.DRYRUN: self._exec_dryrun,
            DirectiveType.DIAGNOSTICS: self._exec_diagnostics,
            DirectiveType.PY: self._exec_py,
            DirectiveType.PYBLOCK: self._exec_pyblock,
            DirectiveType.QUERY: self._exec_query,
            DirectiveType.SILENT: self._exec_silent,
            DirectiveType.CLI_COMMAND: self._exec_cli,
        }
        
        handler = handlers.get(directive.type)
        if handler:
            handler(directive)
    
    def _exec_marker(self, d: Directive):
        """Handle markers."""
        if d.value == 'END_BEGIN_SECTION':
            self.buffer = ''
    
    def _exec_permaprompt(self, d: Directive):
        """Execute @PERMAPROMPT."""
        self.prompt_list = d.prompt_pattern.split('|')
        # Set prompt patterns on driver if supported (pexpect driver)
        if hasattr(self.driver, 'set_prompt_patterns'):
            self.driver.set_prompt_patterns(self.prompt_list)
    
    def _exec_prompt(self, d: Directive):
        """Execute @PROMPT with response."""
        output = self.driver.send_interactive(
            command='',  # No initial command, just expect pattern
            expect_pattern=d.prompt_pattern,
            response=d.response
        )
        self._log_output(output)
        self.buffer += output
        self.full_output += output
    
    def _exec_onprompt(self, d: Directive):
        """Register @ONPROMPT/@RESPONSE global watcher."""
        self.onprompt_handlers.append((d.prompt_pattern, d.response))
        if hasattr(self.driver, 'set_onprompt_handlers'):
            self.driver.set_onprompt_handlers(self.onprompt_handlers)
    
    def _exec_report(self, d: Directive):
        """Register error handler from @ONERROR/@REPORT."""
        # Extract severity (default: high)
        severity = getattr(d, 'severity', 'high') or 'high'
        self.error_handlers.append((d.error_patterns, d.format_string, d.context_lines, severity))
    
    def _exec_diagnostics(self, d: Directive):
        """Enable @DIAGNOSTICS mode - timestamps for each command."""
        self.diagnostics_enabled = True
    
    def _exec_save(self, d: Directive):
        """Execute @SAVE."""
        self._save_buffer(d, generate_txtdb=True)
    
    def _exec_rsave(self, d: Directive):
        """Execute @RSAVE."""
        self._save_buffer(d, generate_txtdb=False)
    
    def _save_buffer(self, d: Directive, generate_txtdb: bool):
        """Common save implementation."""
        content = self.buffer
        filename = d.filename
        
        # Strip carriage returns from SSH output
        content = content.replace('\r', '')
        
        # Handle variable substitution in filename
        if '{' in filename and '}' in filename:
            filename = filename.format(**self.py_globals)
        
        # Apply normalize pipeline if specified
        if d.normalize and d.normalize_pipeline:
            content = self._run_normalize_pipeline(content, d.normalize_pipeline)
        
        # Write main file
        with open(filename, 'w') as f:
            f.write(content)
        self.results['changed'] = True
        
        # Write txtdb if requested
        if generate_txtdb:
            txtdb_content = flatten_to_brontpath(content)
            txtdb_filename = f'{filename}.txtdb'
            with open(txtdb_filename, 'w') as f:
                f.write(txtdb_content)
        
        self.buffer = ''
    
    def _run_normalize_pipeline(self, content: str, pipeline: str) -> str:
        """Run normalize pipeline on content."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:
            tmp.write(content)
            tmp_name = tmp.name
        
        result = subprocess.getoutput(f'cat {tmp_name} | {pipeline}')
        os.unlink(tmp_name)
        return result
    
    def _exec_include(self, d: Directive):
        """Execute @INCLUDE."""
        with open(d.filename, 'r') as f:
            self.buffer += f.read()
    
    def _exec_dryrun(self, d: Directive):
        """Execute @DRYRUN - echo or execute based on dry_run mode."""
        # Get list of commands
        if d.dryrun_commands:
            commands = d.dryrun_commands
        elif d.dryrun_command:
            commands = [d.dryrun_command]
        else:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        for command in commands:
            if self.dry_run:
                # Echo only - don't send to device
                msg = f"++++++++ {timestamp}: DRY-RUN SKIP: {command}"
                if self.output_mode == 'console':
                    print(msg)
                self.buffer += msg + '\n'
                self.full_output += msg + '\n'
                self._log_output(msg + '\n')
            else:
                # Normal execution
                self._send_command(command)
    
    def _exec_py(self, d: Directive):
        """Execute @PY."""
        # Update buffer in namespace
        self.py_globals['buffer'] = self.buffer
        exec(d.python_code, self.py_globals)
        self.buffer = self.py_globals.get('buffer', self.buffer)
    
    def _exec_pyblock(self, d: Directive):
        """Execute @PY block (if/for/while/elif/else)."""
        # Update buffer in namespace
        self.py_globals['buffer'] = self.buffer
        
        block_type = d.py_block_type
        condition = d.py_condition
        body = d.body or []
        
        if block_type == 'if':
            # Evaluate condition
            result = eval(condition, self.py_globals)
            if result:
                self._execute_body(body)
        
        elif block_type == 'elif':
            # elif is handled as part of if chain - evaluate condition
            result = eval(condition, self.py_globals)
            if result:
                self._execute_body(body)
        
        elif block_type == 'else':
            # else always executes (condition checking happens at if/elif level)
            self._execute_body(body)
        
        elif block_type == 'for':
            # Parse "var in iterable" from condition
            match = re.match(r'(\w+)\s+in\s+(.+)', condition)
            if match:
                var_name = match.group(1)
                iterable_expr = match.group(2)
                iterable = eval(iterable_expr, self.py_globals)
                
                # Filter out empty strings — protects against "".split('\n') → ['']
                if isinstance(iterable, list):
                    iterable = [x for x in iterable if x != '']
                
                for item in iterable:
                    self.py_globals[var_name] = item
                    self._execute_body(body)
        
        elif block_type == 'while':
            # While loop
            while eval(condition, self.py_globals):
                self._execute_body(body)
        
        # Update buffer from namespace
        self.buffer = self.py_globals.get('buffer', self.buffer)
    
    def _execute_body(self, body: List[Directive]):
        """Execute a list of directives (block body)."""
        for directive in body:
            self._execute_directive(directive)
    
    def _substitute_py_vars(self, text: str) -> str:
        """Substitute $var and {var} references with Python variable values."""
        # Handle $var syntax
        def replace_dollar_var(match):
            var_name = match.group(1)
            if var_name in self.py_globals:
                return str(self.py_globals[var_name])
            return match.group(0)  # Keep original if not found
        
        text = re.sub(r'\$(\w+)', replace_dollar_var, text)
        
        # Handle {var} syntax — only replace if var exists in namespace
        def replace_brace_var(match):
            var_name = match.group(1)
            if var_name in self.py_globals:
                return str(self.py_globals[var_name])
            return match.group(0)  # Keep original if not found
        
        text = re.sub(r'\{(\w+)\}', replace_brace_var, text)
        
        return text
    
    def _exec_query(self, d: Directive):
        """Execute @QUERY."""
        self.query_verbose = d.is_verbose
        
        # Load required tables
        table_pattern = r'(?:FROM|JOIN)\s+(\w+)'
        tables = re.findall(table_pattern, d.sql_query, re.IGNORECASE)
        for table in tables:
            self._load_txtdb(table)
        
        # Execute query
        try:
            results = self.db_cursor.execute(d.sql_query).fetchall()
            col_names = [desc[0] for desc in self.db_cursor.description]
            
            if d.has_loop and d.loop_body:
                # Execute loop body for each row
                for row_idx, row in enumerate(results, 1):
                    row_vars = {}
                    for col_idx, col_name in enumerate(col_names):
                        row_vars[col_name] = str(row[col_idx])
                        globals()[col_name] = str(row[col_idx])
                    
                    for loop_directive in d.loop_body:
                        self._execute_loop_directive(loop_directive, row_vars)
            else:
                # Basic query - just print results
                if self.output_mode == 'console':
                    for row in results:
                        print('  '.join(str(val) for val in row))
                        
        except Exception as e:
            self.results['errors'].append(f'Query error: {e}')
    
    def _execute_loop_directive(self, d: Directive, row_vars: Dict[str, str]):
        """Execute directive inside @QUERY loop."""
        if d.type == DirectiveType.PY:
            # Use the same safe_bash function
            def safe_bash(cmd):
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True,
                        timeout=30, stdin=subprocess.DEVNULL
                    )
                    return result.stdout.strip()
                except Exception as e:
                    return f"[bash error: {str(e)}]"
            
            # Build execution globals - use self.py_globals as base to get safe print()
            exec_globals = self.py_globals.copy()
            exec_globals.update({'buffer': self.buffer, 'bash': safe_bash})
            exec_globals.update(row_vars)
            exec(d.python_code, exec_globals)
            self.buffer = exec_globals.get('buffer', self.buffer)
            
        elif d.type in (DirectiveType.SAVE, DirectiveType.RSAVE):
            filename = d.filename.format(**row_vars)
            content = self.buffer.replace('\r', '')
            
            if d.normalize and d.normalize_pipeline:
                content = self._run_normalize_pipeline(content, d.normalize_pipeline)
            
            with open(filename, 'w') as f:
                f.write(content)
            self.results['changed'] = True
            
            if d.type == DirectiveType.SAVE:
                txtdb_content = flatten_to_brontpath(content)
                with open(f'{filename}.txtdb', 'w') as f:
                    f.write(txtdb_content)
            
            self.buffer = ''
            
        elif d.type in (DirectiveType.CLI_COMMAND, DirectiveType.SILENT):
            cmd = (d.silent_command if d.type == DirectiveType.SILENT else d.value)
            cmd = cmd.format(**row_vars)
            is_silent = d.type == DirectiveType.SILENT
            self._send_command(cmd, is_silent)
    
    def _exec_silent(self, d: Directive):
        """Execute @SILENT command."""
        cmd = self._substitute_py_vars(d.silent_command)
        self._send_command(cmd, is_silent=True)
    
    def _exec_cli(self, d: Directive):
        """Execute CLI command."""
        cmd = self._substitute_py_vars(d.value)
        self._send_command(cmd, is_silent=False)
    
    def _send_command(self, command: str, is_silent: bool = False):
        """Send command and capture output using driver."""
        # Check if this is a logout/exit command that will close the connection
        logout_commands = {'exit', 'logout', 'quit', 'disconnect'}
        is_logout = command.strip().lower() in logout_commands
        
        # Diagnostics: record start time and emit CMD_START
        if self.diagnostics_enabled and not is_silent:
            start_time = datetime.now()
            start_ts = start_time.strftime('%Y-%m-%d %H:%M:%S.%f')
            diag_start = f"\n### {start_ts} CMD_START 0.0s {command}\n"
            self._log_output(diag_start)
            self.buffer += diag_start
            self.full_output += diag_start
            # Print to console in console mode
            if self.output_mode == 'console':
                print(diag_start, end='')
        
        try:
            # Suppress driver console output for @SILENT commands
            if is_silent and self.output_mode == 'console':
                self.driver.output_mode = 'ansible'
            
            if is_logout:
                # For logout commands, send without expecting prompt
                # The connection will close, so we can't wait for a prompt
                output = self.driver.send_command(command, expect_prompt=False)
            else:
                output = self.driver.send_command(command, expect_prompt=True)
            
            # Strip carriage returns from SSH output
            output = output.replace('\r', '')
            
            # Diagnostics: emit CMD_END with duration
            if self.diagnostics_enabled:
                end_time = datetime.now()
                end_ts = end_time.strftime('%Y-%m-%d %H:%M:%S.%f')
                duration = (end_time - start_time).total_seconds()
                diag_end = f"\n### {end_ts} CMD_END {duration:.6f}s {command}\n"
            
            # Log the command AND output to file
            if not is_silent:
                self._log_output(command + '\n' + output)
            
            # Update buffers — always update buffer (needed for @SAVE)
            # but only update full_output and console when not silent
            self.buffer += command + '\n' + output
            if not is_silent:
                self.full_output += command + '\n' + output
            
            # Diagnostics: append CMD_END after output
            if self.diagnostics_enabled and not is_silent:
                self._log_output(diag_end)
                self.buffer += diag_end
                self.full_output += diag_end
                # Print to console in console mode
                if self.output_mode == 'console':
                    print(diag_end, end='')
            
            # Check for errors (skip for logout commands)
            if not is_logout:
                self._check_errors(output, command)
                
        except (OSError, IOError) as e:
            # Handle I/O errors gracefully (especially for logout commands)
            if is_logout:
                # Expected - connection closed after exit
                self._log_output(command + '\n[connection closed]\n')
                self.buffer += command + '\n'
                self.full_output += command + '\n'
                
                # Diagnostics: emit CMD_END even for logout
                if self.diagnostics_enabled:
                    end_time = datetime.now()
                    end_ts = end_time.strftime('%Y-%m-%d %H:%M:%S.%f')
                    duration = (end_time - start_time).total_seconds()
                    diag_end = f"\n### {end_ts} CMD_END {duration:.6f}s {command}\n"
                    self._log_output(diag_end)
                    self.buffer += diag_end
                    self.full_output += diag_end
                    # Print to console in console mode
                    if self.output_mode == 'console':
                        print(diag_end, end='')
            else:
                # Unexpected I/O error - re-raise
                raise
        
        finally:
            # Restore driver console output after @SILENT
            if is_silent and self.output_mode == 'console':
                self.driver.output_mode = 'console'

    
    def _load_txtdb(self, table_name: str):
        """Load .txtdb file into SQLite."""
        if table_name in self.loaded_tables:
            return
        
        txtdb_file = f'{table_name}.txtdb'
        if not os.path.exists(txtdb_file):
            return
        
        with open(txtdb_file, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return
        
        # Determine columns from first line
        first_line = lines[0].strip()
        fields = first_line.split('|')
        num_cols = len(fields)
        
        col_names = [f'col{i+1}' for i in range(num_cols-1)] + ['original_line']
        col_defs = ', '.join([f'{name} TEXT' for name in col_names])
        
        self.db_cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
        self.db_cursor.execute(f'CREATE TABLE {table_name} ({col_defs})')
        
        placeholders = ', '.join(['?' for _ in range(num_cols)])
        for line in lines:
            fields = line.strip().split('|')
            while len(fields) < num_cols:
                fields.append('')
            self.db_cursor.execute(
                f'INSERT INTO {table_name} VALUES ({placeholders})',
                fields[:num_cols]
            )
        
        self.db_conn.commit()
        self.loaded_tables.add(table_name)
    
    def _check_errors(self, output: str, command: str = ''):
        """Check output against error patterns and emit findings."""
        for handler in self.error_handlers:
            if len(handler) == 4:
                patterns, format_string, context_lines, severity = handler
            else:
                patterns, format_string, context_lines = handler
                severity = 'high'
            for pattern in patterns:
                match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
                if match:
                    matched_text = match.group(0)
                    
                    if context_lines > 0:
                        lines = output.split('\n')
                        for i, line in enumerate(lines):
                            if re.search(pattern, line, re.IGNORECASE):
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                matched_text = '\n'.join(lines[start:end])
                                break
                    
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    report = format_string.replace('%s', matched_text)
                    report = report.replace('%t', timestamp)
                    report = report.replace('%d', self.hostname)
                    
                    log_entry = f"[{timestamp}] {report}\n"
                    self.error_buffer += log_entry
                    self.results['errors'].append(report)
                    
                    # Emit structured finding
                    finding = {
                        'run_id': self.run_id,
                        'device': self.hostname,
                        'source': 'report',
                        'severity': severity,
                        'command': command,
                        'finding': report,
                        'detail': {
                            'pattern': pattern,
                            'matched': matched_text,
                        },
                        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    }
                    self.results['findings'].append(finding)
                    
                    if self.error_log_path:
                        try:
                            with open(self.error_log_path, 'a') as f:
                                f.write(log_entry)
                        except (OSError, IOError):
                            pass
                    
                    break
    
    def _log_output(self, text: str):
        """Log text to output file."""
        if self.output_log_path:
            try:
                with open(self.output_log_path, 'a') as f:
                    f.write(text)
            except (OSError, IOError) as e:
                # Log file writing failed - continue execution
                # Don't re-raise to avoid breaking the entire execution
                pass
    
    def _capture_print(self, *args, **kwargs):
        """Capture print output to buffer (for ansible mode)."""
        end = kwargs.get('end', '\n')
        text = ' '.join(str(a) for a in args) + end
        self.buffer += text
        self.full_output += text
        # Also log to output file so it appears inline in session output
        self._log_output(text)
    
    def _write_device_findings(self):
        """Write per-device findings JSON file.
        
        Each device writes its own findings file to avoid race conditions
        when Ansible runs multiple devices in parallel (forks).
        
        File: workdir/run_id/HOSTNAME_findings.json
        """
        import json
        findings_file = os.path.join(self.findings_dir, f'{self.hostname}_findings.json')
        try:
            with open(findings_file, 'w') as f:
                json.dump(self.results['findings'], f, indent=2)
        except (OSError, IOError):
            pass
    
    @staticmethod
    def merge_findings(run_dir: str, output_format: str = 'json') -> str:
        """Merge all per-device findings into a single file.
        
        Call this after all devices have completed (run_once: true).
        
        Args:
            run_dir: Path to the run_id directory (workdir/run_id/)
            output_format: 'json' or 'csv'
            
        Returns:
            Path to the merged findings file
        """
        import json
        import glob
        
        all_findings = []
        for findings_file in sorted(glob.glob(os.path.join(run_dir, '*_findings.json'))):
            try:
                with open(findings_file, 'r') as f:
                    device_findings = json.load(f)
                all_findings.extend(device_findings)
            except (json.JSONDecodeError, OSError, IOError):
                pass
        
        if output_format == 'csv':
            output_file = os.path.join(run_dir, 'findings.csv')
            if all_findings:
                # CSV header from first finding's keys
                fieldnames = ['run_id', 'device', 'source', 'severity', 
                              'command', 'finding', 'timestamp']
                lines = [','.join(fieldnames)]
                for f in all_findings:
                    row = []
                    for key in fieldnames:
                        val = str(f.get(key, ''))
                        # Escape commas and quotes for CSV
                        if ',' in val or '"' in val or '\n' in val:
                            val = '"' + val.replace('"', '""') + '"'
                        row.append(val)
                    lines.append(','.join(row))
                with open(output_file, 'w') as fh:
                    fh.write('\n'.join(lines) + '\n')
            else:
                with open(output_file, 'w') as fh:
                    fh.write('run_id,device,source,severity,command,finding,timestamp\n')
        else:
            output_file = os.path.join(run_dir, 'findings.json')
            with open(output_file, 'w') as fh:
                json.dump(all_findings, fh, indent=2)
        
        return output_file
