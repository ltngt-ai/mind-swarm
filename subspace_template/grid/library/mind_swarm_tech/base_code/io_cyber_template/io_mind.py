"""I/O Cyber Mind - Extended mind for I/O Gateway Cybers."""

import logging
import os
from pathlib import Path

from .base_code_template.mind import CyberMind
from .io_cognitive_loop import IOCognitiveLoop

logger = logging.getLogger("Cyber.io_mind")


class IOCyberMind(CyberMind):
    """Extended Cyber mind for I/O Gateway Cybers."""
    
    def __init__(self):
        """Initialize I/O Cyber mind."""
        # Initialize base mind first
        super().__init__()
        
        # Replace cognitive loop with I/O version
        self.cognitive_loop = IOCognitiveLoop(self.name, self.personal)
        
        # Log I/O Cyber specific info
        logger.info(f"I/O Gateway Cyber {self.name} initialized")
        
        # Verify special body files
        self._verify_io_files()
        
    def _verify_io_files(self):
        """Verify I/O-specific body files exist."""
        network_file = self.personal / "network"
        user_io_file = self.personal / "user_io"
        
        if network_file.exists():
            logger.info("Network body file available")
        else:
            logger.warning("Network body file not found!")
        
        if user_io_file.exists():
            logger.info("User I/O body file available")
        else:
            logger.warning("User I/O body file not found!")