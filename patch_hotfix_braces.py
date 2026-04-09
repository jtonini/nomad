#!/usr/bin/env python3
"""
NOMAD hotfix — f-string brace escaping in wizard TOML generator

The patch_v1.3.3 script introduced {{ }} inside f-strings where { }
was needed, causing the wizard to output literal brace text instead
of evaluating Python expressions.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_hotfix_braces.py
    python3 -m pytest tests/ -v
    git add -A && git commit -m "fix: f-string brace escaping in wizard TOML generator"
    git push origin main
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
CLI_PY = REPO / "nomad" / "cli.py"

if not CLI_PY.exists():
    print(f"Error: {CLI_PY} not found")
    sys.exit(1)

text = CLI_PY.read_text()
count = 0

replacements = [
    # Regular Python code (not f-string) — {{}} should be {}
    ('c.get("partitions", {{}}).keys())',
     'c.get("partitions", {}).keys())'),

    # f-string expressions — {{expr}} should be {expr}
    ("f'\"{{f}}\"' for f in sorted(all_fs)",
     "f'\"{f}\"' for f in sorted(all_fs)"),

    ('f"filesystems = [{{fs_items}}]"',
     'f"filesystems = [{fs_items}]"'),

    ("f'\"{{p}}\"' for p in sorted(all_parts)",
     "f'\"{p}\"' for p in sorted(all_parts)"),

    ('f"partitions = [{{parts_items}}]"',
     'f"partitions = [{parts_items}]"'),

    ('f"enabled = {{str(any_gpu).lower()}}"',
     'f"enabled = {str(any_gpu).lower()}"'),

    ('f"enabled = {{str(any_nfs).lower()}}"',
     'f"enabled = {str(any_nfs).lower()}"'),

    ('f"enabled = {{str(any_interactive).lower()}}"',
     'f"enabled = {str(any_interactive).lower()}"'),
]

for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        count += 1
        print(f"  Fixed: {old[:60]}...")
    # Don't report skips — if already fixed, that's fine

if count > 0:
    CLI_PY.write_text(text)
    print(f"\nFixed {count} brace escaping issues.")
else:
    print("No issues found — already fixed or different code.")
