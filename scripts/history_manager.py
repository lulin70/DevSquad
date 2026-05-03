#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad History Manager

Historical data storage and retrieval using SQLite.

Features:
  - Metrics snapshots storage
  - Alert history tracking
  - API request logging
  - Time-series queries
  - Automatic data retention/cleanup

Usage:
    from scripts.history_manager import HistoryManager
    
    history = HistoryManager()
    
    # Store metrics snapshot
    history.save_metrics_snapshot({
        "completion_rate": 75.5,
        "avg_response_time_ms": 150.2,
        "cpu_usage": 45.3
    })
    
    # Query historical data
    data = history.get_metrics_history(hours=24)
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    SQLite-based history manager for DevSquad.
    
    Stores and retrieves time-series data including:
    - Performance metrics snapshots
    - Alert history
    - API request logs
    - Lifecycle state changes
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize HistoryManager.
        
        Args:
            db_path: Path to SQLite database file.
                   Defaults to data/devsquad_history.db
        """
        if db_path is None:
            # Default path in project's data directory
            data_dir = Path(__file__).parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "devsquad_history.db")
        
        self.db_path = db_path
        self.conn = self._get_connection()
        
        # Initialize database schema
        self._init_schema()
        
        logger.info(f"HistoryManager initialized (db={db_path})")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def _init_schema(self):
        """Initialize database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Metrics snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                total_phases INTEGER,
                completed_phases INTEGER,
                running_phases INTEGER,
                failed_phases INTEGER,
                completion_rate REAL,
                avg_response_time_ms REAL,
                p95_latency_ms REAL,
                success_rate REAL,
                cpu_usage_percent REAL,
                memory_usage_percent REAL,
                custom_data TEXT,  -- JSON blob for additional data
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Alert history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id VARCHAR(12) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                source VARCHAR(100),
                channel VARCHAR(20),
                acknowledged BOOLEAN DEFAULT 0,
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alert_id)
            )
        """)
        
        # API logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                method VARCHAR(10) NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms REAL,
                client_ip VARCHAR(45),
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Lifecycle events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                event_type VARCHAR(50) NOT NULL,
                phase_id VARCHAR(10),
                previous_status VARCHAR(20),
                new_status VARCHAR(20),
                user_id VARCHAR(100),
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better query performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics_snapshots(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alert_history(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alert_history(severity)",
            "CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp ON api_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_api_logs_path ON api_logs(path)",
            "CREATE INDEX IF NOT EXISTS idx_lifecycle_events_timestamp ON lifecycle_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_lifecycle_events_phase ON lifecycle_events(phase_id)"
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
        
        self.conn.commit()
        logger.debug("Database schema initialized/verified")
    
    def save_metrics_snapshot(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Save a metrics snapshot to the database.
        
        Args:
            metrics_data: Dictionary containing metric values
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Extract known fields
            custom_data = {
                k: v for k, v in metrics_data.items()
                if k not in [
                    'total_phases', 'completed_phases', 'running_phases',
                    'failed_phases', 'completion_rate', 'avg_response_time_ms',
                    'p95_latency_ms', 'success_rate', 'cpu_usage_percent',
                    'memory_usage_percent'
                ]
            }
            
            cursor.execute("""
                INSERT INTO metrics_snapshots (
                    timestamp, total_phases, completed_phases, running_phases,
                    failed_phases, completion_rate, avg_response_time_ms,
                    p95_latency_ms, success_rate, cpu_usage_percent,
                    memory_usage_percent, custom_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(),
                metrics_data.get('total_phases'),
                metrics_data.get('completed_phases'),
                metrics_data.get('running_phases'),
                metrics_data.get('failed_phases'),
                metrics_data.get('completion_rate'),
                metrics_data.get('avg_response_time_ms'),
                metrics_data.get('p95_latency_ms'),
                metrics_data.get('success_rate'),
                metrics_data.get('cpu_usage_percent'),
                metrics_data.get('memory_usage_percent'),
                json.dumps(custom_data) if custom_data else None
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to save metrics snapshot: {e}")
            return False
    
    def get_metrics_history(
        self,
        hours: int = 24,
        interval_minutes: int = 60,
        include_custom: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve metrics history.
        
        Args:
            hours: Number of hours to look back
            interval_minutes: Interval between data points
            include_custom: Whether to include custom data field
            
        Returns:
            List of metric snapshot dictionaries
        """
        try:
            cursor = self.conn.cursor()
            
            cutoff = datetime.now() - timedelta(hours=hours)
            
            # Query with sampling based on interval
            cursor.execute("""
                SELECT * FROM metrics_snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (cutoff,))
            
            rows = cursor.fetchall()
            
            # Sample data based on interval if too many points
            if len(rows) > 500:
                sample_every = max(1, len(rows) // 500)
                rows = rows[::sample_every]
            
            results = []
            for row in rows:
                data = dict(row)
                
                # Parse custom data if requested
                if include_custom and data.get('custom_data'):
                    try:
                        data['custom_data'] = json.loads(data['custom_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Convert timestamp to string for JSON serialization
                if isinstance(data.get('timestamp'), datetime):
                    data['timestamp'] = data['timestamp'].isoformat()
                
                results.append(data)
            
            logger.debug(f"Retrieved {len(results)} metrics snapshots")
            return results
            
        except Exception as e:
            logger.error(f"Failed to get metrics history: {e}")
            return []
    
    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Log an API request to the database.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            client_ip: Client IP address
            user_agent: User agent string
            
        Returns:
            True if logged successfully
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO api_logs (
                    method, path, status_code, response_time_ms,
                    client_ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (method, path, status_code, response_time_ms, client_ip, user_agent))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to log API request: {e}")
            return False
    
    def get_api_stats(
        self,
        hours: int = 1,
        group_by_path: bool = True
    ) -> Dict[str, Any]:
        """
        Get API request statistics.
        
        Args:
            hours: Statistics period in hours
            group_by_path: Whether to group by endpoint path
            
        Returns:
            Dictionary with API statistics
        """
        try:
            cursor = self.conn.cursor()
            cutoff = datetime.now() - timedelta(hours=hours)
            
            # Total requests
            cursor.execute("""
                SELECT COUNT(*) as total,
                       AVG(response_time_ms) as avg_response,
                       MAX(response_time_ms) as max_response,
                       MIN(response_time_ms) as min_response
                FROM api_logs
                WHERE timestamp >= ?
            """, (cutoff,))
            
            row = cursor.fetchone()
            stats = {
                "total_requests": row['total'] or 0,
                "avg_response_time_ms": round(row['avg_response'], 2) if row['avg_response'] else 0,
                "max_response_time_ms": round(row['max_response'], 2) if row['max_response'] else 0,
                "min_response_time_ms": round(row['min_response'], 2) if row['min_response'] else 0,
                "period_hours": hours
            }
            
            # Status code distribution
            cursor.execute("""
                SELECT status_code, COUNT(*) as count
                FROM api_logs
                WHERE timestamp >= ?
                GROUP BY status_code
                ORDER BY count DESC
            """, (cutoff,))
            
            stats["status_codes"] = [
                {"status_code": row['status_code'], "count": row['count']}
                for row in cursor.fetchall()
            ]
            
            # By endpoint (if requested)
            if group_by_path:
                cursor.execute("""
                    SELECT path, COUNT(*) as count,
                           AVG(response_time_ms) as avg_response
                    FROM api_logs
                    WHERE timestamp >= ?
                    GROUP BY path
                    ORDER BY count DESC
                    LIMIT 20
                """, (cutoff,))
                
                stats["endpoints"] = [
                    {
                        "path": row['path'],
                        "requests": row['count'],
                        "avg_response_ms": round(row['avg_response'], 2) if row['avg_response'] else 0
                    }
                    for row in cursor.fetchall()
                ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get API stats: {e}")
            return {}
    
    def save_lifecycle_event(
        self,
        event_type: str,
        phase_id: Optional[str] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """
        Save a lifecycle state change event.
        
        Args:
            event_type: Type of event (phase_advance, phase_complete, etc.)
            phase_id: Phase identifier
            previous_status: Status before change
            new_status: Status after change
            user_id: User who triggered the event
            details: Additional details
            
        Returns:
            True if saved successfully
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO lifecycle_events (
                    event_type, phase_id, previous_status,
                    new_status, user_id, details
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (event_type, phase_id, previous_status, new_status, user_id, details))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to save lifecycle event: {e}")
            return False
    
    def get_lifecycle_history(
        self,
        hours: int = 24,
        phase_id: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get lifecycle event history.
        
        Args:
            hours: Look back period
            phase_id: Filter by specific phase
            event_type: Filter by event type
            
        Returns:
            List of lifecycle event dictionaries
        """
        try:
            cursor = self.conn.cursor()
            cutoff = datetime.now() - timedelta(hours=hours)
            
            query = """
                SELECT * FROM lifecycle_events
                WHERE timestamp >= ?
            """
            params = [cutoff]
            
            if phase_id:
                query += " AND phase_id = ?"
                params.append(phase_id)
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            query += " ORDER BY timestamp DESC LIMIT 200"
            
            cursor.execute(query, params)
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get lifecycle history: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int = 30) -> Dict[str, int]:
        """
        Remove old data beyond retention period.
        
        Args:
            retention_days: Number of days to keep data
            
        Returns:
            Dictionary with counts of deleted records per table
        """
        try:
            cursor = self.conn.cursor()
            cutoff = datetime.now() - timedelta(days=retention_days)
            
            deleted = {}
            
            tables = ['metrics_snapshots', 'alert_history', 'api_logs', 'lifecycle_events']
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
                deleted[table] = cursor.rowcount
            
            self.conn.commit()
            
            total_deleted = sum(deleted.values())
            logger.info(f"Cleaned up {total_deleted} old records (retention={retention_days} days)")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {}
    
    def get_database_size(self) -> Dict[str, Any]:
        """
        Get database size information.
        
        Returns:
            Dictionary with size statistics
        """
        try:
            cursor = self.conn.cursor()
            
            # Table sizes
            table_sizes = {}
            tables = ['metrics_snapshots', 'alert_history', 'api_logs', 'lifecycle_events']
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                table_sizes[table] = cursor.fetchone()['count']
            
            # File size
            db_file = Path(self.db_path)
            file_size_mb = db_file.stat().st_size / (1024 * 1024) if db_file.exists() else 0
            
            return {
                "file_path": self.db_path,
                "file_size_mb": round(file_size_mb, 2),
                "tables": table_sizes,
                "total_records": sum(table_sizes.values())
            }
            
        except Exception as e:
            logger.error(f"Failed to get database size: {e}")
            return {}
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    # Demo: Test history manager
    print("\n📊 DevSquad History Manager Demo\n")
    print("=" * 50)
    
    history = HistoryManager()
    
    # Save some test data
    test_metrics = {
        "total_phases": 11,
        "completed_phases": 7,
        "running_phases": 1,
        "failed_phases": 0,
        "completion_rate": 63.6,
        "avg_response_time_ms": 150.5,
        "cpu_usage_percent": 45.2,
        "memory_usage_percent": 62.8,
        "custom_field": "test_value"
    }
    
    print("\nSaving test metrics snapshot...")
    history.save_metrics_snapshot(test_metrics)
    print("✅ Metrics saved!")
    
    # Log an API request
    print("\nLogging test API request...")
    history.log_api_request("GET", "/api/v1/lifecycle/phases", 200, 45.2)
    print("✅ API request logged!")
    
    # Query data back
    print("\nQuerying metrics history...")
    data = history.get_metrics_history(hours=1)
    print(f"✅ Retrieved {len(data)} snapshots")
    
    # Show database info
    print("\n📈 Database Info:")
    db_info = history.get_database_size()
    for key, value in db_info.items():
        print(f"  {key}: {value}")
    
    history.close()
    print("\n✅ Demo completed!")
