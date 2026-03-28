# Bront Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.17] - 2026-02-11

### Added
- **@ONPROMPT/@RESPONSE directive pair**
  - Global session watcher for interactive prompts that can appear at any time
  - Unlike @PROMPT (positional), @ONPROMPT watches the entire session
  - Automatically sends @RESPONSE when pattern matches, then resumes normal operation
  - Used in device profiles for handling logout confirmations, uncommitted changes, etc.
  - Pexpect driver builds combined expect list: onprompt patterns + prompt patterns
  - Supports multiple @ONPROMPT handlers per session

- **Arista EOS device profile** (`eos.dspy`)
  - `term len 0` / `term width 0` for paging
  - @ONPROMPT handlers for uncommitted config change prompts

- **Nokia SR OS device profile** (`nokia.dspy`)
  - `environment no more` for paging
  - @PERMAPROMPT for A:/B: active/backup RP prompts

- **Juniper Junos device profile** (`junos.dspy`)
  - `set cli screen-length 0` / `set cli screen-width 1024` for paging
  - @PERMAPROMPT for user@host patterns across operational/config/shell modes
  - @ONPROMPT handler for uncommitted changes on exit

- **Embedded profiles in module_utils** (`profiles.py`)
  - All device profiles embedded as Python data in `module_utils/bront_core/profiles.py`
  - Automatically included in Ansible's AnsiballZ payload
  - Filesystem .dspy files still take priority (searched first)
  - Fallback to embedded profiles when .dspy files not found

### Fixed
- **Pexpect driver `str.decode()` crash** — pexpect spawned with `encoding='utf-8'`
  returns `str` objects, but `send_command()`, `send_interactive()`, and
  `expect_pattern()` called `.decode('utf-8')` on them, causing
  `AttributeError: 'str' object has no attribute 'decode'`. Removed all
  `.decode()` calls. This was the root cause of standalone sessions that
  connected but executed zero commands — the exception was silently caught
  by the executor's broad `except Exception`.

- **Ansible profile not found in AnsiballZ payload** — the `profiles/`
  directory is outside `modules/` and `module_utils/`, so Ansible never
  bundles it into the zip payload. Added `profiles.py` with embedded
  content as fallback.

- **Standalone silent execution failures** — when `executor.execute()`
  caught an exception and set `result['failed'] = True`, the standalone
  script only checked `error_buffer` (the @ONERROR buffer), not
  `result['failed']`. Added explicit failure reporting.

- **`report()` built-in for @PY blocks** — emit structured findings
  programmatically from Python code. Same pipeline as `@REPORT`:
  JSON files, Ansible return values, standalone summary.
  `report(msg, severity="high", detail={})`. Source field is `py`
  instead of `report` to distinguish from pattern-matched findings.

- **`{var}` substitution in CLI commands** — CLI commands inside
  `@PY for/if` blocks now support both `$var` and `{var}` syntax.
  Previously only `$var` worked; `{var}` was only available in
  `@QUERY` loop bodies. Both now resolve from the Python namespace.

- **Empty string filtering in `@PY for` loops** — when iterating
  over `"".split('\n')` (e.g., grep returned no matches), the loop
  no longer executes once with an empty string. Empty strings are
  filtered from list iterables automatically.

### Device Profiles
| Profile | Platform | Paging | Special Handling |
|---------|----------|--------|-----------------|
| `ios.dspy` | Cisco IOS | `terminal length 0` | Enable mode detection |
| `iosxr.dspy` | Cisco IOS-XR | `terminal length 0` | — |
| `nxos.dspy` | Cisco NX-OS | `terminal length 0` | — |
| `eos.dspy` | Arista EOS | `term len 0` | Uncommitted changes prompt |
| `nokia.dspy` | Nokia SR OS | `environment no more` | A:/B: RP prompts |
| `junos.dspy` | Juniper Junos | `set cli screen-length 0` | Uncommitted changes prompt |

## [2.0.16] - 2026-02-06

### Added
- **Unified run_id directory structure**
  - New `run_id` parameter for Ansible module and standalone CLI (`--run-id`)
  - All device outputs organized under `workdir/run_id/hostname/`
  - All device logs organized under `logdir/run_id/`
  - Compatible with Tower/AWX `tower_job_id`
  - Auto-generated when not provided (legacy behavior preserved)

- **Structured findings system**
  - `@REPORT` now emits structured JSON findings with device/command metadata
  - New `SEVERITY=` parameter on `@REPORT` (high, medium, low, info; default: high)
  - Per-device findings written to `workdir/run_id/hostname_findings.json`
  - `merge_findings()` static method combines all device findings into one file
  - Findings returned in Ansible module results as `findings[]` array
  - Supports JSON and CSV output formats for merged findings

### Directory Structure (with run_id)
```
bront_work/
  <run_id>/
    ROUTER1/           # per-device work files
    ROUTER2/
    ROUTER1_findings.json
    ROUTER2_findings.json
    findings.json      # merged (after merge_findings)
    findings.csv       # optional CSV export

bront_logs/
  <run_id>/
    ROUTER1_output.log
    ROUTER1_error.log
    ROUTER1_bront.log
    ROUTER2_output.log
    ...
```

### Finding Structure
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

### Usage
```yaml
# Ansible - generate shared run ID
- set_fact:
    bront_run_id: "{{ tower_job_id | default(lookup('pipe', 'date +%Y%m%d%H%M%S')) }}"
  run_once: true

# Run on all devices with shared run_id
- bront.network.bront:
    script: audit.bront
    run_id: "{{ bront_run_id }}"

# @REPORT with severity
@ONERROR "CRC|input error"
@REPORT "CRC errors on %d: %s" SEVERITY=high
```

```bash
# Standalone CLI
bront audit.bront ROUTER1 --run-id 20260206_audit
```

**Base Version:** 2.0.15

---

## [2.0.15] - 2026-01-21

### Added
- **Custom script variables**
  - Standalone CLI: `-e key=value` or `--var key=value` (can be used multiple times)
  - Ansible module: `vars:` parameter (dict)
  - Variables available in `@PY` blocks and `{var}` substitutions
  - Numeric values auto-converted to int/float

### Usage

**Standalone:**
```bash
bront check.bront ROUTER1 -e interface=Gig0/0/0/1 -e threshold=1000
```

**Ansible:**
```yaml
- bront.network.bront:
    script: check.bront
    vars:
      interface: Gig0/0/0/1
      threshold: 1000
```

**In script:**
```bront
show interface {interface}
@PY if errors > threshold:
  print(f"High errors on {interface}")
```

**Base Version:** 2.0.14

---

## [2.0.14] - 2026-01-21

### Fixed
- **BrontPath flattening now produces correct format**
  - Proper hierarchy tracking based on indentation
  - No more empty fields (`||`) in output
  - Parent context (hierarchy prefix) correctly prepended to indented lines
  - Line words split by whitespace, original line preserved at end

### Format
```
hierarchy_words|line_words|original_line
```

### Example
Input:
```
Build Information:
 Built By     : deenayak
```

Output:
```
Build|Information:|Build Information:
Build|Information:|Built|By|:|deenayak| Built By     : deenayak
```

**Base Version:** 2.0.13

---

## [2.0.13] - 2026-01-20

### Fixed
- **@PY print() output now appears inline in Ansible mode**
  - Previously print() output was only captured to buffer, not shown in session output
  - Now print() output appears inline in both Ansible and standalone modes
  - Consistent behavior: both modes produce identical session output

**Base Version:** 2.0.12

---

## [2.0.12] - 2026-01-20

### Fixed
- **Console output now matches real terminal session**
  - Prompt no longer adds extra newline before next command
  - Output now shows `ROUTER#show clock` instead of `ROUTER#\nshow clock`
  - More natural reading of CLI session in standalone mode

**Base Version:** 2.0.11

---

## [2.0.11] - 2026-01-20

### Fixed
- **@DIAGNOSTICS markers now display in standalone CLI mode**
  - Added console output for CMD_START/CMD_END markers when `output_mode='console'`
  - Previously markers were only written to buffer/log, not printed to terminal
  - Now works consistently in both Ansible and standalone CLI modes

**Base Version:** 2.0.10

---

## [2.0.10] - 2026-01-19

### Fixed
- **@DIAGNOSTICS markers now on separate lines**
  - Added leading newline before `### CMD_START` and `### CMD_END` markers
  - Prevents markers from concatenating with device prompts
  - Cleaner output for parsing and readability

### Before
```
RP/0/RP0/CPU0:ROUTER#### 2026-01-19 19:56:16.251822 CMD_END 0.320450s show version
```

### After
```
RP/0/RP0/CPU0:ROUTER#

### 2026-01-19 19:56:16.251822 CMD_END 0.320450s show version
```

**Base Version:** 2.0.9

---

## [2.0.9] - 2026-01-19

### Added
- **@DIAGNOSTICS directive for command timing**
  - When present in script, wraps each CLI command with timestamp headers
  - Format: `### YYYY-MM-DD HH:MM:SS.microseconds CMD_START/END duration command`
  - Timestamps include microseconds for precise timing
  - Duration shows elapsed time for each command execution
  - Only applies to CLI commands, not @SILENT commands
  - Output goes to buffer and log file (not stderr)

### Example Output
```
### 2026-01-19 14:32:05.123456 CMD_START 0.0s show ip interface brief
<command output>
### 2026-01-19 14:32:07.654321 CMD_END 2.530865s show ip interface brief
```

### Use Cases
- Performance analysis: identify slow commands
- Log parsing: grep for CMD_START/CMD_END markers
- Debugging: correlate timing with device behavior
- Audit trails: precise command execution timestamps

### Technical Details
- Modified: `plugins/module_utils/bront_core/parser.py`
  - Added `DIAGNOSTICS` to `DirectiveType` enum
  - Added parsing for `@DIAGNOSTICS` directive
- Modified: `plugins/module_utils/bront_core/executor.py`
  - Added `diagnostics_enabled` flag
  - Added `_exec_diagnostics()` method
  - Updated `_send_command()` to emit CMD_START/CMD_END markers when enabled
- Updated: `docs/GRAMMAR.md` with @DIAGNOSTICS specification
- Updated: `README.md` with @DIAGNOSTICS documentation and examples

**Base Version:** 2.0.8

---

## [2.0.8] - 2026-01-19

### Fixed
- **Critical: I/O error when exit/logout closes SSH connection**
  - Fixed `[Errno 5] Input/output error` caused by `exit` command in device profile logout section
  - Logout commands (`exit`, `logout`, `quit`, `disconnect`) are now detected and sent without expecting a prompt
  - Gracefully handles I/O errors when connection closes after logout commands
  - Ansible module no longer fails on clean session exit

### Technical Details
- Modified: `plugins/module_utils/bront_core/executor.py`
  - Updated `_send_command()` to detect logout commands (line ~530)
  - Logout commands sent with `expect_prompt=False` since connection will close
  - Added try/except to gracefully handle I/O errors on logout
  - Non-logout I/O errors are still raised as before

### Problem
The `exit` command in the `.dspy` logout section was sent like a regular CLI command, which tries to expect a prompt after sending. Since `exit` closes the SSH connection, pexpect threw an I/O error when trying to read from the closed connection.

### Solution
Detect logout commands and handle them specially: send without waiting for prompt, and catch expected I/O errors gracefully.

**Base Version:** 2.0.7

---

## [2.0.7] - 2026-01-19

### Fixed
- **Critical: I/O error in @PY blocks inside @QUERY loops**
  - Fixed `[Errno 5] Input/output error` when using `print()` in @PY blocks within @QUERY loops under Ansible
  - @PY blocks in @QUERY loops now use `self.py_globals` which includes the safe `print()` override
  - Previously used Python's built-in `globals()` which exposed raw `print()` to closed stdout

### Technical Details
- Modified: `plugins/module_utils/bront_core/executor.py`
  - Changed `_execute_loop_directive()` to use `self.py_globals.copy()` instead of `globals()` (line ~479-481)
  - Ensures `print()` calls in @QUERY loop @PY blocks are captured to buffer in Ansible mode
  - Standalone CLI unaffected (uses console output mode)

### Problem
When @PY blocks inside @QUERY loops called `print()`, Ansible's redirected/closed stdout caused I/O errors.

### Solution
Use `self.py_globals` which contains the safe `_capture_print()` override for Ansible mode.

**Base Version:** 2.0.6

---

## [2.0.3] - 2026-01-19

### Fixed
- **Critical: Ansible module I/O error**
  - Fixed `[Errno 5] Input/output error` in Ansible module
  - Added safety checks for `sys.stdout.buffer` availability
  - Prevents crashes when stdout is closed/redirected in Ansible context
  - Standalone CLI unaffected (always worked correctly)

### Technical Details
- Modified: `plugins/module_utils/bront_core/drivers/pexpect_driver.py`
  - Added try/except around `sys.stdout.buffer` assignments (lines 67-72, 84-89)
  - Checks `hasattr(sys.stdout, 'buffer')` before accessing
  - Gracefully handles closed/unavailable stdout

### Problem
Ansible redirects/closes stdout when running modules, but pexpect driver tried to set `child.logfile = sys.stdout.buffer`, causing I/O errors.

### Solution
Only set logfile if stdout.buffer is actually available and writable.

**Base Version:** 2.0.2

---

## [2.0.2] - 2026-01-19

### Added
- **Ansible Vault support in standalone CLI**
  - CLI now automatically decrypts `!vault` tags in inventory files
  - Works with `--vault-password-file` parameter
  - Also checks `ANSIBLE_VAULT_PASSWORD` environment variable
  - Falls back to `~/.vault_pass` if present
  - Custom YAML constructor handles vault tags transparently

### Technical Details
- Modified: `scripts/bront`
  - Added vault YAML constructor to `parse_yaml_inventory()` (line ~176)
  - Updated `load_inventory()` to accept and pass vault_password parameter (line ~223)
  - Improved `decrypt_vault_value()` with better error handling (line ~258)
  - Reordered vault password retrieval before inventory loading (line ~508)
- Requires: `ansible-vault` command available in PATH for decryption

### Usage
```bash
# Now works with vault-encrypted inventory
bront script.bront DEVICE -i inventory.yml --vault-password-file .vault_pass

# Or use environment variable
export ANSIBLE_VAULT_PASSWORD="my_password"
bront script.bront DEVICE -i inventory.yml

# Or use default vault file
cp .vault_pass ~/.vault_pass
bront script.bront DEVICE -i inventory.yml
```

**Base Version:** 2.0.1

---

## [2.0.1] - 2026-01-18

### Fixed
- **CRITICAL:** Initial SSH connection now uses @PERMAPROMPT patterns instead of hardcoded `[>#]`
  - Executor extracts @PERMAPROMPT from directives before connecting
  - Driver uses configured prompt patterns for initial connection
  - Fallback to generic pattern if no @PERMAPROMPT defined
  - Fixes timeout issues with non-standard prompts (e.g., `RP/0/RP0/CPU0:router#`)
- Increased SSH connection timeouts to 60 seconds
  - Password prompt timeout: 60s
  - Initial prompt timeout: 60s
  - Handles slow networks and long login banners

### Technical Details
- Modified: `plugins/module_utils/bront_core/executor.py`
  - Added pre-connection @PERMAPROMPT extraction (lines 152-158)
- Modified: `plugins/module_utils/bront_core/drivers/pexpect_driver.py`
  - Uses configured prompt patterns if available (lines 87-95)
  - Added explicit 60s timeouts to connection expects

**Base Version:** 2.0.0

---

## [2.0.0] - 2026-01-17

### Added
- **Complete rename from "clislice/slice" to "bront"**
  - Package: `bront.network`
  - File extension: `.bront`
  - Classes: `BrontExecutor`, `BrontParser`, `BrontCodeGenerator`
  - Configuration: `BrontConfig`, `BrontPath`
  - Directories: `~/.bront/`, `/etc/bront/`
  - Log files: `*_bront.log`, `bront_logs/`

- **Phase 1: Driver Pattern Architecture** (from clislice 1.2.0)
  - Flexible multi-backend support
  - `DriverFactory` with smart driver selection
  - `BaseDriver` abstract interface
  - `PexpectDriver` implementation
  - Prepared for NetmikoDriver and ScrapliDriver

- **Script log file creation**
  - `*_bront.log` now contains executed script
  - Includes expanded content (begin/end commands, @INCLUDE files)
  - $DEVICE placeholders expanded to actual hostname
  - Works in both CLI and Ansible modes

### Fixed
- Output logging now captures device responses, not just commands
  - Fixed: `_send_command()` logs both command and output
  - Fixed: `_exec_prompt()` logs full interaction
- Console output deduplication
  - Removed duplicate prints from executor
  - Driver handles all console output
  - Screen and file output now consistent
- Script log $DEVICE placeholder expansion
  - Placeholders like `$DEVICE`, `$DEVICEPT`, `$DEVICEPR` are expanded
  - Log shows actual executed script with real hostnames

### Changed
- Directory structure: `bront/network/` instead of `network/`
- Collection name: `bront.network` v2.0.0
- All documentation updated for bront branding
- Installation paths updated in examples

### Technical Details
- Files renamed: 8 files, ~30 files modified, ~150 lines changed
- No functional changes from Phase 1 implementation
- 100% backwards compatible at script syntax level
- Breaking changes: Package names, import paths, file extensions

**Base Version:** clislice 1.2.0 (Phase 1)

---

## Version History Summary

| Version | Date | Description | Base Version |
|---------|------|-------------|--------------|
| 2.0.7 | 2026-01-19 | Fixed print() I/O error in @QUERY @PY blocks | 2.0.6 |
| 2.0.3 | 2026-01-19 | Fixed Ansible I/O error | 2.0.2 |
| 2.0.2 | 2026-01-19 | Added vault support to CLI | 2.0.1 |
| 2.0.1 | 2026-01-18 | Fixed @PERMAPROMPT initial connection | 2.0.0 |
| 2.0.0 | 2026-01-17 | Complete rename to bront + Phase 1 drivers | clislice 1.2.0 |
| 1.2.0 | 2026-01-17 | Phase 1: Driver pattern refactoring | clislice 1.1.0 |
| 1.1.0 | (earlier) | Feature additions | - |

---

## Upgrade Notes

### 2.0.3 → 2.0.7
**No breaking changes.** Simply update the collection:
```bash
cd ~/.ansible/collections/ansible_collections
tar -xzf bront-network-2.0.7.tar.gz
```

This is a critical bug fix for @PY blocks using `print()` inside @QUERY loops. All 2.0.x scripts work unchanged.

### 2.0.1 → 2.0.2
**No breaking changes.** Simply update the collection:
```bash
cd ~/.ansible/collections/ansible_collections
tar -xzf bront-network-2.0.2.tar.gz
```

New feature: CLI now supports vault-encrypted inventories automatically.

### 2.0.0 → 2.0.1
**No breaking changes.** Simply update the collection:
```bash
cd ~/.ansible/collections/ansible_collections
tar -xzf bront-network-2.0.1.tar.gz
```

This is a bug fix release. All 2.0.0 scripts work unchanged.

### clislice 1.x → bront 2.0.x
**Breaking changes** - requires migration:
- Rename `.slice` files to `.bront`
- Update playbooks: `clislice:` → `bront:`
- Update imports: `slice_core` → `bront_core`
- Move `~/.clislice/` to `~/.bront/`

See `BRONT_RENAME_SUMMARY.md` for complete migration guide.

---

## Semantic Versioning

Bront follows semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (2.x.x): Breaking changes (rename, API changes)
- **MINOR** (x.1.x): New features (Phase 2: netmiko, Phase 3: scrapli)
- **PATCH** (x.x.1): Bug fixes, no breaking changes

Current: **2.0.1**
Next feature release: **2.1.0** (Phase 2: NetmikoDriver)
