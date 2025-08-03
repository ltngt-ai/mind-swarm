"""I/O Agent Mind - Extended mind for I/O Gateway agents."""

import logging
import os
from pathlib import Path

from .base_code_template.mind import AgentMind
from .io_cognitive_loop import IOCognitiveLoop

logger = logging.getLogger("agent.io_mind")


class IOAgentMind(AgentMind):
    """Extended agent mind for I/O Gateway agents."""
    
    def __init__(self):
        """Initialize I/O agent mind."""
        # Initialize base mind first
        super().__init__()
        
        # Replace cognitive loop with I/O version
        self.cognitive_loop = IOCognitiveLoop(self.name, self.home)
        
        # Log I/O agent specific info
        logger.info(f"I/O Gateway Agent {self.name} initialized")
        
        # Verify special body files
        self._verify_io_files()
        
    def _verify_io_files(self):
        """Verify I/O-specific body files exist."""
        network_file = self.home / "network"
        user_io_file = self.home / "user_io"
        
        if network_file.exists():
            logger.info("Network body file available")
        else:
            logger.warning("Network body file not found!")
        
        if user_io_file.exists():
            logger.info("User I/O body file available")
        else:
            logger.warning("User I/O body file not found!")