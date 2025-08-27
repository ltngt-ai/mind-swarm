"""
Session persistence and storage management.

This module provides session persistence using SQLite database
for storing session metadata and state across system restarts.
"""

import sqlite3
import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .session import TerminalSession, SessionStatus, SessionInfo
from .exceptions import CyberTerminalError


logger = logging.getLogger(__name__)


class SessionStore:
    """Manages session persistence using SQLite database."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to user's home directory
            home_dir = os.path.expanduser('~')
            cyber_dir = os.path.join(home_dir, '.cyber_terminal')
            os.makedirs(cyber_dir, exist_ok=True)
            db_path = os.path.join(cyber_dir, 'sessions.db')
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        command TEXT NOT NULL,
                        process_id INTEGER,
                        status TEXT NOT NULL,
                        working_directory TEXT,
                        environment TEXT,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        terminal_rows INTEGER NOT NULL,
                        terminal_cols INTEGER NOT NULL,
                        pty_master INTEGER,
                        pty_slave INTEGER,
                        exit_code INTEGER,
                        error_message TEXT,
                        metadata TEXT
                    )
                ''')
                
                # Create indexes for better performance
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sessions_status 
                    ON sessions(status)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sessions_created_at 
                    ON sessions(created_at)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_sessions_process_id 
                    ON sessions(process_id)
                ''')
                
                conn.commit()
                
            logger.info(f"Initialized session database at {self.db_path}")
            
        except sqlite3.Error as e:
            raise CyberTerminalError(f"Failed to initialize session database: {e}")
    
    def save_session(self, session: TerminalSession) -> bool:
        """
        Save session to database.
        
        Args:
            session: Terminal session to save
            
        Returns:
            True if save successful
            
        Raises:
            CyberTerminalError: If database operation fails
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO sessions 
                    (session_id, name, command, process_id, status, working_directory, 
                     environment, created_at, last_activity, terminal_rows, terminal_cols,
                     pty_master, pty_slave, exit_code, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session.session_id,
                    session.name,
                    session.command,
                    session.process_id,
                    session.status.value,
                    session.working_directory,
                    json.dumps(session.environment),
                    session.created_at.isoformat(),
                    session.last_activity.isoformat(),
                    session.terminal_size[0],
                    session.terminal_size[1],
                    session.pty_master,
                    session.pty_slave,
                    session.exit_code,
                    session.error_message,
                    json.dumps(session.metadata)
                ))
                
                conn.commit()
                
            logger.debug(f"Saved session {session.session_id} to database")
            return True
            
        except (sqlite3.Error, json.JSONEncodeError) as e:
            raise CyberTerminalError(f"Failed to save session {session.session_id}: {e}")
    
    def load_session(self, session_id: str) -> Optional[TerminalSession]:
        """
        Load session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Terminal session or None if not found
            
        Raises:
            CyberTerminalError: If database operation fails
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM sessions WHERE session_id = ?
                ''', (session_id,))
                
                row = cursor.fetchone()
                if row is None:
                    return None
                
                return self._row_to_session(row)
                
        except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
            raise CyberTerminalError(f"Failed to load session {session_id}: {e}")
    
    def load_all_sessions(self) -> List[TerminalSession]:
        """
        Load all sessions from database.
        
        Returns:
            List of terminal sessions
            
        Raises:
            CyberTerminalError: If database operation fails
        """
        try:
            sessions = []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM sessions ORDER BY created_at DESC
                ''')
                
                for row in cursor.fetchall():
                    try:
                        session = self._row_to_session(row)
                        sessions.append(session)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse session row: {e}")
                        continue
            
            logger.info(f"Loaded {len(sessions)} sessions from database")
            return sessions
            
        except sqlite3.Error as e:
            raise CyberTerminalError(f"Failed to load sessions: {e}")
    
    def load_active_sessions(self) -> List[TerminalSession]:
        """
        Load only active (non-terminated) sessions.
        
        Returns:
            List of active terminal sessions
        """
        try:
            sessions = []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM sessions 
                    WHERE status != ? 
                    ORDER BY last_activity DESC
                ''', (SessionStatus.TERMINATED.value,))
                
                for row in cursor.fetchall():
                    try:
                        session = self._row_to_session(row)
                        
                        # Verify process is still alive
                        if session.process_id > 0 and self._is_process_alive(session.process_id):
                            sessions.append(session)
                        else:
                            # Mark as terminated if process died
                            session.status = SessionStatus.TERMINATED
                            self.save_session(session)
                    
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse session row: {e}")
                        continue
            
            logger.info(f"Loaded {len(sessions)} active sessions from database")
            return sessions
            
        except sqlite3.Error as e:
            raise CyberTerminalError(f"Failed to load active sessions: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deletion successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM sessions WHERE session_id = ?
                ''', (session_id,))
                
                conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted session {session_id} from database")
                
                return deleted
                
        except sqlite3.Error as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def cleanup_terminated_sessions(self, older_than_hours: int = 24) -> int:
        """
        Clean up old terminated sessions.
        
        Args:
            older_than_hours: Remove sessions terminated more than this many hours ago
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
            cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM sessions 
                    WHERE status = ? AND last_activity < ?
                ''', (SessionStatus.TERMINATED.value, cutoff_iso))
                
                conn.commit()
                
                cleaned_count = cursor.rowcount
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old terminated sessions")
                
                return cleaned_count
                
        except sqlite3.Error as e:
            logger.error(f"Failed to cleanup terminated sessions: {e}")
            return 0
    
    def get_session_count(self) -> Dict[str, int]:
        """
        Get count of sessions by status.
        
        Returns:
            Dictionary with status counts
        """
        try:
            counts = {}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT status, COUNT(*) FROM sessions GROUP BY status
                ''')
                
                for status, count in cursor.fetchall():
                    counts[status] = count
            
            return counts
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get session counts: {e}")
            return {}
    
    def search_sessions(self, query: str, limit: int = 50) -> List[TerminalSession]:
        """
        Search sessions by name or command.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching sessions
        """
        try:
            sessions = []
            search_pattern = f'%{query}%'
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM sessions 
                    WHERE name LIKE ? OR command LIKE ?
                    ORDER BY last_activity DESC
                    LIMIT ?
                ''', (search_pattern, search_pattern, limit))
                
                for row in cursor.fetchall():
                    try:
                        session = self._row_to_session(row)
                        sessions.append(session)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse session row: {e}")
                        continue
            
            return sessions
            
        except sqlite3.Error as e:
            logger.error(f"Failed to search sessions: {e}")
            return []
    
    def _row_to_session(self, row) -> TerminalSession:
        """Convert database row to TerminalSession object."""
        (session_id, name, command, process_id, status, working_directory,
         environment_json, created_at_str, last_activity_str, terminal_rows,
         terminal_cols, pty_master, pty_slave, exit_code, error_message,
         metadata_json) = row
        
        # Parse JSON fields
        environment = json.loads(environment_json) if environment_json else {}
        metadata = json.loads(metadata_json) if metadata_json else {}
        
        # Parse datetime fields
        created_at = datetime.fromisoformat(created_at_str)
        last_activity = datetime.fromisoformat(last_activity_str)
        
        return TerminalSession(
            session_id=session_id,
            name=name,
            command=command,
            process_id=process_id or 0,
            status=SessionStatus(status),
            working_directory=working_directory or "/tmp",
            environment=environment,
            created_at=created_at,
            last_activity=last_activity,
            terminal_size=(terminal_rows, terminal_cols),
            pty_master=pty_master or -1,
            pty_slave=pty_slave or -1,
            exit_code=exit_code,
            error_message=error_message,
            metadata=metadata
        )
    
    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still running."""
        try:
            import os
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            info = {
                'database_path': self.db_path,
                'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                'session_counts': self.get_session_count()
            }
            
            with sqlite3.connect(self.db_path) as conn:
                # Get database version
                cursor = conn.execute('PRAGMA user_version')
                info['database_version'] = cursor.fetchone()[0]
                
                # Get table info
                cursor = conn.execute('PRAGMA table_info(sessions)')
                info['table_columns'] = [row[1] for row in cursor.fetchall()]
            
            return info
            
        except (sqlite3.Error, OSError) as e:
            logger.error(f"Failed to get database info: {e}")
            return {'error': str(e)}
    
    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the session database.
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            True if backup successful
        """
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Created database backup at {backup_path}")
            return True
            
        except (OSError, shutil.Error) as e:
            logger.error(f"Failed to create database backup: {e}")
            return False
    
    def restore_database(self, backup_path: str) -> bool:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restore successful
        """
        try:
            import shutil
            
            # Verify backup file exists and is valid
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Test backup file by opening it
            with sqlite3.connect(backup_path) as conn:
                conn.execute('SELECT COUNT(*) FROM sessions')
            
            # Create backup of current database
            current_backup = f"{self.db_path}.pre_restore"
            shutil.copy2(self.db_path, current_backup)
            
            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"Restored database from {backup_path}")
            logger.info(f"Previous database backed up to {current_backup}")
            
            return True
            
        except (OSError, sqlite3.Error, shutil.Error) as e:
            logger.error(f"Failed to restore database: {e}")
            return False

