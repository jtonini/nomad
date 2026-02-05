#!/usr/bin/env python3
"""Move eduStyles + ResourcesPanel + ActivityPanel outside App().

They were inserted inside function App(), causing React to
recreate them every render → infinite fetch loop.
"""
import sys

path = sys.argv[1]
lines = open(path).readlines()

# Find key line numbers (0-indexed)
edu_start = None  # "const eduStyles = {"
app_line = None   # "function App() {"
activity_end = None

for i, line in enumerate(lines):
    s = line.strip()
    if 'function App()' in s and app_line is None:
        app_line = i
    if 'const eduStyles = {' in s and edu_start is None:
        edu_start = i
    if 'const ActivityPanel = () => {' in s:
        # Now find the closing }; for this component
        # Track brace depth from this line
        depth = 0
        for j in range(i, len(lines)):
            depth += lines[j].count('{') - lines[j].count('}')
            if depth == 0 and j > i:
                activity_end = j
                break

if not all([edu_start, app_line, activity_end]):
    print(f"Could not find markers:")
    print(f"  function App(): line {app_line}")
    print(f"  const eduStyles: line {edu_start}")
    print(f"  ActivityPanel end: line {activity_end}")
    sys.exit(1)

print(f"  function App() at line {app_line + 1}")
print(f"  eduStyles starts at line {edu_start + 1}")
print(f"  ActivityPanel ends at line {activity_end + 1}")

# Extract the block (eduStyles through ActivityPanel closing)
block = lines[edu_start:activity_end + 1]

# Remove from inside App
new_lines = lines[:edu_start] + lines[activity_end + 1:]

# Find where function App() is now (index shifted)
new_app_line = None
for i, line in enumerate(new_lines):
    if 'function App()' in line:
        new_app_line = i
        break

if new_app_line is None:
    print("  ! Lost function App() after removal")
    sys.exit(1)

# Insert block before function App()
# Add a blank line separator
final = (new_lines[:new_app_line]
         + ['\n']
         + block
         + ['\n']
         + new_lines[new_app_line:])

open(path, 'w').writelines(final)

# Verify
content = open(path).read()
for name in ['eduStyles', 'ResourcesPanel', 'ActivityPanel']:
    idx = content.index(f'const {name}')
    app_idx = content.index('function App()')
    pos = "BEFORE" if idx < app_idx else "INSIDE"
    print(f"  {name}: {pos} App()")

print("  Done!")
