#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
Add light theme toggle to dashboard.

Addresses reviewer concern: "While a dark mode is somehow nice for some 
people, it would be welcome to have a white mode as well."

Dark mode remains default. Toggle persists in localStorage.

Usage:
    python3 patch_light_theme.py nomad/viz/server.py
"""

import sys
from pathlib import Path

# Light theme CSS variables
LIGHT_THEME_CSS = '''
        /* Light theme - toggle with button in header */
        .light-theme {
            --bg-deep: #ffffff;
            --bg-surface: #f6f8fa;
            --bg-elevated: #ffffff;
            --bg-hover: #f3f4f6;
            --border: #d0d7de;
            --text-primary: #1f2328;
            --text-secondary: #656d76;
            --text-muted: #8c959f;
            --green: #1a7f37;
            --yellow: #9a6700;
            --red: #cf222e;
            --cyan: #0969da;
            --purple: #8250df;
        }
        .light-theme .node-card {
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .light-theme .sidebar {
            box-shadow: -2px 0 8px rgba(0,0,0,0.1);
        }
        .light-theme .util-track {
            background: #e1e4e8;
        }
'''

# Theme toggle button CSS
TOGGLE_BUTTON_CSS = '''
        .theme-toggle {
            background: var(--bg-hover);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 6px 12px;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .theme-toggle:hover {
            background: var(--bg-elevated);
            color: var(--text-primary);
        }
        .theme-toggle svg {
            width: 16px;
            height: 16px;
        }
'''

# Theme toggle JavaScript
THEME_JS = '''
    // Theme toggle
    function initTheme() {
        const saved = localStorage.getItem('nomad-theme');
        if (saved === 'light') {
            document.body.classList.add('light-theme');
        }
    }
    function toggleTheme() {
        document.body.classList.toggle('light-theme');
        const isLight = document.body.classList.contains('light-theme');
        localStorage.setItem('nomad-theme', isLight ? 'light' : 'dark');
        // Update button icon
        const btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.innerHTML = isLight 
                ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg> Light'
                : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> Dark';
        }
    }
    initTheme();
'''

# Theme toggle button HTML
TOGGLE_BUTTON_HTML = '''<button class="theme-toggle" onclick="toggleTheme()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> Dark
                </button>'''


def patch_server(path):
    """Add light theme toggle to server.py."""
    content = path.read_text()
    
    if 'light-theme' in content:
        print("  = Light theme already added")
        return True
    
    changes = 0
    
    # 1. Add light theme CSS after :root block
    marker = "            --purple: #a371f7;\n        }"
    if marker in content:
        content = content.replace(marker, marker + LIGHT_THEME_CSS + TOGGLE_BUTTON_CSS, 1)
        changes += 1
        print("  + Added light theme CSS variables")
    else:
        print("  ! Could not find :root CSS block")
        return False
    
    # 2. Add theme toggle button in header
    # Find the header section with the logo/title
    header_marker = '<span class="logo-text">NØMAD</span>'
    if header_marker in content:
        # Add toggle button after the logo
        new_header = header_marker + '\n                ' + TOGGLE_BUTTON_HTML
        content = content.replace(header_marker, new_header, 1)
        changes += 1
        print("  + Added theme toggle button")
    else:
        # Try alternative: add to header-right if it exists
        alt_marker = 'class="header-right">'
        if alt_marker in content:
            content = content.replace(alt_marker, alt_marker + '\n                ' + TOGGLE_BUTTON_HTML, 1)
            changes += 1
            print("  + Added theme toggle button (alt location)")
        else:
            print("  ! Could not find header location for toggle button")
    
    # 3. Add theme JavaScript
    # Find the script section
    script_marker = "document.addEventListener('DOMContentLoaded'"
    if script_marker in content:
        content = content.replace(script_marker, THEME_JS + "\n    " + script_marker, 1)
        changes += 1
        print("  + Added theme toggle JavaScript")
    else:
        # Try to find any script tag
        alt_script = '<script>'
        if alt_script in content:
            content = content.replace(alt_script, alt_script + THEME_JS, 1)
            changes += 1
            print("  + Added theme toggle JavaScript (alt location)")
        else:
            print("  ! Could not find script section")
    
    if changes > 0:
        # Backup and write
        backup = path.with_suffix('.py.theme_bak')
        import shutil
        shutil.copy(path, backup)
        path.write_text(content)
        print(f"  Backup saved to {backup}")
        return True
    
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 patch_light_theme.py nomad/viz/server.py")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    
    print("\nAdding Light Theme Toggle")
    print("=" * 30)
    
    if patch_server(path):
        print("\nDone! Toggle appears in dashboard header.")
        print("Dark mode remains default. Preference saved in localStorage.")
    else:
        print("\nFailed to apply patch.")
        sys.exit(1)


if __name__ == '__main__':
    main()
