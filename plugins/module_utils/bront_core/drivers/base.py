# bront.network - Base Driver Interface
# Bront Language v3.6

"""
Abstract base class for connection drivers.

All connection drivers (pexpect, netmiko, scrapli) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple


class BaseDriver(ABC):
    """
    Abstract base class for all connection drivers.
    
    Each driver handles device connections differently but provides
    a consistent interface to the BrontExecutor.
    """
    
    def __init__(self, device_info: Dict[str, Any], output_mode: str = 'ansible'):
        """
        Initialize driver.
        
        Args:
            device_info: Device connection parameters (host, username, password, etc.)
            output_mode: 'console' for stdout, 'ansible' for structured return
        """
        self.device_info = device_info
        self.output_mode = output_mode
        self.hostname = device_info.get('hostname', 'DEVICE')
        self.is_connected = False
        
    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to device.
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to device."""
        pass
    
    @abstractmethod
    def send_command(self, command: str, expect_prompt: bool = True) -> str:
        """
        Send a command and return output.
        
        Args:
            command: Command to send
            expect_prompt: Whether to wait for prompt after command
            
        Returns:
            Command output (may include echo and prompt)
        """
        pass
    
    @abstractmethod
    def send_interactive(self, command: str, expect_pattern: str, 
                        response: str) -> str:
        """
        Send command that triggers interactive prompt.
        
        Used for @PROMPT directive - command triggers a question,
        we expect a pattern, then respond.
        
        Args:
            command: Initial command to send
            expect_pattern: Pattern to wait for (the question)
            response: Answer to send
            
        Returns:
            Full interaction output
        """
        pass
    
    @abstractmethod
    def expect_pattern(self, pattern: str, timeout: int = 30) -> Tuple[str, str]:
        """
        Wait for a pattern to appear.
        
        Args:
            pattern: Regular expression pattern to match
            timeout: Seconds to wait
            
        Returns:
            Tuple of (before, match) - text before pattern and the match itself
        """
        pass
    
    @abstractmethod
    def send_line(self, line: str) -> None:
        """
        Send a line without waiting for response.
        
        Used for low-level access in @PY blocks.
        
        Args:
            line: Text to send (newline added automatically)
        """
        pass
    
    @abstractmethod
    def get_buffer(self) -> str:
        """
        Get accumulated output buffer.
        
        Returns:
            All output captured since last clear_buffer()
        """
        pass
    
    @abstractmethod
    def clear_buffer(self) -> None:
        """Clear the output buffer."""
        pass
    
    @abstractmethod
    def is_alive(self) -> bool:
        """
        Check if connection is still active.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def driver_name(self) -> str:
        """
        Get driver name for logging/debugging.
        
        Returns:
            Driver identifier (e.g., 'pexpect', 'netmiko', 'scrapli')
        """
        pass
    
    def set_logging(self, logfile) -> None:
        """
        Enable output logging (optional).
        
        Args:
            logfile: File-like object or path for logging
        """
        # Default: no-op, drivers can override
        pass
    
    def get_prompt(self) -> Optional[str]:
        """
        Get current device prompt (optional).
        
        Returns:
            Current prompt string or None if not available
        """
        # Default: None, drivers can override
        return None
