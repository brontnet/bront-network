# bront.network - Pexpect Driver
# Bront Language v3.6

"""
Pexpect-based connection driver.

Provides low-level SSH connection using pexpect for maximum control.
Supports raw expect() and send() for @PY blocks.
"""

import sys
from typing import Dict, Any, Optional, List, Tuple

try:
    import pexpect
    HAS_PEXPECT = True
except ImportError:
    HAS_PEXPECT = False

from .base import BaseDriver


class PexpectDriver(BaseDriver):
    """
    Pexpect-based driver for SSH connections.
    
    Provides low-level access to pexpect session for maximum flexibility.
    Best for scenarios requiring raw expect() and send() control.
    """
    
    def __init__(self, device_info: Dict[str, Any], output_mode: str = 'ansible'):
        """
        Initialize pexpect driver.
        
        Args:
            device_info: Must contain host, username, password; optionally port
            output_mode: 'console' or 'ansible'
        """
        if not HAS_PEXPECT:
            raise ImportError("pexpect is required for PexpectDriver")
        
        super().__init__(device_info, output_mode)
        self.child = None
        self._buffer = ''
        self._current_prompt = None
        self._logfile = None
        self._onprompt_handlers = []  # Global (pattern, response) pairs
        
    @property
    def driver_name(self) -> str:
        """Return driver name."""
        return 'pexpect'
    
    def connect(self) -> None:
        """Establish SSH or telnet connection using pexpect."""
        if self.is_connected:
            return
        
        host = self.device_info['host']
        username = self.device_info['username']
        password = self.device_info['password']
        connection = self.device_info.get('connection', 'ssh').lower()
        
        if connection == 'telnet':
            self._connect_telnet(host, username, password)
        else:
            self._connect_ssh(host, username, password)
        
        self.is_connected = True
    
    def _connect_ssh(self, host: str, username: str, password: str) -> None:
        """Establish SSH connection."""
        port = str(self.device_info.get('port', 22))
        
        # SSH options to avoid interactive prompts
        ssh_options = [
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'PubkeyAuthentication=no',
        ]
        
        # Spawn SSH connection
        ssh_args = ssh_options + [f'{username}@{host}', '-p', port]
        self.child = pexpect.spawn('ssh', args=ssh_args, encoding='utf-8')
        
        # Set logfile if console mode AND stdout is available
        if self.output_mode == 'console':
            try:
                if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer:
                    self.child.logfile = sys.stdout
            except (AttributeError, ValueError, OSError):
                pass
        
        # Wait for password prompt (handle various formats)
        try:
            self.child.expect(r'[Pp]assword:\s*', timeout=30)
        except pexpect.TIMEOUT:
            # Maybe key-based auth or unexpected prompt
            raise RuntimeError(
                f"Timeout waiting for password prompt.\n"
                f"Buffer: {self.child.before[-200:] if self.child.before else '(empty)'}"
            )
        
        # Capture pre-login banner
        if self.child.before:
            self._buffer += self.child.before
        
        # Disable logging during password entry
        saved_logfile = self.child.logfile
        self.child.logfile = None
        self.child.sendline(password)
        self.child.logfile = saved_logfile
        
        # Wait for initial prompt
        self._wait_for_prompt()
    
    def _connect_telnet(self, host: str, username: str, password: str) -> None:
        """Establish telnet connection."""
        port = str(self.device_info.get('port', 23))
        
        # Spawn telnet connection
        self.child = pexpect.spawn('telnet', args=[host, port], encoding='utf-8')
        
        # Set logfile if console mode
        if self.output_mode == 'console':
            try:
                if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer:
                    self.child.logfile = sys.stdout
            except (AttributeError, ValueError, OSError):
                pass
        
        # Wait for username or password prompt
        try:
            index = self.child.expect([
                r'[Uu]sername:\s*',
                r'[Ll]ogin:\s*',
                r'[Pp]assword:\s*',
            ], timeout=30)
        except pexpect.TIMEOUT:
            raise RuntimeError(
                f"Timeout waiting for login prompt (telnet).\n"
                f"Buffer: {self.child.before[-200:] if self.child.before else '(empty)'}"
            )
        
        # Capture pre-login banner
        if self.child.before:
            self._buffer += self.child.before
        
        if index in (0, 1):
            # Got username prompt — send username, wait for password
            self.child.sendline(username)
            try:
                self.child.expect(r'[Pp]assword:\s*', timeout=15)
            except pexpect.TIMEOUT:
                raise RuntimeError(
                    f"Timeout waiting for password prompt after username (telnet).\n"
                    f"Buffer: {self.child.before[-200:] if self.child.before else '(empty)'}"
                )
        
        # Send password (index 2 means we got password prompt directly)
        saved_logfile = self.child.logfile
        self.child.logfile = None
        self.child.sendline(password)
        self.child.logfile = saved_logfile
        
        # Wait for initial prompt
        self._wait_for_prompt()
    
    def _wait_for_prompt(self) -> None:
        """Wait for device prompt after login."""
        # Use configured patterns if available, otherwise use generic pattern
        if hasattr(self, '_prompt_patterns') and self._prompt_patterns:
            prompt_pattern = self._prompt_patterns
        else:
            # Fallback to generic pattern if no @PERMAPROMPT was set
            prompt_pattern = [r'[>#$]']
        
        try:
            self.child.expect(prompt_pattern, timeout=60)
        except pexpect.TIMEOUT:
            raise RuntimeError(
                f"Timeout waiting for device prompt.\n"
                f"Patterns: {prompt_pattern}\n"
                f"Buffer (last 300 chars): {self.child.before[-300:] if self.child.before else '(empty)'}"
            )
        
        # Capture post-login output
        if self.child.before:
            self._buffer += self.child.before
        
        if self.child.after:
            self._buffer += self.child.after
            self._current_prompt = self.child.after
    
    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.child and self.child.isalive():
            self.child.close()
        self.is_connected = False
    
    def send_command(self, command: str, expect_prompt: bool = True) -> str:
        """
        Send command and return output.
        
        Args:
            command: Command to send
            expect_prompt: If True, wait for prompt and return output
            
        Returns:
            Command output (without command echo, with prompt)
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        
        # Disable pexpect's direct logging - we'll handle output ourselves
        saved_logfile = self.child.logfile
        self.child.logfile = None
        
        # Send command
        self.child.sendline(command)
        
        if not expect_prompt:
            # Just send, don't wait
            self.child.logfile = saved_logfile
            return ''
        
        # Wait for prompt
        output = ''
        try:
            # Use generic prompt pattern if no specific prompt set
            prompt_pattern = [r'[>#$]'] if not hasattr(self, '_prompt_patterns') else self._prompt_patterns
            
            # Build combined expect list: onprompt patterns first, then prompt patterns
            onprompt_patterns = [h[0] for h in self._onprompt_handlers]
            combined_patterns = onprompt_patterns + prompt_pattern
            num_onprompt = len(onprompt_patterns)
            
            # Loop to handle multiple onprompt matches before reaching the real prompt
            while True:
                match_index = self.child.expect(combined_patterns)
                
                if match_index < num_onprompt:
                    # Matched an @ONPROMPT pattern — capture output, send response, loop
                    if self.child.before:
                        output += self.child.before
                    if self.child.after:
                        output += self.child.after
                    response = self._onprompt_handlers[match_index][1]
                    self.child.sendline(response)
                else:
                    # Matched a normal prompt — done
                    break
            
            raw_output = self.child.before
            matched_prompt = self.child.after
            
            # Prepend any output captured during onprompt handling
            raw_output = output + raw_output
            
            # Strip command echo
            output_lines = raw_output.split('\n')
            filtered_lines = [l for l in output_lines if l.strip() != command]
            output = '\n'.join(filtered_lines)
            
            # Add to buffer
            self._buffer += command + '\n' + output + matched_prompt + '\n'
            
            # Console output - print the full interaction
            # Note: prompt is already printed from previous command, so just print command + output + new prompt
            if self.output_mode == 'console':
                print(command)
                print(output, end='')
                print(matched_prompt, end='')
            
            # Return output with prompt
            return output + matched_prompt
            
        except pexpect.EOF:
            # Connection closed
            if self.child.before:
                raw_output = self.child.before
                output_lines = raw_output.split('\n')
                filtered_lines = [l for l in output_lines if l.strip() != command]
                output = '\n'.join(filtered_lines)
                self._buffer += command + '\n' + output + '\n'
                
                # Console output
                if self.output_mode == 'console':
                    print(command)
                    print(output)
            return output
            
        finally:
            # Restore logging
            self.child.logfile = saved_logfile
    
    def send_interactive(self, command: str, expect_pattern: str, 
                        response: str) -> str:
        """
        Send command that triggers interactive prompt.
        
        Args:
            command: Initial command
            expect_pattern: Pattern to wait for
            response: Answer to send
            
        Returns:
            Full interaction output
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        
        output = ''
        
        # Send initial command
        self.child.sendline(command)
        self._buffer += command + '\n'
        
        # Wait for interactive prompt
        self.child.expect(expect_pattern)
        
        if self.child.before:
            output += self.child.before
        if self.child.after:
            output += self.child.after
        
        # Send response
        self.child.sendline(response)
        self._buffer += response + '\n'
        
        # Wait for next prompt
        prompt_pattern = [r'[>#$]'] if not hasattr(self, '_prompt_patterns') else self._prompt_patterns
        self.child.expect(prompt_pattern)
        
        if self.child.before:
            output += self.child.before
        if self.child.after:
            output += self.child.after
        
        self._buffer += output
        return output
    
    def expect_pattern(self, pattern: str, timeout: int = 30) -> Tuple[str, str]:
        """
        Wait for pattern and return (before, match).
        
        Args:
            pattern: Regular expression to match
            timeout: Seconds to wait
            
        Returns:
            Tuple of (before_text, matched_text)
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        
        self.child.expect(pattern, timeout=timeout)
        
        before = self.child.before if self.child.before else ''
        match = self.child.after if self.child.after else ''
        
        self._buffer += before + match
        
        return (before, match)
    
    def send_line(self, line: str) -> None:
        """
        Send line without waiting.
        
        Args:
            line: Text to send
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        
        self.child.sendline(line)
        self._buffer += line + '\n'
    
    def get_buffer(self) -> str:
        """Get accumulated output buffer."""
        return self._buffer
    
    def clear_buffer(self) -> None:
        """Clear output buffer."""
        self._buffer = ''
    
    def is_alive(self) -> bool:
        """Check if connection is active."""
        return self.child is not None and self.child.isalive()
    
    def set_logging(self, logfile) -> None:
        """
        Enable output logging.
        
        Args:
            logfile: File object or file path for logging
        """
        self._logfile = logfile
        if self.child:
            self.child.logfile = logfile
    
    def get_prompt(self) -> Optional[str]:
        """Get current prompt."""
        return self._current_prompt
    
    def set_prompt_patterns(self, patterns: List[str]) -> None:
        """
        Set expected prompt patterns for command execution.
        
        Args:
            patterns: List of regex patterns to expect as prompts
        """
        self._prompt_patterns = patterns
    
    def set_onprompt_handlers(self, handlers: List[Tuple[str, str]]) -> None:
        """
        Set global @ONPROMPT/@RESPONSE handlers.
        
        These patterns are watched during every send_command.
        If matched, the response is sent automatically and the
        command continues waiting for the normal prompt.
        
        Args:
            handlers: List of (pattern, response) tuples
        """
        self._onprompt_handlers = handlers
    
    # Pexpect-specific methods for @PY block raw access
    
    def raw_expect(self, pattern, timeout: int = 30):
        """
        Raw pexpect expect() - for @PY blocks.
        
        Directly delegates to pexpect.expect().
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        return self.child.expect(pattern, timeout=timeout)
    
    def raw_send(self, text: str) -> None:
        """
        Raw pexpect send() - for @PY blocks.
        
        Directly delegates to pexpect.send().
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        self.child.send(text)
    
    def raw_sendline(self, line: str) -> None:
        """
        Raw pexpect sendline() - for @PY blocks.
        
        Directly delegates to pexpect.sendline().
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to device")
        self.child.sendline(line)
