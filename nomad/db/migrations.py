# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""Database migration system for NOMAD."""

import logging
import sqlite3
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Migration scripts: (version, description, SQL)
MIGRATIONS: List[Tuple[int, str, str]] = [
    (1, "Initial schema", Path(__file__).parent.joinpath("schema.sql").read_text()),
    (2, "Add alert_history table", """
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
            message TEXT NOT NULL,
            metric_name TEXT,
            metric_value REAL,
            threshold_value REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_by TEXT,
            acknowledged_at DATETIME
        );
        CREATE INDEX idx_alert_history_timestamp ON alert_history(timestamp);
        CREATE INDEX idx_alert_history_severity ON alert_history(severity);
    """),
    (3, "Add collector_runs table", """
        CREATE TABLE IF NOT EXISTS collector_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector_name TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            status TEXT CHECK (status IN ('running', 'success', 'failed')),
            records_collected INTEGER DEFAULT 0,
            error_message TEXT,
            UNIQUE(collector_name, start_time)
        );
        CREATE INDEX idx_collector_runs_name ON collector_runs(collector_name);
    """),
]


class MigrationManager:
    """Manages database schema migrations."""
    
    def __init__(self, db_path: Path):
        """Initialize migration manager."""
        self.db_path = db_path
        self.conn = None
        
    def __enter__(self):
        """Context manager entry."""
        self.conn = sqlite3.connect(self.db_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.conn:
            self.conn.close()
            
    def get_current_version(self) -> int:
        """Get current database schema version."""
        cursor = self.conn.cursor()
        
        # Create migration tracking table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get the highest applied version
        cursor.execute("SELECT MAX(version) FROM schema_migrations")
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0
        
    def apply_migration(self, version: int, description: str, sql: str) -> None:
        """Apply a single migration."""
        logger.info(f"Applying migration {version}: {description}")
        
        cursor = self.conn.cursor()
        try:
            # Execute the migration SQL
            cursor.executescript(sql)
            
            # Record the migration
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (version, description)
            )
            
            self.conn.commit()
            logger.info(f"Migration {version} applied successfully")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Migration {version} failed: {e}")
            raise
            
    def migrate(self) -> int:
        """Run all pending migrations."""
        current_version = self.get_current_version()
        applied_count = 0
        
        for version, description, sql in MIGRATIONS:
            if version > current_version:
                self.apply_migration(version, description, sql)
                applied_count += 1
                
        if applied_count == 0:
            logger.info(f"Database is up to date (version {current_version})")
        else:
            new_version = self.get_current_version()
            logger.info(f"Applied {applied_count} migrations (now at version {new_version})")
            
        return applied_count
        
    def reset(self) -> None:
        """Reset database to fresh state (WARNING: destroys all data)."""
        logger.warning("Resetting database - all data will be lost!")
        
        cursor = self.conn.cursor()
        
        # Get all table names
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = cursor.fetchall()
        
        # Drop all tables
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
            
        self.conn.commit()
        logger.info("Database reset complete")
        
        # Re-run all migrations
        self.migrate()


def ensure_database(db_path: Path) -> None:
    """Ensure database exists and is up to date."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    with MigrationManager(db_path) as mgr:
        mgr.migrate()