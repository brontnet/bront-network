#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, bront
# MIT License

DOCUMENTATION = r'''
---
module: bront
short_description: Execute Bront language scripts for network automation
version_added: "1.0.0"
description:
    - Execute Bront language scripts against network devices
    - Bront is a CLI-native scripting language for network device automation
    - Automatically selects device profile based on network_os
    - Supports SSH connections, command execution, output parsing, and SQL queries
options:
    script:
        description:
            - Path to the Bront script file (.bront)
        type: path
        required: false
    script_content:
        description:
            - Bront script content as a string (alternative to script file)
        type: str
        required: false
    host:
        description:
            - Target device hostname or IP address
        type: str
        required: true
    username:
        description:
            - Username for SSH authentication
        type: str
        required: true
    password:
        description:
            - Password for SSH authentication
        type: str
        required: true
        no_log: true
    port:
        description:
            - SSH port number
        type: int
        default: 22
    hostname:
        description:
            - Device hostname for logging and prompt substitution
            - Defaults to host if not specified
        type: str
        required: false
    network_os:
        description:
            - Network OS type (used to select .dspy file)
            - Examples: iosxr, ios, nxos, junos, eos
        type: str
        required: false
    device_profile:
        description:
            - Path to device profile (.dspy) file
            - If not specified, auto-detected from network_os
        type: path
        required: false
    dspy_search_paths:
        description:
            - List of paths to search for .dspy files
        type: list
        elements: str
        default: ['./', '~/.bront/', '/etc/bront/']
    workdir:
        description:
            - Working directory for output files
        type: path
        default: ./bront_work
    logdir:
        description:
            - Log directory for execution logs
        type: path
        default: ./bront_logs
    timestamp_subdirs:
        description:
            - Create timestamp subdirectories in log directory
        type: bool
        default: false
    dry_run:
        description:
            - Run in dry-run mode (skip @DRYRUN commands)
        type: bool
        default: false
    run_id:
        description:
            - Shared run ID for unified directory structure across devices
            - All device outputs and logs are organized under this ID
            - Use tower_job_id or generate with set_fact run_once
        type: str
        required: false
    vars:
        description:
            - Custom variables to pass to the script
            - Available in @PY blocks and {var} substitutions
        type: dict
        required: false
        default: {}
    show_output:
        description:
            - Show device output in Ansible task result
            - When true, output is returned as stdout/stdout_lines
            - Visible with ansible-playbook -v or in debug tasks
        type: bool
        default: false
author:
    - bront
requirements:
    - pexpect
notes:
    - Either device_profile or network_os must be specified
    - network_os auto-selects {network_os}.dspy from search paths
'''

EXAMPLES = r'''
# Run bront script with explicit parameters
- name: Execute health check
  bront.network.bront:
    script: scripts/health_check.bront
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    hostname: "{{ inventory_hostname }}"
    network_os: "{{ ansible_network_os }}"

# Run on multiple devices using inventory variables
- name: Collect interface status
  bront.network.bront:
    script: scripts/interfaces.bront
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    network_os: "{{ ansible_network_os }}"

# With explicit device profile path
- name: Use custom profile
  bront.network.bront:
    script: scripts/custom.bront
    host: 192.168.1.1
    username: admin
    password: "{{ vault_password }}"
    device_profile: /path/to/custom.dspy

# Inline script
- name: Quick command
  bront.network.bront:
    script_content: |
      show version
      @SAVE version
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    device_profile: iosxr.dspy

# With custom variables
- name: Check specific interface
  bront.network.bront:
    script: scripts/check_interface.bront
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    network_os: "{{ ansible_network_os }}"
    vars:
      interface: GigabitEthernet0/0/0/1
      threshold: 1000

# With unified run_id for multi-device runs
- name: Generate shared run ID
  set_fact:
    bront_run_id: "{{ tower_job_id | default(lookup('pipe', 'date +%Y%m%d%H%M%S') + '_' + 999999 | random | string) }}"
  run_once: true

- name: Audit all routers
  bront.network.bront:
    script: scripts/audit.bront
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    network_os: "{{ ansible_network_os }}"
    run_id: "{{ bront_run_id }}"
  register: bront_result

- name: Merge findings from all devices
  bront.network.bront:
    script_content: |
      @PY from bront_core.executor import BrontExecutor
      @PY merged = BrontExecutor.merge_findings('bront_work/{{ bront_run_id }}')
      @PY print(f"Merged findings: {merged}")
    host: localhost
    username: local
    password: local
    run_id: "{{ bront_run_id }}"
  run_once: true
'''

RETURN = r'''
changed:
    description: Whether any files were created or modified
    type: bool
    returned: always
output:
    description: Full CLI session output
    type: str
    returned: always
errors:
    description: List of errors matched by @ONERROR patterns
    type: list
    returned: always
findings:
    description: Structured findings from @REPORT and @AI directives
    type: list
    returned: always
    sample: [{"device": "ROUTER1", "source": "report", "severity": "high", "finding": "CRC errors detected"}]
run_id:
    description: Run ID for this execution (shared across devices when provided)
    type: str
    returned: always
device:
    description: Device hostname
    type: str
    returned: always
'''

import os
import re
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.bront.network.plugins.module_utils.bront_core import (
        BrontParser, BrontExecutor, load_config
    )
    HAS_BRONT_CORE = True
except ImportError:
    HAS_BRONT_CORE = False

try:
    import pexpect
    HAS_PEXPECT = True
except ImportError:
    HAS_PEXPECT = False


# Default .dspy search paths
# Default .dspy search paths (includes collection's profiles directory)
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_COLLECTION_PROFILES = os.path.normpath(os.path.join(_MODULE_DIR, '..', '..', 'profiles'))
DEFAULT_DSPY_PATHS = ['./', os.path.expanduser('~/.bront/'), '/etc/bront/', _COLLECTION_PROFILES]


def find_dspy_file(network_os: str, search_paths: list) -> str:
    """Find .dspy file for given network OS."""
    dspy_filename = f"{network_os}.dspy"
    
    for search_path in search_paths:
        expanded_path = os.path.expanduser(search_path)
        full_path = os.path.join(expanded_path, dspy_filename)
        if os.path.exists(full_path):
            return full_path
    
    return None


def find_dspy_content(network_os: str, search_paths: list):
    """
    Find .dspy file or fall back to embedded profile.
    
    Returns:
        Tuple of (file_path_or_None, content_or_None)
    """
    # Try filesystem first
    dspy_path = find_dspy_file(network_os, search_paths)
    if dspy_path:
        return dspy_path, None  # Path found, content loaded later
    
    # Fall back to embedded profiles (always available in AnsiballZ payload)
    try:
        from ansible_collections.bront.network.plugins.module_utils.bront_core.profiles import get_embedded_profile
    except ImportError:
        try:
            from bront_core.profiles import get_embedded_profile
        except ImportError:
            return None, None
    
    content = get_embedded_profile(network_os)
    if content:
        return None, content  # No file, but have embedded content
    
    return None, None


def extract_sections(dspy_content: str):
    """Extract begin and end sections from device profile content."""
    begin_match = re.search(
        r'## begin commands start\n(.*?)## begin commands end',
        dspy_content, re.DOTALL
    )
    begin_section = begin_match.group(1).rstrip() if begin_match else ''
    
    end_match = re.search(
        r'## logout commands start\n(.*?)## logout commands end',
        dspy_content, re.DOTALL
    )
    end_section = end_match.group(1).rstrip() if end_match else ''
    
    return begin_section, end_section


def expand_bront_script(script_content: str, dspy_path: str = None, dspy_content: str = None):
    """Expand bront script with device profile sections."""
    begin_section = ''
    end_section = ''
    
    if dspy_path and os.path.exists(dspy_path):
        with open(dspy_path, 'r') as f:
            dspy_content = f.read()
    
    if dspy_content:
        begin_section, end_section = extract_sections(dspy_content)
    
    # Extract @PERMAPROMPT and move to front
    permaprompt_line = ''
    user_lines = []
    for line in script_content.split('\n'):
        if line.strip().startswith('@PERMAPROMPT'):
            permaprompt_line = line
        else:
            user_lines.append(line)
    
    user_content = '\n'.join(user_lines)
    
    # Build expanded content
    parts = []
    if permaprompt_line:
        parts.append(permaprompt_line)
    if begin_section:
        parts.append(begin_section)
    parts.append('## END_BEGIN_SECTION')
    parts.append(user_content)
    if end_section:
        parts.append(end_section)
    
    return '\n'.join(parts)


def run_module():
    """Main module execution."""
    try:
        module_args = dict(
            script=dict(type='path', required=False),
            script_content=dict(type='str', required=False),
            # Connection params - can be explicit or from inventory
            host=dict(type='str', required=False),
            username=dict(type='str', required=False),
            password=dict(type='str', required=False, no_log=True),
            enable_password=dict(type='str', required=False, no_log=True),
            port=dict(type='int', required=False, default=22),
            hostname=dict(type='str', required=False),
            # Device profile
            network_os=dict(type='str', required=False),
            device_profile=dict(type='path', required=False),
            dspy_search_paths=dict(type='list', elements='str', default=DEFAULT_DSPY_PATHS),
            # Directories
            workdir=dict(type='path', default='./bront_work'),
            logdir=dict(type='path', default='./bront_logs'),
            timestamp_subdirs=dict(type='bool', default=False),
            # Execution mode
            dry_run=dict(type='bool', default=False),
            # Shared run ID for unified directories
            run_id=dict(type='str', required=False, default=None),
            # Custom script variables
            vars=dict(type='dict', required=False, default={}),
            # Output display control
            show_output=dict(type='bool', default=False),
            # Connection type
            connection=dict(type='str', default='ssh', choices=['ssh', 'telnet']),
        )
        
        module = AnsibleModule(
            argument_spec=module_args,
            supports_check_mode=True,
            required_one_of=[['script', 'script_content']],
        )
        
        # Check dependencies
        if not HAS_PEXPECT:
            module.fail_json(msg='pexpect is required for this module')
        
        if not HAS_BRONT_CORE:
            module.fail_json(msg='bront_core module_utils not found')
        
        # Get parameters
        script_path = module.params['script']
        script_content = module.params['script_content']
        network_os = module.params['network_os']
        device_profile = module.params['device_profile']
        dspy_search_paths = module.params['dspy_search_paths']
        workdir = module.params['workdir']
        logdir = module.params['logdir']
        timestamp_subdirs = module.params['timestamp_subdirs']
        
        # Get connection info - explicit params take priority
        host = module.params.get('host')
        username = module.params.get('username')
        password = module.params.get('password')
        port = module.params.get('port', 22)
        hostname = module.params.get('hostname')
        
        # Fallback to inventory variables if not explicitly provided
        # Note: modules don't automatically get hostvars, so users should pass them explicitly
        # or use the playbook to set these from inventory
        if not host:
            host = os.environ.get('ANSIBLE_HOST')
        if not username:
            username = os.environ.get('ANSIBLE_USER')
        if not password:
            password = os.environ.get('ANSIBLE_PASSWORD')
        
        # Set hostname to host if not provided
        if not hostname:
            hostname = host
        
        # Validate required connection info
        if not host:
            module.fail_json(msg='host is required (pass explicitly or set ansible_host in inventory)')
        if not username:
            module.fail_json(msg='username is required (pass explicitly or set ansible_user in inventory)')
        if not password:
            module.fail_json(msg='password is required (pass explicitly or set ansible_password in inventory)')
        
        # Find device profile
        dspy_path = device_profile  # Explicit path from user
        dspy_content = None
        
        if not dspy_path:
            if not network_os:
                module.fail_json(msg='ansible_network_os not defined and no device_profile specified')
            
            dspy_path, dspy_content = find_dspy_content(network_os, dspy_search_paths)
            if not dspy_path and not dspy_content:
                searched = [os.path.join(p, f"{network_os}.dspy") for p in dspy_search_paths]
                module.fail_json(msg=f"Driver file not found: {network_os}.dspy. Searched: {', '.join(searched)}. No embedded profile available.")
        
        # Load script content
        if script_content:
            content = script_content
        elif script_path:
            if not os.path.exists(script_path):
                module.fail_json(msg=f'Script file not found: {script_path}')
            with open(script_path, 'r') as f:
                content = f.read()
        else:
            module.fail_json(msg='Either script or script_content must be provided')
        
        # Expand script with device profile
        expanded_content = expand_bront_script(content, dspy_path=dspy_path, dspy_content=dspy_content)
        
        # Check mode - don't execute
        if module.check_mode:
            module.exit_json(
                changed=False,
                msg='Check mode - no execution',
                script_lines=len(expanded_content.split('\n')),
                device_profile=dspy_path or '(embedded)',
                network_os=network_os
            )
        
        # Get enable_password - fall back to password if not set
        enable_password = module.params.get('enable_password') or password
        
        # Setup device info and config
        device_info = {
            'host': host,
            'username': username,
            'password': password,
            'enable_password': enable_password,
            'port': int(port),
            'hostname': hostname,
            'connection': module.params.get('connection', 'ssh'),
        }
        
        config = {
            'WORKDIR': os.path.abspath(workdir),
            'LOGDIR': os.path.abspath(logdir),
            'timestamp_subdirs': timestamp_subdirs,
        }
        
        # Get dry_run flag
        dry_run = module.params.get('dry_run', False)
        
        # Get run_id for unified directories
        run_id = module.params.get('run_id', None)
        
        # Get custom script variables
        script_vars = module.params.get('vars', {})
        
        try:
            # Parse script
            parser = BrontParser(hostname=hostname)
            directives = parser.parse_string(expanded_content)
            
            # Execute
            executor = BrontExecutor(device_info, config, output_mode='ansible', dry_run=dry_run, script_vars=script_vars, run_id=run_id)
            
            # Save the executed script to log directory for reference
            # Expand $DEVICE placeholders for the log
            device_pt = hostname[:8]
            device_pr = hostname[-4:] if len(hostname) >= 4 else hostname
            log_content = expanded_content.replace('$DEVICEPT', device_pt)
            log_content = log_content.replace('$DEVICEPR', device_pr)
            log_content = log_content.replace('$DEVICE', hostname)
            
            try:
                with open(executor.bront_log_path, 'w') as f:
                    f.write(log_content)
            except (OSError, IOError) as e:
                # Log file writing failed - continue anyway
                pass
            
            result = executor.execute(directives)
            
            # Add profile source info
            result['device_profile'] = dspy_path or f'(embedded {network_os})'
            
            # Add file paths
            result['output_log'] = executor.output_log_path
            result['error_log'] = executor.error_log_path
            result['script_log'] = executor.bront_log_path
            result['work_dir'] = executor.run_dir
            if executor.findings_dir and result.get('findings'):
                result['findings_file'] = os.path.join(executor.findings_dir, f'{executor.hostname}_findings.json')
            
            # Show output control
            show_output = module.params.get('show_output', False)
            if show_output and result.get('output'):
                # stdout/stdout_lines are recognized by Ansible's default callback
                result['stdout'] = result['output']
                result['stdout_lines'] = result['output'].splitlines()
            
            # Return results
            if result.get('failed'):
                error_msg = result.pop('msg', 'Execution failed')
                module.fail_json(msg=error_msg, **result)
            else:
                module.exit_json(**result)
        except Exception as inner_e:
            # Inner exception during execution
            import traceback
            error_details = {
                'msg': str(inner_e),
                'exception_type': type(inner_e).__name__,
                'traceback': traceback.format_exc(),
                'errno': getattr(inner_e, 'errno', None)
            }
            module.fail_json(**error_details)
                
    except Exception as e:
        import traceback
        import tempfile
        
        # Write debug info to temp file for troubleshooting
        try:
            debug_file = tempfile.mktemp(prefix='bront_debug_', suffix='.log')
            with open(debug_file, 'w') as f:
                f.write(f"Exception: {type(e).__name__}: {str(e)}\n")
                f.write(f"Errno: {getattr(e, 'errno', None)}\n\n")
                f.write("Full traceback:\n")
                f.write(traceback.format_exc())
        except:
            pass
        
        # Try to use module.fail_json if module exists, otherwise print JSON
        error_details = {
            'msg': str(e),
            'exception_type': type(e).__name__,
            'traceback': traceback.format_exc(),
            'errno': getattr(e, 'errno', None),
            'debug_file': debug_file if 'debug_file' in locals() else None
        }
        try:
            module.fail_json(**error_details)
        except NameError:
            # module doesn't exist yet - print JSON for Ansible to parse
            import json
            import sys
            error_details['failed'] = True
            try:
                print(json.dumps(error_details))
            except (OSError, IOError):
                # stdout is closed - write to stderr as last resort
                try:
                    sys.stderr.write(json.dumps(error_details) + '\n')
                except:
                    # Give up - re-raise original exception
                    pass
            raise


def main():
    run_module()


if __name__ == '__main__':
    main()
