# bront.network - Driver Factory
# Bront Language v3.6

"""
Factory for creating connection drivers.

Supports multiple driver types: pexpect, netmiko, scrapli.
Selection can be specified via device profile, inventory, or CLI args.
"""

from typing import Dict, Any, Optional
from .base import BaseDriver
from .pexpect_driver import PexpectDriver


# Track available drivers
AVAILABLE_DRIVERS = {
    'pexpect': PexpectDriver,
}

# Try to import optional drivers
try:
    from .netmiko_driver import NetmikoDriver
    AVAILABLE_DRIVERS['netmiko'] = NetmikoDriver
except ImportError:
    pass

try:
    from .scrapli_driver import ScrapliDriver
    AVAILABLE_DRIVERS['scrapli'] = ScrapliDriver
except ImportError:
    pass


class DriverFactory:
    """
    Factory for creating connection drivers.
    
    Handles driver selection and instantiation based on configuration.
    """
    
    @staticmethod
    def create_driver(device_info: Dict[str, Any], 
                     config: Dict[str, Any],
                     output_mode: str = 'ansible',
                     driver_name: Optional[str] = None) -> BaseDriver:
        """
        Create a connection driver instance.
        
        Driver selection priority:
        1. Explicit driver_name parameter
        2. device_info['driver']
        3. config['default_driver']
        4. Auto-detect with fallback (scrapli → netmiko → pexpect)
        
        Args:
            device_info: Device connection parameters
            config: Bront configuration
            output_mode: 'console' or 'ansible'
            driver_name: Explicit driver selection (overrides all)
            
        Returns:
            Instantiated driver
            
        Raises:
            ValueError: If requested driver is not available
        """
        # Determine driver to use
        selected_driver = None
        
        # Priority 1: Explicit parameter
        if driver_name:
            selected_driver = driver_name.lower()
        
        # Priority 2: Device info
        elif 'driver' in device_info:
            selected_driver = device_info['driver'].lower()
        
        # Priority 3: Config default
        elif 'default_driver' in config:
            selected_driver = config['default_driver'].lower()
        
        # Priority 4: Auto-detect with fallback
        else:
            selected_driver = DriverFactory.auto_select_driver()
        
        # Validate driver is available
        if selected_driver not in AVAILABLE_DRIVERS:
            available = ', '.join(AVAILABLE_DRIVERS.keys())
            raise ValueError(
                f"Driver '{selected_driver}' is not available. "
                f"Available drivers: {available}"
            )
        
        # Instantiate driver
        driver_class = AVAILABLE_DRIVERS[selected_driver]
        return driver_class(device_info, output_mode)
    
    @staticmethod
    def auto_select_driver() -> str:
        """
        Auto-select best available driver.
        
        Preference order: scrapli → netmiko → pexpect
        
        Returns:
            Name of selected driver
        """
        if 'scrapli' in AVAILABLE_DRIVERS:
            return 'scrapli'
        elif 'netmiko' in AVAILABLE_DRIVERS:
            return 'netmiko'
        else:
            return 'pexpect'  # Always available (checked at import)
    
    @staticmethod
    def list_available_drivers() -> list:
        """
        Get list of available drivers.
        
        Returns:
            List of driver names
        """
        return list(AVAILABLE_DRIVERS.keys())
    
    @staticmethod
    def is_driver_available(driver_name: str) -> bool:
        """
        Check if a driver is available.
        
        Args:
            driver_name: Driver to check
            
        Returns:
            True if available, False otherwise
        """
        return driver_name.lower() in AVAILABLE_DRIVERS


def get_driver(device_info: Dict[str, Any],
               config: Dict[str, Any],
               output_mode: str = 'ansible',
               driver_name: Optional[str] = None) -> BaseDriver:
    """
    Convenience function to create a driver.
    
    Wrapper around DriverFactory.create_driver().
    
    Args:
        device_info: Device connection parameters
        config: Bront configuration
        output_mode: 'console' or 'ansible'
        driver_name: Explicit driver selection
        
    Returns:
        Instantiated driver
    """
    return DriverFactory.create_driver(device_info, config, output_mode, driver_name)
