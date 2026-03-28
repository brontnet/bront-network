# bront.network - Bront Language Core
# Network Device Automation
# Version 3.5

"""
Bront Language Core Module

This module provides the core functionality for the Bront network automation language.
It can be used standalone via the bront CLI or as an Ansible module.

Components:
- parser: Parse .bront files into directive list
- codegen: Generate Python code from directives  
- executor: Runtime execution engine
- brontpath: BrontPath format utilities
- config: Configuration management
"""

__version__ = '3.5.0'
__author__ = 'bront'

from .config import load_config, BrontConfig
from .parser import BrontParser
from .codegen import BrontCodeGenerator
from .brontpath import flatten_to_brontpath
from .executor import BrontExecutor

__all__ = [
    'load_config',
    'BrontConfig', 
    'BrontParser',
    'BrontCodeGenerator',
    'flatten_to_brontpath',
    'BrontExecutor',
    '__version__',
]
