# bront.network - Embedded Device Profiles
# Bront Language v3.6
#
# Profiles are embedded here so they are included in the Ansible
# AnsiballZ payload. The payload only bundles modules/ and module_utils/,
# so the top-level profiles/ directory is not available at runtime.

"""
Embedded device profile content.

Each profile is stored as a string keyed by network_os name.
These are used as a fallback when the .dspy file cannot be found
on the filesystem (e.g., inside Ansible's zip payload).
"""

EMBEDDED_PROFILES = {

    'eos': """\
## eos.dspy - Arista EOS Device Profile
## Place in: ./ or ~/.bront/ or /etc/bront/

## begin commands start
show clock
term len 0
term width 0
@ONPROMPT "Uncommitted changes found"
@RESPONSE "no"
@ONPROMPT "Do you wish to proceed with this commit anyway"
@RESPONSE "no"
## begin commands end

## logout commands start
show clock
exit
## logout commands end
""",

    'ios': """\
# ios.dspy - Cisco IOS Device Profile
# Place in: ./ or ~/.bront/ or /etc/bront/
## begin commands start
show clock
terminal length 0
terminal width 0
show privilege
@PY priv = int(re.search(r'level.*?(\\d+)', buffer).group(1)) if 'level' in buffer else 15
@PY if priv < 15:
    enable
    @PROMPT "assword:" "$ENABLE_PASSWORD"
## begin commands end
## logout commands start
show clock
exit
## logout commands end
""",

    'iosxr': """\
# iosxr.dspy - Cisco IOS-XR Device Profile
# Place in: ./ or ~/.bront/ or /etc/bront/

## begin commands start
@PERMAPROMPT RP/\\d+/\\S+:.*#|RP/\\d+/\\S+:.*>|sysadmin-vm:.*#|sysadmin-vm:.*>
show clock
terminal length 0
terminal width 0
## begin commands end

## logout commands start
show clock
exit
## logout commands end
""",

    'junos': """\
## junos.dspy - Juniper Junos Device Profile
## Place in: ./ or ~/.bront/ or /etc/bront/

## begin commands start
@PERMAPROMPT \\S+@\\S+>|\\S+@\\S+#|\\S+@\\S+%|sftp>
set cli screen-length 0
set cli screen-width 1024
show system uptime
@ONPROMPT "Discard uncommitted changes"
@RESPONSE "yes"
## begin commands end

## logout commands start
exit
## logout commands end
""",

    'nokia': """\
## nokia.dspy - Nokia SR OS Device Profile
## Place in: ./ or ~/.bront/ or /etc/bront/

## begin commands start
@PERMAPROMPT ^A:.*#|^A:.*$|^A:.*>|A:.*#|A:.*>|B:.*#|B:.*>
environment no more
## begin commands end

## logout commands start
logout
## logout commands end
""",

    'nxos': """\
# nxos.dspy - Cisco NX-OS Device Profile
# Place in: ./ or ~/.bront/ or /etc/bront/
## begin commands start
show clock
terminal length 0
terminal width 511
## begin commands end
## logout commands start

show clock
exit
## logout commands end
""",

}


def get_embedded_profile(network_os: str) -> str:
    """
    Get embedded profile content for a network OS.

    Args:
        network_os: Network OS identifier (e.g., 'iosxr', 'eos')

    Returns:
        Profile content string, or None if not found
    """
    return EMBEDDED_PROFILES.get(network_os)
