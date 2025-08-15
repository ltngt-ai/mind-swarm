"""File operation utilities for the cognitive loop.

This module provides safe file operations and path management
utilities used throughout the cognitive system.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List, Union, Dict
import logging

logger = logging.getLogger("Cyber.utils.file")


class FileManager:
    """Manages file operations with safety checks and error handling."""
    
    @staticmethod
    def ensure_directory(dir_path: Union[str, Path]) -> bool:
        """Ensure a directory exists, creating it if necessary.
        
        Args:
            dir_path: Path to directory
            
        Returns:
            True if directory exists or was created successfully
        """
        try:
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure directory {dir_path}: {e}")
            return False
    
    @staticmethod
    def load_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> Optional[str]:
        """Load file contents safely.
        
        Args:
            file_path: Path to file
            encoding: File encoding (default: utf-8)
            
        Returns:
            File contents or None if error
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.debug(f"File not found: {file_path}")
                return None
            return path.read_text(encoding=encoding)
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return None
    
    @staticmethod
    def save_file(file_path: Union[str, Path], content: str, 
                  encoding: str = 'utf-8', atomic: bool = True) -> bool:
        """Save content to file safely.
        
        Args:
            file_path: Path to file
            content: Content to save
            encoding: File encoding (default: utf-8)
            atomic: Use atomic write with temp file (default: True)
            
        Returns:
            True if saved successfully
        """
        try:
            path = Path(file_path)
            
            # Ensure parent directory exists
            FileManager.ensure_directory(path.parent)
            
            if atomic:
                # Write to temp file first
                temp_path = path.with_suffix(path.suffix + '.tmp')
                temp_path.write_text(content, encoding=encoding)
                # Atomic rename
                temp_path.replace(path)
            else:
                path.write_text(content, encoding=encoding)
                
            return True
        except Exception as e:
            logger.error(f"Failed to save file {file_path}: {e}")
            return False
    
    @staticmethod
    def list_directory(dir_path: Union[str, Path], 
                      pattern: Optional[str] = None,
                      recursive: bool = False) -> List[Path]:
        """List files in directory with optional pattern matching.
        
        Args:
            dir_path: Path to directory
            pattern: Glob pattern (e.g., "*.json")
            recursive: Search recursively
            
        Returns:
            List of file paths
        """
        try:
            path = Path(dir_path)
            if not path.exists() or not path.is_dir():
                return []
                
            if pattern:
                if recursive:
                    return list(path.rglob(pattern))
                else:
                    return list(path.glob(pattern))
            else:
                if recursive:
                    return [p for p in path.rglob("*") if p.is_file()]
                else:
                    return [p for p in path.iterdir() if p.is_file()]
        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return []
    
    @staticmethod
    def move_file(src_path: Union[str, Path], 
                  dst_path: Union[str, Path],
                  create_dst_dir: bool = True) -> bool:
        """Move file from source to destination.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            create_dst_dir: Create destination directory if needed
            
        Returns:
            True if moved successfully
        """
        try:
            src = Path(src_path)
            dst = Path(dst_path)
            
            if not src.exists():
                logger.error(f"Source file not found: {src_path}")
                return False
                
            if create_dst_dir:
                FileManager.ensure_directory(dst.parent)
                
            shutil.move(str(src), str(dst))
            return True
        except Exception as e:
            logger.error(f"Failed to move file from {src_path} to {dst_path}: {e}")
            return False
    
    @staticmethod
    def copy_file(src_path: Union[str, Path], 
                  dst_path: Union[str, Path],
                  create_dst_dir: bool = True) -> bool:
        """Copy file from source to destination.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            create_dst_dir: Create destination directory if needed
            
        Returns:
            True if copied successfully
        """
        try:
            src = Path(src_path)
            dst = Path(dst_path)
            
            if not src.exists():
                logger.error(f"Source file not found: {src_path}")
                return False
                
            if create_dst_dir:
                FileManager.ensure_directory(dst.parent)
                
            shutil.copy2(str(src), str(dst))
            return True
        except Exception as e:
            logger.error(f"Failed to copy file from {src_path} to {dst_path}: {e}")
            return False
    
    @staticmethod
    def delete_file(file_path: Union[str, Path], safe: bool = True) -> bool:
        """Delete file safely.
        
        Args:
            file_path: Path to file
            safe: Only delete if it's a file (not directory)
            
        Returns:
            True if deleted successfully or didn't exist
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return True
                
            if safe and not path.is_file():
                logger.error(f"Refusing to delete non-file: {file_path}")
                return False
                
            path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    @staticmethod
    def get_file_info(file_path: Union[str, Path]) -> Optional[Dict]:
        """Get file information.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dict with file info or None if error
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            stat = path.stat()
            return {
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "exists": True
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return None