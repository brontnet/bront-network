# Bront

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/brontnet/bront-network)](https://github.com/brontnet/bront-network/releases)
[![Ansible Galaxy](https://img.shields.io/badge/galaxy-bront.network-blue.svg)](https://galaxy.ansible.com/ui/repo/published/bront/network/)

**CLI-native network automation.** Write what you would type — nothing more.

Bront is a streamlined approach to network device automation. What takes 50 lines of Python fits in 5 lines of Bront — scripts look like CLI sessions. If you can type it on a terminal, you can automate it.

Three CLI commands, one print — that's a complete automation script:

```bront
## script name: check.bront
show ip interface brief
show version
show running-config | section router bgp
@PY print(f"Collected data from {device_name}")
```

Save output and act on it — count down interfaces across your fleet:

```bront
## script name: count_down_interfaces.bront
show ip interface brief
@SAVE interfaces

@PY down = bash("grep -ic 'down' interfaces")
@PY print(f"{device_name}: {down} interfaces down")
```

Run it:

```bash
# Standalone
bront check.bront ROUTER1

# Ansible playbook
ansible-playbook -i inventory.ini site.yml
```

Same script, both modes — no changes needed.

## Install

```bash
# From Ansible Galaxy (recommended)
ansible-galaxy collection install bront.network
pip install pexpect pyyaml

# Add standalone CLI to PATH
export PATH="$PATH:~/.ansible/collections/ansible_collections/bront/network/scripts"

# Verify
bront --help
```

Or install from GitHub release:

```bash
# Download latest release from https://github.com/brontnet/bront-network/releases
mkdir -p ~/.ansible/collections/ansible_collections/
tar -xzf bront-network-<version>.tar.gz -C ~/.ansible/collections/ansible_collections/
export PATH="$PATH:~/.ansible/collections/ansible_collections/bront/network/scripts"
pip install pexpect pyyaml
bront --help
```

## Quick Start

**1. Create inventory** (`inventory.ini`):
```ini
[routers]
ROUTER1 ansible_host=192.168.1.1 ansible_network_os=iosxr ansible_user=admin ansible_password=secret123
```

**2. Write script** (`check.bront`):
```bront
show interface brief
show version
@PY print(f"Collected data from {device_name}")
```

**3. Run**:
```bash
bront check.bront ROUTER1
```

## Why Bront?

**You already know the commands.** Network engineers spend years learning CLI syntax. Bront doesn't ask you to learn a new abstraction — it runs the commands you already know.

**Structured output without parsers.** The `@SAVE` directive creates BrontPath format — a pipe-delimited flattening of hierarchical CLI output. Process it with the grep, awk, sed or SQL you already know. No TextFSM templates, no Genie parsers, no custom regex.

**Loop and act on output.** Extract data with `bash()` or SQL queries, loop with `@PY for`, and run CLI commands per result. Fix 50 down interfaces with a few lines.

**Multi-vendor device profiles.** Built-in profiles for Cisco IOS/IOS-XR/NX-OS, Arista EOS, Nokia SR OS, and Juniper Junos handle paging, prompt detection, and interactive prompts automatically.

**Works standalone or with Ansible.** Run from command line for quick tasks. Run from Ansible playbooks for orchestration, inventories, vaults, and Tower/AWX scheduling. Same `.bront` script runs identically in both modes.

**Python and bash when you need them.** Bront is Python-based — `@PY` blocks give you the full power of Python, and `bash()` lets you call any shell command. Stay simple for simple tasks, drop into real code when the logic demands it.

**Works where APIs don't.** Many production devices have no API — older IOS, legacy NX-OS, end-of-life platforms. Bront works on anything with an SSH or telnet CLI.

**Integrates with your existing tools.** Output is files and JSON — pipe it to ServiceNow, vulnerability scanners, CMDB imports, or any internal platform. No SDK, no adapter needed.

---

## Reference

### Installation Options

**From Ansible Galaxy** (recommended):

```bash
ansible-galaxy collection install bront.network
pip install pexpect pyyaml
```

**Standalone only** (no Ansible needed):

```bash
tar -xzf bront-network-<version>.tar.gz
cd bront/network
export PATH="$PATH:$(pwd)/scripts"
ln -s $(pwd)/scripts/bront ~/bin/bront
pip install pexpect pyyaml
bront --help
```

**From GitHub release** (includes standalone CLI):

```bash
mkdir -p ~/.ansible/collections/ansible_collections/
tar -xzf bront-network-<version>.tar.gz -C ~/.ansible/collections/ansible_collections/
ansible-galaxy collection list | grep bront
```

Device profiles are embedded in the collection and available automatically — no separate file installation needed.

### Inventory Format

Bront reads standard Ansible inventory files:

```ini
[routers]
ROUTER1 ansible_host=192.168.1.1
ROUTER2 ansible_host=192.168.1.2

[routers:vars]
ansible_network_os=iosxr
ansible_user=admin
ansible_password=secret123
ansible_port=22
```

Or YAML format (`inventory.yml`):

```yaml
all:
  hosts:
    ROUTER1:
      ansible_host: 192.168.1.1
      ansible_network_os: iosxr
      ansible_user: admin
      ansible_password: secret123
```

**Inventory variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `ansible_host` | Yes | Device IP or hostname |
| `ansible_network_os` | Yes | Platform: `iosxr`, `ios`, `nxos`, `eos`, `nokia`, `junos` |
| `ansible_user` | Yes | SSH username |
| `ansible_password` | Yes | SSH password |
| `ansible_port` | No | SSH port (default: 22) or telnet port (default: 23) |
| `bront_connection` | No | `ssh` (default) or `telnet` |

### Standalone CLI

```bash
bront <script.bront> <hostname> [options]

Options:
  -i, --inventory FILE        Inventory file (default: ./inventory.ini or ./inventory.yml)
  --vault-password-file FILE  Ansible vault password file
  --dry-run                   Skip @DRYRUN commands, show what would execute
  --run-id ID                 Shared run ID for unified directory structure
  --no-profile                Skip device profile expansion (for re-running expanded scripts from logs)
  -e, --var KEY=VALUE         Set script variable (can be used multiple times)
```

Examples:
```bash
# Basic
bront health_check.bront ROUTER1

# With explicit inventory
bront health_check.bront ROUTER1 -i /path/to/inventory.yml

# With vault-encrypted passwords
bront health_check.bront ROUTER1 --vault-password-file .vault_pass

# Dry run mode
bront config_change.bront ROUTER1 --dry-run

# With shared run ID
bront audit.bront ROUTER1 --run-id audit_20260206

# With custom variables
bront check_interface.bront ROUTER1 -e interface=GigabitEthernet0/0/0/1 -e threshold=1000

# Re-run an expanded script from logs (skip profile, already embedded)
bront bront_logs/007/ROUTER1_bront.log ROUTER1 --no-profile --vault-password-file .vault_pass
```

### Ansible Playbook

```yaml
- name: Health check
  hosts: routers
  gather_facts: no
  tasks:
    - name: Generate run ID
      set_fact:
        bront_run_id: "{{ lookup('pipe', 'date +%Y%m%d%H%M%S') }}"
      run_once: true

    - name: Run audit
      bront.network.bront:
        script: health_check.bront
        host: "{{ ansible_host }}"
        hostname: "{{ inventory_hostname }}"
        username: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        network_os: "{{ ansible_network_os }}"
        run_id: "{{ bront_run_id }}"
      register: bront_result

    - name: Show findings
      debug:
        var: bront_result.findings
      when: bront_result.findings | length > 0

    - name: Show output
      debug:
        var: bront_result.output

    - name: Show profile source
      debug:
        var: bront_result.device_profile
```

Run with:
```bash
# Single device
ansible-playbook -i inventory.ini site.yml -l ROUTER1

# Multiple devices in parallel
ansible-playbook -i inventory.ini site.yml -l ROUTER1,ROUTER2,ROUTER3 -f 10

# All devices in group
ansible-playbook -i inventory.ini site.yml -l routers
```

### Ansible Module Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `script` | path | — | Path to `.bront` script file |
| `script_content` | str | — | Inline script content (alternative to `script`) |
| `host` | str | — | Device IP or hostname |
| `hostname` | str | — | Display name (defaults to `host`) |
| `username` | str | — | SSH username |
| `password` | str | — | SSH password |
| `enable_password` | str | — | Enable mode password (defaults to `password`) |
| `port` | int | 22 | SSH port |
| `network_os` | str | — | Platform identifier (selects device profile) |
| `device_profile` | path | — | Explicit path to `.dspy` profile |
| `workdir` | path | `./bront_work` | Working directory for output files |
| `logdir` | path | `./bront_logs` | Log directory |
| `run_id` | str | — | Shared run ID for unified directories |
| `dry_run` | bool | false | Skip `@DRYRUN` commands |
| `vars` | dict | `{}` | Custom variables for the script |
| `show_output` | bool | false | Include output as `stdout`/`stdout_lines` in result |
| `timestamp_subdirs` | bool | false | Create timestamp subdirectories in log directory |
| `connection` | str | `ssh` | Connection type: `ssh` or `telnet` |

### Module Return Values

| Field | Description |
|-------|-------------|
| `output` | Full device output (always available) |
| `stdout` | Same as `output` (when `show_output: true`) |
| `stdout_lines` | Output split into lines (when `show_output: true`) |
| `findings` | Structured findings from `@REPORT` and `report()` |
| `findings_file` | Path to per-device findings JSON (when findings exist) |
| `errors` | Error patterns matched by `@ONERROR` |
| `changed` | Whether commands were executed |
| `run_id` | Run identifier used |
| `device` | Device hostname |
| `device_profile` | Profile source (filesystem path or `(embedded <os>)`) |
| `work_dir` | Per-device work directory path |
| `output_log` | Session output log path |
| `error_log` | Error log path |
| `script_log` | Expanded script log path |

### Directives Reference

| Directive | Purpose | Example |
|-----------|---------|---------|
| `@SAVE` | Save buffer to file + BrontPath txtdb | `@SAVE interfaces` |
| `@RSAVE` | Save buffer to file only (raw, no txtdb) | `@RSAVE raw_output` |
| `@PY` | Execute Python code | `@PY count = bash("grep -c Up interfaces")` |
| `@QUERY` | SQL query on saved BrontPath data | `@QUERY SELECT col1 FROM interfaces WHERE ...` |
| `@ONERROR` | Define error detection pattern | `@ONERROR "error\|failed\|invalid"` |
| `@REPORT` | Format error report (paired with `@ONERROR`) | `@REPORT "Error on %d: %s" SEVERITY=high` |
| `@ONPROMPT` | Global session watcher for interactive prompts | `@ONPROMPT "Uncommitted changes"` |
| `@RESPONSE` | Auto-response paired with `@ONPROMPT` | `@RESPONSE "no"` |
| `@PROMPT` | Positional interactive prompt handler | `@PROMPT "Password:" "$ENABLE_PASSWORD"` |
| `@PERMAPROMPT` | Set device prompt regex patterns | `@PERMAPROMPT RP/\d+/\S+:.*#` |
| `@SILENT` | Send command, suppress from output | `@SILENT terminal length 0` |
| `@INCLUDE` | Include another `.bront` script | `@INCLUDE common/setup.bront` |
| `@DRYRUN` | Command skipped in dry-run mode | `@DRYRUN shutdown` |
| `@DIAGNOSTICS` | Enable command timing timestamps | `@DIAGNOSTICS` |

### Device Profiles

Device profiles (`.dspy` files) handle platform-specific setup: paging, prompt patterns, and interactive prompt responses. They are applied automatically based on `network_os`.

| Profile | Platform | `network_os` | Paging | Special Handling |
|---------|----------|--------------|--------|------------------|
| `ios.dspy` | Cisco IOS | `ios` | `terminal length 0` | Enable mode detection |
| `iosxr.dspy` | Cisco IOS-XR | `iosxr` | `terminal length 0` | RP prompt patterns |
| `nxos.dspy` | Cisco NX-OS | `nxos` | `terminal length 0` | `terminal width 511` |
| `eos.dspy` | Arista EOS | `eos` | `term len 0` | Uncommitted changes prompt |
| `nokia.dspy` | Nokia SR OS | `nokia` | `environment no more` | A:/B: active/backup RP prompts |
| `junos.dspy` | Juniper Junos | `junos` | `set cli screen-length 0` | Uncommitted changes on exit |

Profiles are searched in order: `./`, `~/.bront/`, `/etc/bront/`, collection `profiles/` directory, and finally an embedded fallback compiled into the module (always available, even inside Ansible's execution payload).

**Custom profiles** — create a `.dspy` file with begin and logout sections:

```
## begin commands start
@PERMAPROMPT your_device>|your_device#
terminal length 0
@ONPROMPT "Save changes?"
@RESPONSE "no"
## begin commands end

## logout commands start
exit
## logout commands end
```

Place in `./`, `~/.bront/`, or `/etc/bront/` and reference with `network_os` or `device_profile`.

### @ONPROMPT / @RESPONSE

Global session watchers that handle interactive prompts appearing at any time during a session. Unlike `@PROMPT` (which is positional — it handles one specific prompt at one point in the script), `@ONPROMPT` patterns are watched during every command.

```bront
@ONPROMPT "Uncommitted changes found"
@RESPONSE "no"

@ONPROMPT "Do you wish to proceed"
@RESPONSE "yes"

show running-config
configure terminal
  interface Loopback999
  no shutdown
commit
exit
```

If the device prompts "Uncommitted changes found" at any point during the session, Bront automatically sends "no" and continues. Multiple `@ONPROMPT/@RESPONSE` pairs can be active simultaneously.

These are primarily used in device profiles, so engineers don't need to handle platform-specific interactive prompts in their scripts.

### @ONERROR / @REPORT and Structured Findings

Define error patterns and generate structured findings with severity levels:

```bront
@ONERROR "CRC|input error|output error"
@REPORT "Link errors on %d: %s" SEVERITY=high CONTEXT=3

@ONERROR "down|administratively"
@REPORT "Interface down on %d: %s" SEVERITY=medium

show interfaces
@SAVE interfaces
```

`@ONERROR` defines patterns to match in command output. `@REPORT` formats the finding with:
- `%t` — timestamp
- `%d` — device name
- `%s` — matched output
- `CONTEXT=N` — include N lines before/after the match
- `SEVERITY=high|medium|low|info` — finding severity (default: high)

Findings are returned as structured JSON in the Ansible result (`findings[]` array) and written to per-device files:

```json
{
  "run_id": "20260206_143000",
  "device": "ROUTER1",
  "source": "report",
  "severity": "high",
  "command": "show interface GigabitEthernet0/0/0/1",
  "finding": "CRC errors detected",
  "detail": {"pattern": "CRC", "matched": "CRC errors 1523"},
  "timestamp": "2026-02-06T14:30:05Z"
}
```

### @PY Variables

| Variable | Description |
|----------|-------------|
| `device_name` | Inventory name, e.g. `ROUTER1` (same as `hostname`) |
| `hostname` | Inventory name, e.g. `ROUTER1` (same as `device_name`) |
| `host` | SSH target address, e.g. `192.168.1.1` or `router1.example.com` |
| `buffer` | Current output buffer (output since last `@SAVE`) |
| `bash(cmd)` | Run shell command, return output |
| `report(msg, severity, detail)` | Emit structured finding from code (see below) |
| `send(cmd)` | Send raw command to device |
| `expect(pattern)` | Wait for pattern, capture output |
| *custom* | Variables passed via `-e key=value` (CLI) or `vars:` (Ansible) |

These map to Ansible inventory variables as follows: `device_name`/`hostname` comes from `inventory_hostname` (or the `hostname` module parameter), and `host` comes from `ansible_host`.

**Programmatic findings with `report()`:**

`@ONERROR/@REPORT` matches patterns in device output. For threshold checks, calculations, or any logic-driven finding, use `report()` from `@PY`:

```bront
dir harddisk:
@SAVE hdspace_raw

@PY hdspace = bash("grep free hdspace_raw | awk '{print $(NF-2)}' | sed 's/(//'").strip()
@PY if hdspace and int(hdspace) < 2500000:
  @PY report(f"XR harddisk space low: {hdspace} kbytes free", severity="high", detail={"metric": "disk_free", "value": hdspace})
```

`report()` feeds the same findings pipeline as `@REPORT` — JSON files, Ansible return values, standalone summary. Parameters:
- `message` (required) — finding description
- `severity` — `high`, `medium`, `low`, or `info` (default: `high`)
- `detail` — optional dict with additional context

**Using custom variables:**
```bront
## Script: check_interface.bront
show interface {interface}

@PY print(f"Checked {interface} on {device_name}")
```

Both `{var}` and `$var` syntax work in CLI commands inside `@PY for/if` blocks:

```bront
@PY interfaces = bash("grep '/' interfaces | awk '{print $1}'")
@PY for iface in interfaces.strip().split('\n'):
  show interface {iface}
  show interface $iface
```

Run with:
```bash
# Standalone
bront check_interface.bront ROUTER1 -e interface=GigabitEthernet0/0/0/1

# Ansible
- bront.network.bront:
    script: check_interface.bront
    vars:
      interface: GigabitEthernet0/0/0/1
```

**Tower/AWX integration** — variables from surveys, job templates, or inventory flow through Jinja:

```yaml
- name: Check interface
  bront.network.bront:
    script: check_interface.bront
    host: "{{ ansible_host }}"
    username: "{{ ansible_user }}"
    password: "{{ ansible_password }}"
    network_os: "{{ ansible_network_os }}"
    vars:
      interface: "{{ interface }}"
      threshold: "{{ threshold | default(1000) }}"
```

### Run ID and Directory Structure

Use `run_id` to organize output from multi-device runs under a single identifier. Without `run_id`, each device gets a unique timestamped directory.

```bash
# Standalone
bront audit.bront ROUTER1 --run-id audit_20260206
```

```yaml
# Ansible — generate shared run ID once, use across all hosts
- set_fact:
    bront_run_id: "{{ tower_job_id | default(lookup('pipe', 'date +%Y%m%d%H%M%S')) }}"
  run_once: true

- bront.network.bront:
    script: audit.bront
    run_id: "{{ bront_run_id }}"
```

Directory layout with `run_id`:

```
bront_work/
  <run_id>/
    ROUTER1/                    # per-device work files, @SAVE output
    ROUTER2/
    ROUTER1_findings.json       # per-device findings
    ROUTER2_findings.json
    findings.json               # merged findings (after merge_findings)

bront_logs/
  <run_id>/
    ROUTER1_output.log          # full session output
    ROUTER1_error.log           # @ONERROR matches
    ROUTER1_bront.log           # expanded script as executed
    ROUTER2_output.log
    ...
```

## Examples

**Collect configs** — back up running config and version info:
```bront
show running-config
@SAVE config

show version
@SAVE version

@PY print(f"Backup complete for {device_name}")
```

Files are saved to the device's work directory: `bront_work/<run_id>/<hostname>/config` and `config.txtdb`. To save to an absolute path:

```bront
show running-config
@SAVE /opt/backups/{device_name}_config

show version
@SAVE /opt/backups/{device_name}_version
```

**Process output with @PY** — count interface states:
```bront
show ip interface brief
@SAVE interfaces

@PY up_count = bash("grep -c 'Up' interfaces")
@PY down_count = bash("grep -c 'Down' interfaces")
@PY print(f"Interfaces — UP: {up_count}, DOWN: {down_count}")
```

**Multi-line @PY block** — iterate over buffer lines:
```bront
show ip interface brief

@PY @@@
for line in buffer.split('\n'):
    if 'Up' in line:
        iface = line.split()[0]
        print(f"  {iface} is operational")
@@@
```

**Conditional logic** — run extra commands based on platform:
```bront
show version
@SAVE version

@PY version_text = bash("cat version")
@PY if 'IOS XR' in version_text:
  show install active
```

**Error handling with findings** — catch config errors:
```bront
@ONERROR "Invalid input|Incomplete command"
@REPORT "[%t] Command error on %d: %s" SEVERITY=high CONTEXT=2

configure terminal
interface Loopback999
  ip address 10.255.255.1 255.255.255.255
commit
```

**Command timing with @DIAGNOSTICS** — measure command execution time:
```bront
@DIAGNOSTICS

show ip interface brief
show running-config
```

Output includes timestamps for each command:
```
### 2026-01-19 14:32:05.123456 CMD_START 0.0s show ip interface brief
<command output>
### 2026-01-19 14:32:07.654321 CMD_END 2.530865s show ip interface brief
```

**Disk space check** — programmatic threshold finding with `report()`:
```bront
dir harddisk:
@SAVE hdspace_raw

@PY hdspace = bash("grep free hdspace_raw | awk '{print $(NF-2)}' | sed 's/(//'").strip()
@PY print(f"Harddisk free space: {hdspace} kbytes")
@PY if hdspace and int(hdspace) < 2500000:
  @PY report(f"Harddisk space low: {hdspace} kbytes free", severity="high", detail={"metric": "disk_free", "value": int(hdspace)})
```

**Loop over interfaces** — run per-interface commands from saved output:
```bront
show ip interface brief
@SAVE interfaces

@PY intfs = bash("grep '/' interfaces | awk '{print $1}'")
@PY for iface in intfs.strip().split('\n'):
  show interface {iface}
```

**Find and remove unused ACLs** — audit and clean up with `--dry-run` safety:
```bront
show running-config
@SAVE full_config

show running-config ipv4 access-list
@SAVE acl_v4

show running-config ipv6 access-list
@SAVE acl_v6

@PY unused = []
@PY @@@
for af, filename in [('ipv4', 'acl_v4'), ('ipv6', 'acl_v6')]:
    acls = bash(f"grep '^{af} access-list' {filename} | awk '{{print $3}}'").strip()
    if not acls:
        continue
    for acl in acls.splitlines():
        acl = acl.strip()
        if not acl:
            continue
        refs = bash(f"grep -w '{acl}' full_config | grep -v '^{af} access-list {acl}$'").strip()
        if not refs:
            unused.append((af, acl))
            report(f"Unused {af} ACL: {acl}", severity="medium", detail={"type": af, "acl": acl})
@@@

@PY if unused:
  @DRYRUN configure
  @PY for af, acl in unused:
    @DRYRUN no {af} access-list {acl}
  @DRYRUN commit
  @DRYRUN end
```

Run with `--dry-run` to report only, without `--dry-run` to remove.

## BrontPath Format and txtdb Files

When `@SAVE` runs, it creates two files:
- `filename` — raw CLI output
- `filename.txtdb` — pipe-delimited BrontPath format for queries

**Operational output** like `show interfaces`:
```
GigabitEthernet0/0/0/1 is up, line protocol is up
  MTU 1514 bytes, BW 1000000 Kbit
    0 input errors, 0 CRC, 0 frame
GigabitEthernet0/0/0/2 is administratively down, line protocol is down
  MTU 1514 bytes, BW 1000000 Kbit
    0 input errors, 5 CRC, 0 frame
```

Becomes BrontPath — each parent's words are prepended to indented children:
```
GigabitEthernet0/0/0/1|is|up,|line|protocol|is|up|GigabitEthernet0/0/0/1 is up, line protocol is up
GigabitEthernet0/0/0/1|is|up,|line|protocol|is|up|MTU|1514|bytes,|BW|1000000|Kbit|  MTU 1514 bytes, BW 1000000 Kbit
GigabitEthernet0/0/0/1|is|up,|line|protocol|is|up|MTU|1514|bytes,|BW|1000000|Kbit|0|input|errors,|0|CRC,|0|frame|    0 input errors, 0 CRC, 0 frame
GigabitEthernet0/0/0/2|is|administratively|down,|line|protocol|is|down|GigabitEthernet0/0/0/2 is administratively down, line protocol is down
GigabitEthernet0/0/0/2|is|administratively|down,|line|protocol|is|down|MTU|1514|bytes,|BW|1000000|Kbit|  MTU 1514 bytes, BW 1000000 Kbit
GigabitEthernet0/0/0/2|is|administratively|down,|line|protocol|is|down|MTU|1514|bytes,|BW|1000000|Kbit|0|input|errors,|5|CRC,|0|frame|    0 input errors, 5 CRC, 0 frame
```

The key: the first field (`$1` in awk) is always the interface name, even for deeply indented lines. Find interfaces with CRC errors:
```bront
show interfaces
@SAVE interfaces

@PY crc_intfs = bash("grep 'CRC' interfaces.txtdb | awk -F'|' '{print $1}' | sort -u")
@PY print(f"Interfaces with CRC errors:\n{crc_intfs}")
```

**Config output** works the same way:
```
interface GigabitEthernet0/0/0/1
 ipv4 address 10.1.1.1 255.255.255.0
 description Uplink
!
```
```
interface|GigabitEthernet0/0/0/1|interface GigabitEthernet0/0/0/1
interface|GigabitEthernet0/0/0/1|ipv4|address|10.1.1.1|255.255.255.0| ipv4 address 10.1.1.1 255.255.255.0
interface|GigabitEthernet0/0/0/1|description|Uplink| description Uplink
```

Each pipe-delimited field becomes `col1`, `col2`, `col3`, etc. in SQL queries — or use bash tools directly.

### Processing txtdb with Bash Pipelines

The pipe-delimited format works naturally with grep, sed, awk:

**Find interfaces with input errors:**
```bront
show interfaces
@SAVE interfaces

@PY error_intfs = bash("grep 'input errors' interfaces.txtdb | awk -F'|' '$7 > 0 {print $1}'")
@PY print(f"Interfaces with errors:\n{error_intfs}")
```

**Extract specific fields with awk:**
```bront
show ip interface brief
@SAVE brief

@PY result = bash("awk -F'|' '$5 ~ /down/ {print $1, $5}' brief.txtdb")
@PY print(result)
```

**Count occurrences:**
```bront
show interfaces
@SAVE interfaces

@PY up_count = bash("grep -c '|is|up|' interfaces.txtdb")
@PY down_count = bash("grep -c '|is|down|' interfaces.txtdb")
@PY print(f"Up: {up_count}, Down: {down_count}")
```

### Advanced: SQL Queries with @QUERY

For most scripts, `bash()` with grep/awk on txtdb files is all you need. `@QUERY` is for advanced use cases — joining data across multiple command outputs using SQL:

**Find configured interfaces that are operationally down:**
```bront
show running-config interface
@SAVE config_intf

show interfaces
@SAVE show_intf

@QUERY SELECT c.col2, s.col2 FROM config_intf c
       JOIN show_intf s ON c.col2 = s.col1
       WHERE s.col2 LIKE '%down%' @@@
  @PY print(f"Interface {col2} is configured but DOWN")
  show interface {col2}
@@@
```

**Find interfaces not in ISIS:**
```bront
show running-config interface
@SAVE config_interfaces

show running-config router isis
@SAVE config_isis

@QUERY SELECT c.col2 FROM config_interfaces c
       WHERE c.col2 NOT IN (SELECT col2 FROM config_isis WHERE col1='interface') @@@
  @PY print(f"Interface {col2} not in ISIS")
  show interface {col2}
@@@
```

**Audit BGP neighbors:**
```bront
show running-config router bgp
@SAVE config_bgp

show bgp summary
@SAVE bgp_state

@QUERY SELECT c.col2, s.col6 FROM config_bgp c
       JOIN bgp_state s ON c.col2 = s.col1
       WHERE c.col1 = 'neighbor' AND s.col6 != 'Established' @@@
  @PY print(f"BGP neighbor {col2} configured but state is {col6}")
  show bgp neighbor {col2}
@@@
```

**How @QUERY works:**
- Loads `.txtdb` files as SQL tables (table name = filename without extension)
- Column references: `col1`, `col2`, `col3`, etc.
- Standard SQL: SELECT, WHERE, JOIN, LIKE, IN, NOT IN
- The `@@@` block executes for each row returned, with `{col1}`, `{col2}` substitution

### File Locations

| File | Search Paths |
|------|--------------|
| Device profiles (`.dspy`) | `./`, `~/.bront/`, `/etc/bront/`, collection `profiles/`, embedded fallback |
| Config (`bront.conf`) | `./`, `~/.bront/`, `/etc/bront/` |
| Inventory | `./inventory.yml`, `./inventory.ini`, `./hosts`, `/etc/ansible/hosts` |

## Documentation

- [Full Grammar Reference](docs/GRAMMAR.md)
- [Changelog](CHANGELOG.md)

## Background

Bront evolved from 20+ years of network automation experience. The core concept — write CLI commands directly, capture output in queryable format — has been refined through real production use across enterprise networks.

The philosophy: network engineers think in CLI. Automation tools should meet them there, not force translation into programming abstractions.

## Roadmap

- Console server driver (terminal server access with state detection)
- gNMI/gRPC structured data collection alongside CLI
- Golden config comparison as a first-class feature
- PyPI package for `pip install bront`

## License

MIT

## Contributing

Issues and pull requests welcome. For commercial support or custom development, contact the maintainer.
