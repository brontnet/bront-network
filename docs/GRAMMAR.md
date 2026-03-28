# Bront Language Grammar v3.6
# Network Device Automation Language
# January 2026

## Complete EBNF Grammar

```ebnf
(* ============================================ *)
(* Bront Language v3.6 - Complete EBNF Grammar *)
(* ============================================ *)

bront_script          = { statement } ;

statement             = comment
                      | prompt_directive
                      | onerror_directive
                      | report_directive
                      | save_directive
                      | rsave_directive
                      | include_directive
                      | dryrun_directive
                      | diagnostics_directive
                      | py_directive
                      | query_directive
                      | silent_command
                      | cli_command
                      | blank_line ;

(* ============================================ *)
(* Comments - Require ## or More               *)
(* ============================================ *)

comment               = "##" , { any_character } , newline ;

(* Note: Single # is NOT a comment - it's valid in device configs *)
(* Example: "# community-set EXAMPLE" is a CLI command *)

(* ============================================ *)
(* Prompt Management                           *)
(* ============================================ *)

prompt_directive      = permaprompt | prompt_response ;

permaprompt           = "@PERMAPROMPT" , whitespace , quoted_string ;

prompt_response       = "@PROMPT" , whitespace , quoted_string ,
                        newline , quoted_string ;

(* ============================================ *)
(* Error Handling                              *)
(* ============================================ *)

onerror_directive     = "@ONERROR" , whitespace , error_patterns ;

error_patterns        = quoted_string ;
                        (* Pipe-separated patterns: "error|failed|invalid" *)

report_directive      = "@REPORT" , whitespace , format_string ,
                        [ whitespace , "CONTEXT=" , integer ] ;

format_string         = quoted_string ;
                        (* Format specifiers: %d=device, %t=time, %s=context *)

(* ============================================ *)
(* File Save Operations                        *)
(* ============================================ *)

save_directive        = "@SAVE" , whitespace , filename ,
                        [ whitespace , normalize_clause ] ;

rsave_directive       = "@RSAVE" , whitespace , filename ,
                        [ whitespace , normalize_clause ] ;

filename              = identifier | variable_substitution ;

normalize_clause      = normalize_single | normalize_multiline ;

normalize_single      = "NORMALIZE" , whitespace , pipeline_command ;

normalize_multiline   = "NORMALIZE" , whitespace , "@@@" , newline ,
                        { pipeline_line } ,
                        "@@@" ;

pipeline_command      = shell_command , { whitespace , "|" , whitespace , shell_command } ;

pipeline_line         = shell_command , [ whitespace , "|" ] , newline ;

shell_command         = { any_character - "|" - newline } ;

(* ============================================ *)
(* Include Directive                           *)
(* ============================================ *)

include_directive     = "@INCLUDE" , whitespace , filepath ;

filepath              = { any_character - newline } ;
                        (* Relative to including script's directory *)

(* ============================================ *)
(* Dry Run Directive                           *)
(* ============================================ *)

dryrun_directive      = dryrun_single | dryrun_block ;

dryrun_single         = "@DRYRUN" , whitespace , device_command ;

dryrun_block          = "@DRYRUN" , whitespace , "{" , newline ,
                        { device_command } ,
                        "}" ;

(* Note: @DRYRUN commands are echoed but not executed in --dry-run mode *)

(* ============================================ *)
(* Diagnostics Directive                       *)
(* ============================================ *)

diagnostics_directive = "@DIAGNOSTICS" ;

(* Note: When present, wraps each CLI command with timestamp headers:
   ### 2026-01-19 14:32:05.123456 CMD_START 0.0s show ip interface brief
   <command output>
   ### 2026-01-19 14:32:07.654321 CMD_END 2.530865s show ip interface brief
   
   - Timestamps include microseconds
   - Duration shows elapsed time for command execution
   - Only applies to CLI commands, not @SILENT commands
   - Output goes to buffer and log file, not stderr
*)

(* ============================================ *)
(* Python Integration                          *)
(* ============================================ *)

py_directive          = py_single | py_multiline | py_block ;

py_single             = "@PY" , whitespace , python_statement ;

py_multiline          = "@PY" , whitespace , "@@@" , newline ,
                        { python_line } ,
                        "@@@" ;

py_block              = "@PY" , whitespace , block_opener , newline ,
                        { indented_statement } ;

block_opener          = ( "if" | "for" | "while" | "elif" ) , whitespace ,
                        expression , ":" 
                      | "else" , ":" ;

indented_statement    = indent , ( statement | py_directive ) ;
                        (* Block ends when indentation returns to base level *)

expression            = { any_character - ":" - newline } ;

python_statement      = { any_character - newline } ;

python_line           = { any_character } , newline ;

indent                = whitespace , { whitespace } ;
                        (* 4 spaces or 1 tab recommended *)

(* ============================================ *)
(* SQL Query Operations                        *)
(* ============================================ *)

query_directive       = query_basic | query_loop ;

query_basic           = "@QUERY" , [ whitespace , "VERBOSE" ] ,
                        whitespace , sql_query ;

query_loop            = "@QUERY" , [ whitespace , "VERBOSE" ] ,
                        whitespace , sql_query , whitespace , "@@@" , newline ,
                        { loop_command } ,
                        "@@@" ;

sql_query             = "SELECT" , { any_character - "@@@" } ;

loop_command          = save_directive
                      | rsave_directive
                      | py_directive
                      | cli_command
                      | comment
                      | blank_line ;

(* ============================================ *)
(* Command Execution                           *)
(* ============================================ *)

silent_command        = "@SILENT" , whitespace , device_command ;

cli_command           = device_command ;

device_command        = { any_character - newline } , newline ;
                        (* May contain $varname for variable substitution *)

(* ============================================ *)
(* Variable Substitution                       *)
(* ============================================ *)

variable_substitution = "$" , identifier ;

identifier            = letter , { letter | digit | "_" } ;

(* ============================================ *)
(* Lexical Elements                            *)
(* ============================================ *)

quoted_string         = '"' , { any_character - '"' } , '"' ;

regex_pattern         = "/" , { any_character - "/" } , "/" ;

integer               = digit , { digit } ;

letter                = "A" | "B" | ... | "Z" | "a" | "b" | ... | "z" ;

digit                 = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

whitespace            = " " | tab ;

newline               = "\n" | "\r\n" ;

blank_line            = { whitespace } , newline ;

any_character         = (* any Unicode character *) ;

(* ============================================ *)
(* End of Grammar                              *)
(* ============================================ *)
```

## Grammar Notes

### Version History
- **v3.6** (January 2026) - Added @DRYRUN, @PY blocks, @INCLUDE, $var substitution, send()/expect()
- **v3.5** (December 2025) - Added VERBOSE, @SILENT, ## comments
- **v3.4** (December 2025) - Added @QUERY, multiline blocks, NORMALIZE
- **v3.3** (Earlier) - Added @ONERROR/@REPORT, @RSAVE
- **v3.2** (Earlier) - Added @PY, variable substitution
- **v3.1** (Earlier) - Core directives and BrontPath

### Key Features in v3.6

1. **@DRYRUN Directive**
   - Commands marked with @DRYRUN are skipped in --dry-run mode
   - Single command: `@DRYRUN configure terminal`
   - Block syntax: `@DRYRUN { ... }`
   - Use for destructive commands (config changes, commits)

2. **@PY Control Blocks**
   - Python if/for/while with CLI commands in body
   - Indentation determines block membership
   - Variables accessible via $varname in CLI commands
   - Example:
     ```bront
     @PY for vrf in ['red', 'blue']:
         vrf context $vrf
         ip route 10.0.0.0/8 $nexthop
         exit
     ```

3. **@INCLUDE Directive**
   - Include other bront files
   - Paths relative to including script
   - Recursive includes supported
   - Circular include detection

4. **Variable Substitution**
   - Use `$varname` in CLI commands
   - Variables set via @PY
   - Works in @QUERY loops with column names

5. **Python Functions**
   - `send(cmd)` - Send command to device
   - `expect(pattern)` - Wait for pattern
   - `bash(cmd)` - Run shell command
   - Available in @PY blocks for low-level control

### Directive Summary

| Directive | Purpose | Options |
|-----------|---------|---------|
| `@PERMAPROMPT "pattern"` | Set permanent prompt | Pipe-separated patterns |
| `@PROMPT "pattern" "response"` | One-time prompt/response | - |
| `@ONERROR "patterns"` | Define error patterns | Pipe-separated |
| `@REPORT "format"` | Report error match | CONTEXT=N |
| `@SAVE file` | Save buffer + txtdb | NORMALIZE |
| `@RSAVE file` | Save buffer only | NORMALIZE |
| `@INCLUDE file` | Include bront file | Relative paths |
| `@DRYRUN cmd` | Dry-run protected | Block { } |
| `@PY code` | Execute Python | Multiline @@@, Blocks |
| `@QUERY sql` | SQL query | VERBOSE, Loop @@@ |
| `@SILENT command` | Silent execution | - |

### Python Globals

| Variable/Function | Description |
|-------------------|-------------|
| `buffer` | Current output buffer |
| `device_name` | Device hostname |
| `enable_password` | Enable password from inventory |
| `re` | Python regex module |
| `send(cmd, silent=False)` | Send command to device |
| `expect(pattern)` | Wait for pattern, capture output |
| `bash(cmd)` | Run shell command, return output |
| `print(...)` | Print to output |

### Variable Substitution

Variables can be used in:
- CLI commands: `show interface $iface`
- @SAVE/@RSAVE filenames: `@SAVE ${device}_output`
- @QUERY loop commands: Column names as `$col1`, `$col2`

### @PY Block Examples

**Conditional:**
```bront
@PY priv = int(re.search(r'level.*?(\d+)', buffer).group(1)) if 'level' in buffer else 15
@PY if priv < 15:
    enable
    @PROMPT "assword:" "$ENABLE_PASSWORD"
```

**Loop:**
```bront
@PY for vrf in ['management', 'production', 'backup']:
    vrf context $vrf
    ip route 10.0.0.0/8 $gateway
    exit
```

**Nested:**
```bront
@PY for region in regions:
    @PY for router in region.routers:
        show interface $router
        @SAVE ${region}_${router}_interfaces
```

### @DRYRUN Examples

**Single command:**
```bront
show version
@DRYRUN configure terminal
@DRYRUN commit
show running-config
```

**Block:**
```bront
show version
@DRYRUN {
configure terminal
router bgp 65000
  neighbor 10.0.0.1 shutdown
commit
}
show bgp summary
```

**Execution modes:**
```bash
# Normal - all commands execute
bront deploy.bront ROUTER1

# Dry-run - @DRYRUN commands echoed only
bront deploy.bront ROUTER1 --dry-run
```

### @INCLUDE Examples

**Main script:**
```bront
@INCLUDE common/prompts.bront
@INCLUDE common/error_handlers.bront

show version
@SAVE version

@INCLUDE checks/interface_check.bront
@INCLUDE checks/bgp_check.bront
```

**Included file (common/error_handlers.bront):**
```bront
@ONERROR "error|failed|invalid"
@REPORT "ERROR on %d at %t:\n%s" CONTEXT=3
```

### Device Profile (.dspy)

```
# ios.dspy - Cisco IOS Device Profile
## begin commands start
show clock
terminal length 0
terminal width 0
show privilege
@PY priv = int(re.search(r'level.*?(\d+)', buffer).group(1)) if 'level' in buffer else 15
@PY if priv < 15:
    enable
    @PROMPT "assword:" "$ENABLE_PASSWORD"
## begin commands end
## logout commands start
show clock
exit
## logout commands end
```

### Multiline Blocks

Delimited with `@@@`:
```bront
@PY @@@
for item in items:
    process(item)
result = compute()
@@@

@SAVE file NORMALIZE @@@
grep pattern |
sed 's/old/new/' |
sort -u
@@@

@QUERY SELECT col1, col2 FROM table @@@
show interface $col1
@SAVE ${col1}_detail
@@@
```

### Error Handling

```bront
## Error patterns (pipe-separated in quotes)
@ONERROR "error|failed|invalid"
@REPORT "ERROR on %d at %t:\n%s" CONTEXT=3

## Format specifiers:
## %d = device name
## %t = timestamp
## %s = context (matched lines)
```

### File Operations

```bront
## Basic save (creates .txtdb for SQL queries)
@SAVE output

## With normalization
@SAVE clean NORMALIZE grep pattern | sort

## Raw save (no .txtdb)
@RSAVE raw.txt

## Variable in filename
@PY device = "ROUTER1"
@SAVE ${device}_config
```

### Reserved Keywords

- `@PERMAPROMPT`
- `@PROMPT`
- `@ONERROR`
- `@REPORT`
- `@SAVE`
- `@RSAVE`
- `@INCLUDE`
- `@DRYRUN`
- `@PY`
- `@QUERY`
- `@SILENT`
- `CONTEXT`
- `NORMALIZE`
- `VERBOSE`
- `SELECT` (in @QUERY)
- `@@@` (multiline delimiter)

### Execution Model

1. **Parse Phase**
   - Parse .bront file
   - Expand @INCLUDE directives
   - Parse @PY blocks with indentation
   - Build directive tree

2. **Execution Phase**
   - Connect to device via SSH
   - Auto-detect privilege level (if in .dspy)
   - Execute directives sequentially
   - Handle @PY blocks conditionally
   - Buffer output
   - Save files
   - Execute queries
   - Check errors
   - Log everything

3. **Output**
   - **Stdout**: Command output (unless @SILENT)
   - **Logs**: All output logged
   - **Files**: @SAVE/@RSAVE outputs
   - **Errors**: Matched errors reported
   - **Dry-run**: @DRYRUN commands echoed with timestamp

### Inventory Variables

```yaml
ROUTER1:
  ansible_host: 192.168.1.1
  ansible_network_os: ios
  ansible_user: admin
  ansible_password: loginpass
  ansible_enable_password: enablesecret  # optional
  ansible_port: 22
```

### Command Line Usage

**Standalone:**
```bash
bront script.bront HOSTNAME
bront script.bront HOSTNAME -i inventory.yml
bront script.bront HOSTNAME --dry-run
bront script.bront HOSTNAME --vault-password-file .vault_pass
```

**Ansible:**
```bash
ansible-playbook -i inventory.ini playbook.yml -l HOSTNAME
ansible-playbook -i inventory.ini playbook.yml -l "HOST1,HOST2" -f 5
ansible-playbook -i inventory.ini playbook.yml -e "dry_run=true"
```

## Compliance

This grammar follows:
- **EBNF ISO/IEC 14977** notation
- **Bront Language Design Principles**:
  - "Write what you would type on the CLI — nothing more"
  - Device-agnostic core
  - Python integration for power
  - SQL for data querying
  - Clean, readable syntax

## Implementation

Reference implementation: **bront.network v1.1.0**

Features:
- Combined Ansible collection + standalone CLI
- Full grammar support
- Python 3.8+ compatible
- Pexpect-based SSH execution
- SQLite integration for @QUERY
- Ansible inventory support (YAML/INI)
- Vault password support
- Comprehensive logging
- Error handling with context
- Dry-run mode

---

**Bront Language v3.6**
Network Device Automation Redefined
January 2026
