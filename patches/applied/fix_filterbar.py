#!/usr/bin/env python3
"""Fix FilterBar flicker in Resources and Activity tabs.

Usage: python3 fix_filterbar.py /path/to/nomad/nomad/viz/server.py
"""
import sys

path = sys.argv[1]
content = open(path).read()

# The pattern: const FilterBar = () => ... ; return ...createElement(FilterBar),
# Replace with: return ...createElement('div', {style: eduStyles.filterBar}, ...selects...)

FILTER_SELECTS = """React.createElement('div', {style: eduStyles.filterBar},
                        React.createElement('select', {value: filters.cluster, onChange: e => setFilters({...filters, cluster: e.target.value}), style: eduStyles.select},
                            React.createElement('option', {value: 'all'}, 'All Clusters'),
                            (data.filters.clusters || []).map(c => React.createElement('option', {key: c, value: c}, c))
                        ),
                        React.createElement('select', {value: filters.group, onChange: e => setFilters({...filters, group: e.target.value}), style: eduStyles.select},
                            React.createElement('option', {value: 'all'}, 'All Groups'),
                            (data.filters.groups || []).map(g => React.createElement('option', {key: g, value: g}, g))
                        ),
                        React.createElement('select', {value: filters.days, onChange: e => setFilters({...filters, days: e.target.value}), style: eduStyles.select},
                            React.createElement('option', {value: '7'}, 'Last 7 days'),
                            React.createElement('option', {value: '30'}, 'Last 30 days'),
                            React.createElement('option', {value: '90'}, 'Last 90 days'),
                            React.createElement('option', {value: '365'}, 'Last year')
                        )
                    ),"""

lines = content.split('\n')
new_lines = []
skip_until_return = False
n = 0

i = 0
while i < len(lines):
    line = lines[i]

    # Detect start of FilterBar definition
    if 'const FilterBar = () =>' in line:
        # Skip all lines until we hit the return statement
        skip_until_return = True
        i += 1
        continue

    if skip_until_return:
        if line.strip().startswith('return React.createElement'):
            skip_until_return = False
            # Next line should be React.createElement(FilterBar),
            # Check the next line
            if i + 1 < len(lines) and 'React.createElement(FilterBar)' in lines[i + 1]:
                # Output the return line but replace next line
                new_lines.append(line)
                new_lines.append('                    ' + FILTER_SELECTS)
                i += 2  # skip the FilterBar line
                n += 1
                continue
            else:
                new_lines.append(line)
                i += 1
                continue
        else:
            i += 1
            continue

    new_lines.append(line)
    i += 1

if n > 0:
    open(path, 'w').write('\n'.join(new_lines))
    print(f"Fixed {n} FilterBar definitions (inlined)")
else:
    print("Could not find FilterBar pattern via line scan")
    print(f"'const FilterBar' count: {content.count('const FilterBar')}")
    print(f"'React.createElement(FilterBar)' count: {content.count('React.createElement(FilterBar)')}")
