"""Freeze/unfreeze handler for backing up and restoring Cybers.

This module provides functionality to freeze (backup) Cybers to tar.gz archives
and unfreeze (restore) them to a subspace, preserving their personal space and state.
"""

import tarfile
import json
import asyncio
import io
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import tempfile
import shutil

from mind_swarm.utils.logging import logger


class FreezeHandler:
    """Handles freezing and unfreezing of Cybers."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the freeze handler.
        
        Args:
            subspace_root: Root path of the subspace
        """
        self.subspace_root = subspace_root
        self.cybers_dir = subspace_root / "cybers"
        self.freeze_dir = subspace_root / "frozen"
        
        # Ensure freeze directory exists
        self.freeze_dir.mkdir(exist_ok=True)
        
        logger.info(f"Initialized freeze handler with freeze dir: {self.freeze_dir}")
    
    async def freeze_cyber(self, cyber_name: str, output_path: Optional[Path] = None) -> Path:
        """Freeze a single Cyber to a tar.gz archive.
        
        Args:
            cyber_name: Name of the Cyber to freeze
            output_path: Optional custom output path for the archive
            
        Returns:
            Path to the created archive
            
        Raises:
            FileNotFoundError: If the Cyber doesn't exist
            IOError: If archive creation fails
        """
        cyber_dir = self.cybers_dir / cyber_name
        
        if not cyber_dir.exists():
            raise FileNotFoundError(f"Cyber '{cyber_name}' not found at {cyber_dir}")
        
        # Default output path if not specified
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.freeze_dir / f"{cyber_name}_{timestamp}.tar.gz"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create metadata about the freeze
            metadata = {
                "cyber_name": cyber_name,
                "frozen_at": datetime.now().isoformat(),
                "subspace_root": str(self.subspace_root),
                "version": "1.0"
            }
            
            # Create tar.gz archive
            with tarfile.open(output_path, "w:gz") as tar:
                # Add metadata file
                metadata_bytes = json.dumps(metadata, indent=2).encode()
                metadata_info = tarfile.TarInfo(name="freeze_metadata.json")
                metadata_info.size = len(metadata_bytes)
                
                # Create a proper file object for the metadata
                import io
                metadata_file = io.BytesIO(metadata_bytes)
                tar.addfile(metadata_info, fileobj=metadata_file)
                
                # Add the entire Cyber directory
                tar.add(cyber_dir, arcname=cyber_name)
            
            logger.info(f"Froze Cyber '{cyber_name}' to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to freeze Cyber '{cyber_name}': {e}")
            if output_path.exists():
                output_path.unlink()
            raise IOError(f"Failed to freeze Cyber: {e}")
    
    async def freeze_all(self, output_path: Optional[Path] = None) -> Path:
        """Freeze all Cybers to a single tar.gz archive.
        
        Args:
            output_path: Optional custom output path for the archive
            
        Returns:
            Path to the created archive
        """
        # Get all Cyber directories
        cyber_names = []
        if self.cybers_dir.exists():
            cyber_names = [d.name for d in self.cybers_dir.iterdir() if d.is_dir()]
        
        if not cyber_names:
            logger.warning("No Cybers found to freeze")
            return None
        
        # Default output path if not specified
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.freeze_dir / f"all_cybers_{timestamp}.tar.gz"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create metadata about the freeze
            metadata = {
                "cyber_names": cyber_names,
                "frozen_at": datetime.now().isoformat(),
                "subspace_root": str(self.subspace_root),
                "version": "1.0",
                "type": "all_cybers"
            }
            
            # Create tar.gz archive
            with tarfile.open(output_path, "w:gz") as tar:
                # Add metadata file
                metadata_bytes = json.dumps(metadata, indent=2).encode()
                metadata_info = tarfile.TarInfo(name="freeze_metadata.json")
                metadata_info.size = len(metadata_bytes)
                
                # Create a proper file object for the metadata
                import io
                metadata_file = io.BytesIO(metadata_bytes)
                tar.addfile(metadata_info, fileobj=metadata_file)
                
                # Add all Cyber directories
                for cyber_name in cyber_names:
                    cyber_dir = self.cybers_dir / cyber_name
                    if cyber_dir.exists():
                        tar.add(cyber_dir, arcname=f"cybers/{cyber_name}")
                        logger.debug(f"Added {cyber_name} to archive")
            
            logger.info(f"Froze {len(cyber_names)} Cybers to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to freeze all Cybers: {e}")
            if output_path.exists():
                output_path.unlink()
            raise IOError(f"Failed to freeze all Cybers: {e}")
    
    async def unfreeze_cyber(self, archive_path: Path, force: bool = False) -> List[str]:
        """Unfreeze Cyber(s) from a tar.gz archive.
        
        Args:
            archive_path: Path to the archive file
            force: If True, overwrite existing Cybers
            
        Returns:
            List of unfrozen Cyber names
            
        Raises:
            FileNotFoundError: If archive doesn't exist
            IOError: If extraction fails
        """
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        unfrozen_cybers = []
        
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                # First, read metadata
                metadata = None
                try:
                    metadata_member = tar.getmember("freeze_metadata.json")
                    metadata_file = tar.extractfile(metadata_member)
                    if metadata_file:
                        metadata = json.loads(metadata_file.read().decode())
                        logger.debug(f"Freeze metadata: {metadata}")
                except KeyError:
                    logger.warning("No metadata found in archive")
                
                # Determine if this is a single Cyber or multiple
                is_multi = metadata and metadata.get("type") == "all_cybers"
                
                # Extract to temporary directory first
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Extract all files
                    tar.extractall(temp_path)
                    
                    # Process extracted files
                    if is_multi:
                        # Multiple Cybers
                        cybers_temp_dir = temp_path / "cybers"
                        if cybers_temp_dir.exists():
                            for cyber_dir in cybers_temp_dir.iterdir():
                                if cyber_dir.is_dir():
                                    await self._restore_cyber_dir(cyber_dir, cyber_dir.name, force)
                                    unfrozen_cybers.append(cyber_dir.name)
                    else:
                        # Single Cyber
                        for item in temp_path.iterdir():
                            if item.is_dir() and item.name != "freeze_metadata.json":
                                cyber_name = item.name
                                await self._restore_cyber_dir(item, cyber_name, force)
                                unfrozen_cybers.append(cyber_name)
                                break
            
            logger.info(f"Unfroze {len(unfrozen_cybers)} Cybers from {archive_path}")
            return unfrozen_cybers
            
        except Exception as e:
            logger.error(f"Failed to unfreeze from {archive_path}: {e}")
            raise IOError(f"Failed to unfreeze: {e}")
    
    async def _restore_cyber_dir(self, source_dir: Path, cyber_name: str, force: bool = False):
        """Restore a Cyber directory from extracted archive.
        
        Args:
            source_dir: Source directory containing Cyber data
            cyber_name: Name of the Cyber
            force: If True, overwrite existing Cyber
        """
        target_dir = self.cybers_dir / cyber_name
        
        # Check if Cyber already exists
        if target_dir.exists() and not force:
            logger.warning(f"Cyber '{cyber_name}' already exists, skipping (use force=True to overwrite)")
            return
        
        # Remove existing if force is True
        if target_dir.exists() and force:
            logger.info(f"Removing existing Cyber '{cyber_name}' (force=True)")
            shutil.rmtree(target_dir)
        
        # Copy the Cyber directory
        shutil.copytree(source_dir, target_dir)
        logger.info(f"Restored Cyber '{cyber_name}' to {target_dir}")
    
    async def list_frozen(self) -> List[Dict[str, Any]]:
        """List all frozen archives.
        
        Returns:
            List of frozen archive information
        """
        frozen_list = []
        
        if not self.freeze_dir.exists():
            return frozen_list
        
        for archive_path in self.freeze_dir.glob("*.tar.gz"):
            try:
                # Try to read metadata from archive
                with tarfile.open(archive_path, "r:gz") as tar:
                    metadata = None
                    try:
                        metadata_member = tar.getmember("freeze_metadata.json")
                        metadata_file = tar.extractfile(metadata_member)
                        if metadata_file:
                            metadata = json.loads(metadata_file.read().decode())
                    except KeyError:
                        pass
                    
                    frozen_info = {
                        "filename": archive_path.name,
                        "path": str(archive_path),
                        "size": archive_path.stat().st_size,
                        "modified": datetime.fromtimestamp(archive_path.stat().st_mtime).isoformat(),
                        "metadata": metadata
                    }
                    frozen_list.append(frozen_info)
                    
            except Exception as e:
                logger.warning(f"Could not read archive {archive_path}: {e}")
                frozen_list.append({
                    "filename": archive_path.name,
                    "path": str(archive_path),
                    "size": archive_path.stat().st_size,
                    "modified": datetime.fromtimestamp(archive_path.stat().st_mtime).isoformat(),
                    "error": str(e)
                })
        
        return frozen_list