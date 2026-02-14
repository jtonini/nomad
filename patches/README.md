# NØMAD Patches

## Directory Structure
```
patches/
├── README.md           # This file
└── applied/            # Historical migration scripts (already applied)
```

## Applied Patches

The `applied/` directory contains one-time migration scripts that were used during development to add features incrementally. These patches have already been applied to the codebase and are preserved for historical reference only.

**Do not run these scripts** — they may fail or cause issues since the code has evolved.

## Writing New Patches

For future patches, use the `nomad.patching.Patcher` framework:
```python
from nomad.patching import Patcher, Patch

patcher = Patcher('/path/to/nomad')
patcher.add(Patch(
    file='collectors/node_state.py',
    name='add_cluster_column',
    old='self.nodes = config.get(...)',
    new='self.nodes = config.get(...)\nself.cluster_name = ...',
    skip_if_present='self.cluster_name',  # Idempotent
))

# Validate first
errors = patcher.validate()
if errors:
    print("Cannot apply:", errors)
else:
    result = patcher.apply()
    print(result.summary())
```

### Benefits

- **Proper syntax highlighting**: Patch content in separate `.py` files
- **Linting support**: Code checked by IDE and CI
- **Idempotent**: Patches skip if already applied
- **Dry run**: Preview changes before applying
- **Automatic backups**: Original files preserved with `.bak` suffix
