#!/usr/bin/env python3
"""
NOMAD fix — Light theme support for all dashboard panels

Adds missing CSS variables and replaces hardcoded dark colors with
CSS variable references so panels render correctly in both themes.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_light_theme.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SERVER_PY = REPO / "nomad" / "viz" / "server.py"

if not SERVER_PY.exists():
    print(f"Error: {SERVER_PY} not found")
    sys.exit(1)

text = SERVER_PY.read_text()
changes = 0


def replace_all(old, new, label):
    global text, changes
    n = text.count(old)
    if n == 0:
        print(f"  SKIP {label} -- not found")
        return
    if new in text and old not in text:
        print(f"  SKIP {label} -- already applied")
        return
    text = text.replace(old, new)
    changes += n
    print(f"  OK   {label} ({n}x)")


def replace_once(old, new, label):
    global text, changes
    if old not in text:
        print(f"  SKIP {label} -- not found")
        return
    if new in text:
        print(f"  SKIP {label} -- already applied")
        return
    text = text.replace(old, new, 1)
    changes += 1
    print(f"  OK   {label}")


# =====================================================================
print("\n[1] Add --bg-secondary, --bg-tertiary, --input-bg to dark theme")
# =====================================================================

replace_once(
    "            --purple: #a371f7;\n"
    "        }",

    "            --purple: #a371f7;\n"
    "            --bg-secondary: #1e293b;\n"
    "            --bg-tertiary: #0f172a;\n"
    "            --input-bg: #1e293b;\n"
    "            --input-border: #334155;\n"
    "            --btn-text: #e2e8f0;\n"
    "        }",

    "css/dark_theme_vars")


# =====================================================================
print("\n[2] Add --bg-secondary, --bg-tertiary, --input-bg to light theme")
# =====================================================================

replace_once(
    "            --purple: #6b21a8;\n"
    "        }",

    "            --purple: #6b21a8;\n"
    "            --bg-secondary: #f0f2f5;\n"
    "            --bg-tertiary: #e8eaed;\n"
    "            --input-bg: #ffffff;\n"
    "            --input-border: #c0c6cc;\n"
    "            --btn-text: #1a1a1a;\n"
    "        }",

    "css/light_theme_vars")


# =====================================================================
print("\n[3] Replace hardcoded #1e293b with var(--bg-secondary)")
# =====================================================================

# In inline styles, #1e293b appears as background, border-bottom, etc.
# Replace all bare occurrences (not already wrapped in var())

# Background uses
replace_all(
    "background: '#1e293b'",
    "background: 'var(--bg-secondary)'",
    "inline/bg_secondary_sq")

replace_all(
    'background: "#1e293b"',
    'background: "var(--bg-secondary)"',
    "inline/bg_secondary_dq")

replace_all(
    "background:'#1e293b'",
    "background:'var(--bg-secondary)'",
    "inline/bg_secondary_nospc")

# Border uses
replace_all(
    "borderBottom: '1px solid #1e293b'",
    "borderBottom: '1px solid var(--border)'",
    "inline/border_1e293b")

replace_all(
    "border:'1px solid #1e293b'",
    "border:'1px solid var(--border)'",
    "inline/border_1e293b_nospc")


# =====================================================================
print("\n[4] Replace hardcoded #0f172a with var(--bg-tertiary)")
# =====================================================================

replace_all(
    "background:'#0f172a'",
    "background:'var(--bg-tertiary)'",
    "inline/bg_tertiary")


# =====================================================================
print("\n[5] Replace hardcoded #334155 with var(--input-border)")
# =====================================================================

replace_all(
    "border:'1px solid #334155'",
    "border:'1px solid var(--input-border)'",
    "inline/input_border_nospc")

replace_all(
    "border: '1px solid #334155'",
    "border: '1px solid var(--input-border)'",
    "inline/input_border")


# =====================================================================
print("\n[6] Replace hardcoded #e2e8f0 with var(--btn-text)")
# =====================================================================

replace_all(
    "color:'#e2e8f0'",
    "color:'var(--btn-text)'",
    "inline/btn_text_nospc")

replace_all(
    "color: '#e2e8f0'",
    "color: 'var(--btn-text)'",
    "inline/btn_text")


# =====================================================================
# Write and report
# =====================================================================
SERVER_PY.write_text(text)

print(f"\n{'='*60}")
print(f"Total replacements: {changes}")
print()
