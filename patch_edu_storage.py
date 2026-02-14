#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
Integrate proficiency score storage into NØMAD.

Changes:
    1. nomad/edu/storage.py   — New file with schema and logging functions
    2. nomad/edu/__init__.py  — Export storage functions
    3. nomad/edu/explain.py   — Save scores after computation
    4. nomad/demo.py          — Add proficiency_scores table to demo schema

Usage:
    python3 patch_edu_storage.py /path/to/nomad/
"""

import sys
import shutil
from pathlib import Path


def patch_edu_init(nomad_dir: Path) -> bool:
    """Update edu/__init__.py to export storage functions."""
    path = nomad_dir / 'edu' / '__init__.py'
    content = path.read_text()
    
    if 'save_proficiency_score' in content:
        print("  = edu/__init__.py already has storage exports")
        return True
    
    # Add imports
    addition = '''
# Storage functions for proficiency tracking
from nomad.edu.storage import (
    init_proficiency_table,
    save_proficiency_score,
    get_user_proficiency_history,
    get_group_proficiency_stats,
)
'''
    
    content += addition
    path.write_text(content)
    print("  + Added storage exports to edu/__init__.py")
    return True


def patch_explain(nomad_dir: Path) -> bool:
    """Update explain.py to save scores after computation."""
    path = nomad_dir / 'edu' / 'explain.py'
    content = path.read_text()
    
    if 'save_proficiency_score' in content:
        print("  = explain.py already saves scores")
        return True
    
    # Add import at top
    old_import = "from nomad.edu.scoring import score_job"
    new_import = """from nomad.edu.scoring import score_job
from nomad.edu.storage import save_proficiency_score"""
    
    if old_import in content:
        content = content.replace(old_import, new_import, 1)
    else:
        # Try alternative
        old_import2 = "from .scoring import score_job"
        new_import2 = """from .scoring import score_job
from .storage import save_proficiency_score"""
        if old_import2 in content:
            content = content.replace(old_import2, new_import2, 1)
        else:
            print("  ! Could not find import location in explain.py")
            return False
    
    # Find where fingerprint is computed and add save call
    # Look for the pattern after score_job is called
    old_pattern = "fp = score_job(job, summary)"
    new_pattern = """fp = score_job(job, summary)
    
    # Save to database for historical tracking
    save_proficiency_score(db_path, fp)"""
    
    if old_pattern in content and 'save_proficiency_score(db_path' not in content:
        content = content.replace(old_pattern, new_pattern, 1)
        print("  + Added save_proficiency_score call to explain.py")
    else:
        print("  = explain.py score saving already present or pattern not found")
    
    path.write_text(content)
    return True


def patch_demo(nomad_dir: Path) -> bool:
    """Add proficiency_scores table to demo.py schema."""
    path = nomad_dir / 'demo.py'
    content = path.read_text()
    
    if 'proficiency_scores' in content:
        print("  = demo.py already has proficiency_scores table")
        return True
    
    # Find where group_membership is created and add proficiency_scores after
    marker = '# Group membership for edu module'
    
    addition = '''# Proficiency scores for edu tracking
        c.execute("""CREATE TABLE IF NOT EXISTS proficiency_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            job_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            cluster TEXT DEFAULT 'default',
            cpu_score REAL, cpu_level TEXT,
            memory_score REAL, memory_level TEXT,
            time_score REAL, time_level TEXT,
            io_score REAL, io_level TEXT,
            gpu_score REAL, gpu_level TEXT, gpu_applicable INTEGER,
            overall_score REAL, overall_level TEXT,
            needs_work TEXT, strengths TEXT,
            UNIQUE(job_id))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_prof_user ON proficiency_scores(user_name)")
        '''
    
    if marker in content:
        content = content.replace(marker, addition + '\n        ' + marker, 1)
        path.write_text(content)
        print("  + Added proficiency_scores table to demo.py")
        return True
    else:
        print("  ! Could not find marker in demo.py")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 patch_edu_storage.py /path/to/nomad/")
        sys.exit(1)
    
    nomad_dir = Path(sys.argv[1])
    if not nomad_dir.exists():
        print(f"ERROR: {nomad_dir} not found")
        sys.exit(1)
    
    # First, copy storage.py to edu/
    storage_src = Path(__file__).parent / 'edu_storage.py'
    storage_dst = nomad_dir / 'edu' / 'storage.py'
    
    print("\nIntegrating Edu Storage")
    print("=" * 30)
    
    if storage_src.exists():
        shutil.copy(storage_src, storage_dst)
        print(f"  + Copied storage.py to {storage_dst}")
    else:
        print(f"  ! Source file not found: {storage_src}")
        print("    Copy edu_storage.py to nomad/edu/storage.py manually")
    
    patch_edu_init(nomad_dir)
    patch_explain(nomad_dir)
    patch_demo(nomad_dir)
    
    print("\nDone! Proficiency scores will now be saved to the database.")
    print("Test with: nomad edu explain <job_id>")


if __name__ == '__main__':
    main()
