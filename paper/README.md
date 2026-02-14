# NØMAD JORS Paper Package

This package contains the submission materials for the Journal of Open Research Software (JORS).

## Contents

```
nomad-jors-paper/
├── README.md                    # This file
├── nomad-jors-paper.tex        # LaTeX source (primary submission)
├── nomad-jors-paper.md         # Markdown version
├── nomad-jors-paper.pdf        # Compiled PDF (draft - needs figures)
└── figures/                     # Figure placeholders (replace with actual files)
    ├── architecture.png
    ├── dashboard.png
    ├── compute.png
    ├── gpu.png
    ├── highmem.png
    └── network.png
```

## To Compile the Final PDF

The included PDF was compiled without the actual figure files. To generate the final PDF with figures:

1. Copy your actual figure files from `~/nomad/paper/figures/` to the `figures/` directory in this package
2. Compile:

```bash
cd nomad-jors-paper
pdflatex nomad-jors-paper.tex
pdflatex nomad-jors-paper.tex  # Run twice for cross-references
```

## Required Figures

| Filename | Description |
|----------|-------------|
| `architecture.png` | System architecture diagram |
| `dashboard.png` | Main web dashboard screenshot |
| `compute.png` | Compute partition view |
| `gpu.png` | GPU partition view |
| `highmem.png` | High-memory partition view |
| `network.png` | 3D job similarity network visualization |

## JORS Submission Notes

- Primary submission format: LaTeX (.tex)
- The Markdown version is provided for reference/alternative use
- Update PyPI version number if a new release is made before submission
- Current version referenced: v0.3.4

## Changes from Previous Version

- Removed biogeography analogy in favor of direct description of similarity networks
- Clarified that SLURM is **optional** - system-level collectors (disk, iostat, mpstat, vmstat) work on any Linux system
- SLURM integration enables job-level analytics but is not required for basic monitoring
- Updated feature engineering description to reflect optional vs required features
