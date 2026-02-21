# Point-by-Point Response to Reviewers

I thank all reviewers for their careful evaluation and constructive suggestions. Below we address each point raised.

---

## Reviewer 1

**Recommendation: Accept**

> Looking at the code on GitHub, a lot of the recently added patching code is inside strings (for monkey-patching various other tools). This makes the code syntax highlight poorly, and makes linting difficult. I recommend instead this code is moved to source code files and these are loaded into the strings through file-slurping.

**Response**: Done. Patching code has been moved to separate source files in `nomad/patching/` and loaded at runtime.

> This would improve the code quality. The patching code could be DRYer, for example by abstracting out the patcher as a class.

**Response**: Done. The patching logic has been refactored into a `Patcher` base class with subclasses for specific targets (SLURM prolog, job scripts, etc.).

> The test coverage could also be significantly improved - perhaps by developing a Mock class for a fictional cluster.

**Response**: Done. We have implemented `MockCluster` in `nomad/testing/__init__.py` that provides:
- Simulated compute nodes across multiple partitions
- Mock SLURM command outputs (`scontrol`, `squeue`, `sacct`)
- Synthetic job data with configurable success/failure rates
- Temporary SQLite database with full schema

This enables comprehensive testing of collectors, feature engineering, and ML components without requiring HPC infrastructure.

---

## Reviewer 2

**Recommendation: Accept**

> While a dark mode is somehow nice for some people, it would be welcome to have a white mode as well, and use those screenshots for the article. That would allow a cleaner view for the readership.

**Response**: Done. The dashboard now includes a light theme toggle. Manuscript figures will be updated with light mode screenshots for improved print readability.

> I would suggest anyway to register a DOI for every release, the way Zenodo does.

**Response**: Done. The software is archived on Zenodo with DOI: https://doi.org/10.5281/zenodo.18614517. Future releases will automatically receive DOIs through GitHub-Zenodo integration.

> I would suggest some other form of release, especially under the Nix environment (for reproducible installations).

**Response**: Thank you for this suggestion. Nix packaging is planned for a future release. Currently, the software is available via PyPI (`pip install nomad-hpc`) and direct installation from GitHub.

> Is it included in the source code? No.

**Response**: Done. All source files now include SPDX license identifiers (`SPDX-License-Identifier: AGPL-3.0-or-later`) and copyright notices.

> Running "nomad edu explain 1104" should provide details about that job id but I get NameError: name '_resolve_db_path' is not defined (a Python error) instead.

**Response**: Fixed. This was a scoping issue in the demo mode database path resolution. The `nomad edu explain` command now works correctly with demo data.

---

## Reviewer 3

**Recommendation: Accept**

> This paper presents NØMAD, a lightweight HPC monitoring and predictive analytics system... I recommend acceptance.

**Response**: Thank you for the positive assessment. I have continued to strengthen the software with additional features (data readiness estimator, infrastructure monitoring, diagnostic tools) as described in the revised manuscript.

---

## Summary of Changes

| Suggestion | Status |
|------------|--------|
| Move patching code to separate files | Done |
| Abstract patching logic into class | Done |
| Implement MockCluster for testing | Done |
| Add light mode to dashboard | Done |
| Update figures with light mode | In progress |
| Register DOI on Zenodo | Done |
| Add Nix packaging | Future work |
| Add license headers to source | Done |
| Fix edu explain in demo mode | Done |

