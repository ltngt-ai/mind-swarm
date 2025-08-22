"""Body file management for Cyber interfaces.

Body files are special files in an Cyber's home directory that act as
interfaces to capabilities. They appear as regular files to Cybers but
trigger actions when written to.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import aiofiles
import aiofiles.os

from mind_swarm.utils.logging import logger


class BodyFile:
    """Represents a body file interface."""
    
    def __init__(self, name: str, help_text: str, handler: Optional[Callable] = None):
        """Initialize a body file.
        
        Args:
            name: File name (e.g., "brain", "voice")
            help_text: Text shown when file is read
            handler: Async function to handle writes
        """
        self.name = name
        self.help_text = help_text
        self.handler = handler


class BodyManager:
    """Manages body files for an Cyber."""
    
    def __init__(self, name: str, cyber_personal: Path, knowledge_handler=None, awareness_handler=None, cbr_handler=None):
        """Initialize body manager for an Cyber.
        
        Args:
            name: Cyber's unique name
            cyber_personal: Cyber's home directory path
            knowledge_handler: Optional knowledge handler for knowledge body file
            awareness_handler: Optional awareness handler for awareness body file
            cbr_handler: Optional CBR handler for CBR body file
        """
        self.name = name
        self.cyber_personal = cyber_personal
        self.body_files: Dict[str, BodyFile] = {}
        self._watch_task: Optional[asyncio.Task] = None
        self.knowledge_handler = knowledge_handler
        self.awareness_handler = awareness_handler
        self.cbr_handler = cbr_handler
        
    async def create_body_files(self):
        """Create the standard body files for an Cyber."""
        # Brain - for thinking
        brain = BodyFile("brain", "")
        self.body_files["brain"] = brain
        
        # Knowledge - for searching and storing knowledge
        if self.knowledge_handler:
            knowledge = BodyFile("knowledge_api", "")
            self.body_files["knowledge_api"] = knowledge
        
        # Awareness - for environmental awareness queries
        if self.awareness_handler:
            awareness = BodyFile("awareness", "")
            self.body_files["awareness"] = awareness
        
        # CBR - for case-based reasoning
        if self.cbr_handler:
            cbr = BodyFile("cbr_api", "")
            self.body_files["cbr_api"] = cbr
        
        # Voice file removed - not implemented
        
        # Create the actual files in .internal directory
        internal_dir = self.cyber_personal / ".internal"
        internal_dir.mkdir(exist_ok=True)
        
        for name, body_file in self.body_files.items():
            file_path = internal_dir / name
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(body_file.help_text)
            # Set read-only from Cyber's perspective
            file_path.chmod(0o644)
            
        logger.info(f"Created body files for Cyber {self.name}")
    
    async def start_monitoring(self, ai_handler: Callable):
        """Start monitoring body files for changes.
        
        Args:
            ai_handler: Async function to handle AI requests
        """
        self.body_files["brain"].handler = ai_handler
        self._watch_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started body file monitoring for {self.name}")
    
    async def stop_monitoring(self):
        """Stop monitoring body files."""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped body file monitoring for {self.name}")
    
    async def _monitor_loop(self):
        """Main loop for monitoring body files."""
        # Track what we're currently processing
        processing: Dict[str, bool] = {}
        loop_count = 0
        
        logger.debug(f"MONITOR: Starting monitor loop for {self.name}")
        
        while True:
            try:
                loop_count += 1
                
                # Log periodically to prove the loop is running
                if loop_count % 1000 == 0:
                    logger.debug(f"MONITOR: Loop #{loop_count} for {self.name}, processing state: {processing}")
                
                for name, body_file in self.body_files.items():
                    file_path = self.cyber_personal / ".internal" / name
                    
                    if not await aiofiles.os.path.exists(file_path):
                        if loop_count % 1000 == 0:
                            logger.debug(f"MONITOR: File {name} does not exist for {self.name}")
                        continue
                    
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                    
                    # Log brain file content checks more frequently
                    if name == "brain" and loop_count % 500 == 0:
                        logger.debug(f"MONITOR: Brain file check #{loop_count} for {self.name}")
                        logger.debug(f"MONITOR: Content length: {len(content)}, has END marker: {'<<<END_THOUGHT>>>' in content}")
                        logger.debug(f"MONITOR: Processing state for brain: {processing.get('brain', False)}")
                    
                    # For brain file, check for end marker
                    if name == "brain":
                        # Debug: log what we're seeing in the brain file
                        if content != body_file.help_text:
                            logger.debug(f"Brain file content for {self.name}: length={len(content)}, first 100 chars: {repr(content[:100])}")
                            logger.debug(f"Contains END_THOUGHT: {'<<<END_THOUGHT>>>' in content}")
                        
                        if "<<<END_THOUGHT>>>" in content and not processing.get(name, False):
                            # Cyber has written a thought and is waiting
                            processing[name] = True
                            
                            # Extract the prompt
                            prompt = content.split("<<<END_THOUGHT>>>")[0].strip()
                            logger.info(f"BODY: Brain activated by {self.name}, prompt length: {len(prompt)}")
                            logger.debug(f"BODY: Prompt preview: {prompt[:200]}..." if len(prompt) > 200 else f"BODY: Prompt preview: {prompt}")
                            
                            if body_file.handler:
                                logger.info(f"BODY: Calling brain handler for {self.name}")
                                # Process the thought
                                response = await body_file.handler(self.name, prompt)
                                
                                logger.info(f"BODY: Got response from handler, length: {len(response)}")
                                logger.debug(f"BODY: Response preview: {response[:200]}..." if len(response) > 200 else f"BODY: Response preview: {response}")
                                
                                # Write response with completion marker
                                # From Cyber's perspective, this happens instantly
                                # Check if response already has completion marker
                                if "<<<THOUGHT_COMPLETE>>>" not in response:
                                    final_response = f"{response}\n<<<THOUGHT_COMPLETE>>>"
                                else:
                                    final_response = response
                                
                                logger.info(f"BODY: Writing response to brain file for {self.name}")
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(final_response)
                                logger.info(f"BODY: Successfully wrote response to brain file")
                                
                                # After writing response, reset processing flag so we can handle the next request
                                logger.debug(f"MONITOR: Request processed, resetting processing flag for {self.name}")
                                processing[name] = False
                            else:
                                logger.error(f"BODY: No handler for brain file of {self.name}")
                        
                        elif not content.strip() or "<<<THOUGHT_COMPLETE>>>" in content:
                            # File is empty or has completed response, we can process again
                            if processing.get(name, False):
                                logger.debug(f"MONITOR: Brain file ready for next request from {self.name}")
                            processing[name] = False
                    
                    # For knowledge file, check for complete request with marker
                    elif name == "knowledge_api" and self.knowledge_handler:
                        # Check for request completion marker
                        if "<<<END_KNOWLEDGE_REQUEST>>>" in content and not processing.get(name, False):
                            try:
                                # Extract the request (everything before the marker)
                                request_text = content.split("<<<END_KNOWLEDGE_REQUEST>>>")[0].strip()
                                
                                # Skip if empty
                                if not request_text:
                                    continue
                                
                                # Parse the JSON request
                                request = json.loads(request_text)
                                
                                if "request_id" in request and "operation" in request:
                                    processing[name] = True
                                    logger.info(f"BODY: Knowledge request from {self.name}: {request.get('operation')}")
                                    
                                    # Process the request
                                    response = await self.knowledge_handler.process_request(self.name, request)
                                    
                                    # Handle None response (shouldn't happen with fixed handlers, but be safe)
                                    if response is None:
                                        response = {
                                            "request_id": request.get('request_id', 'error'),
                                            "status": "error",
                                            "error": "Knowledge system not available"
                                        }
                                    
                                    # Write response with completion marker
                                    response_text = json.dumps(response, indent=2)
                                    final_response = f"{response_text}\n<<<KNOWLEDGE_COMPLETE>>>"
                                    
                                    async with aiofiles.open(file_path, 'w') as f:
                                        await f.write(final_response)
                                    
                                    logger.info(f"BODY: Knowledge response written for {self.name}")
                                    processing[name] = False
                                else:
                                    logger.warning(f"Invalid knowledge request from {self.name}: missing required fields")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON in knowledge request from {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": f"Invalid JSON: {str(e)}"
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<KNOWLEDGE_COMPLETE>>>")
                                processing[name] = False
                                
                            except Exception as e:
                                logger.error(f"Error processing knowledge request for {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": str(e)
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<KNOWLEDGE_COMPLETE>>>")
                                processing[name] = False
                        
                        elif not content.strip() or "<<<KNOWLEDGE_COMPLETE>>>" in content:
                            # File is empty or has completed response, we can process again  
                            if processing.get(name, False):
                                logger.debug(f"MONITOR: Knowledge file ready for next request from {self.name}")
                            processing[name] = False
                    
                    # For CBR file, check for complete request with marker
                    elif name == "cbr_api" and self.cbr_handler:
                        # Check for request completion marker
                        if "<<<END_CBR_REQUEST>>>" in content and not processing.get(name, False):
                            try:
                                # Extract the request (everything before the marker)
                                request_text = content.split("<<<END_CBR_REQUEST>>>")[0].strip()
                                
                                # Skip if empty
                                if not request_text:
                                    continue
                                
                                # Parse the JSON request
                                request = json.loads(request_text)
                                
                                if "request_id" in request and "operation" in request:
                                    processing[name] = True
                                    logger.info(f"BODY: CBR request from {self.name}: {request.get('operation')}")
                                    
                                    # Process the request
                                    response = await self.cbr_handler.handle_request(self.name, request)
                                    
                                    # Handle None response (shouldn't happen with fixed handlers, but be safe)
                                    if response is None:
                                        response = {
                                            "request_id": request.get('request_id', 'error'),
                                            "status": "error",
                                            "error": "CBR system not available"
                                        }
                                    
                                    # Write response with completion marker
                                    response_text = json.dumps(response, indent=2)
                                    final_response = f"{response_text}\n<<<CBR_COMPLETE>>>"
                                    
                                    async with aiofiles.open(file_path, 'w') as f:
                                        await f.write(final_response)
                                    
                                    logger.info(f"BODY: CBR response written for {self.name}")
                                    processing[name] = False
                                else:
                                    logger.warning(f"Invalid CBR request from {self.name}: missing required fields")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON in CBR request from {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": f"Invalid JSON: {str(e)}"
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<CBR_COMPLETE>>>")
                                processing[name] = False
                                
                            except Exception as e:
                                logger.error(f"Error processing CBR request for {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": str(e)
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<CBR_COMPLETE>>>")
                                processing[name] = False
                        
                        elif not content.strip() or "<<<CBR_COMPLETE>>>" in content:
                            # File is empty or has completed response, we can process again  
                            if processing.get(name, False):
                                logger.debug(f"MONITOR: CBR file ready for next request from {self.name}")
                            processing[name] = False
                    
                    # For awareness file, check for complete request with marker
                    elif name == "awareness" and self.awareness_handler:
                        # Check for request completion marker
                        if "<<<END_AWARENESS_REQUEST>>>" in content and not processing.get(name, False):
                            try:
                                # Extract the request (everything before the marker)
                                request_text = content.split("<<<END_AWARENESS_REQUEST>>>")[0].strip()
                                
                                # Skip if empty
                                if not request_text:
                                    continue
                                
                                # Parse the JSON request
                                request = json.loads(request_text)
                                
                                if "request_id" in request and "query_type" in request:
                                    processing[name] = True
                                    logger.info(f"BODY: Awareness request from {self.name}: {request.get('query_type')}")
                                    
                                    # Process the request
                                    response = await self.awareness_handler.handle_request(self.name, request)
                                    
                                    # Write response with completion marker
                                    response_text = json.dumps(response, indent=2)
                                    final_response = f"{response_text}\n<<<AWARENESS_COMPLETE>>>"
                                    
                                    async with aiofiles.open(file_path, 'w') as f:
                                        await f.write(final_response)
                                    
                                    logger.info(f"BODY: Awareness response written for {self.name}")
                                    processing[name] = False
                                else:
                                    logger.warning(f"Invalid awareness request from {self.name}: missing required fields")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON in awareness request from {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": f"Invalid JSON: {str(e)}"
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<AWARENESS_COMPLETE>>>")
                                processing[name] = False
                                
                            except Exception as e:
                                logger.error(f"Error processing awareness request for {self.name}: {e}")
                                # Write error response with marker
                                error_response = {
                                    "request_id": "error",
                                    "status": "error",
                                    "error": str(e)
                                }
                                error_text = json.dumps(error_response, indent=2)
                                async with aiofiles.open(file_path, 'w') as f:
                                    await f.write(f"{error_text}\n<<<AWARENESS_COMPLETE>>>")
                                processing[name] = False
                        
                        elif not content.strip() or "<<<AWARENESS_COMPLETE>>>" in content:
                            # File is empty or has completed response, we can process again  
                            if processing.get(name, False):
                                logger.debug(f"MONITOR: Awareness file ready for next request from {self.name}")
                            processing[name] = False
                
                # Adaptive delay - longer when nothing is happening
                if any(processing.values()):
                    # Active processing, check more frequently
                    await asyncio.sleep(0.05)
                else:
                    # Nothing happening, check less frequently
                    await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error in body file monitor for {self.name}: {e}")
                await asyncio.sleep(1)


class BodySystemManager:
    """Manages body files for all Cybers."""
    
    def __init__(self, knowledge_handler=None, awareness_handler=None, cbr_handler=None):
        """Initialize the body system manager."""
        self.body_managers: Dict[str, BodyManager] = {}
        self.knowledge_handler = knowledge_handler
        self.awareness_handler = awareness_handler
        self.cbr_handler = cbr_handler
        
    async def create_agent_body(self, name: str, cyber_personal: Path) -> BodyManager:
        """Create body files for a new Cyber.
        
        Args:
            name: Cyber's unique name  
            cyber_personal: Cyber's home directory path
            
        Returns:
            BodyManager instance for the Cyber
        """
        manager = BodyManager(name, cyber_personal, self.knowledge_handler, self.awareness_handler, self.cbr_handler)
        await manager.create_body_files()
        self.body_managers[name] = manager
        return manager
    
    async def start_agent_monitoring(self, name: str, ai_handler: Callable):
        """Start monitoring body files for an Cyber.
        
        Args:
            name: Cyber's unique name
            ai_handler: Async function to handle AI requests
        """
        if name in self.body_managers:
            await self.body_managers[name].start_monitoring(ai_handler)
    
    async def stop_agent_monitoring(self, name: str):
        """Stop monitoring body files for an Cyber.
        
        Args:
            name: Cyber's unique name
        """
        if name in self.body_managers:
            await self.body_managers[name].stop_monitoring()
            del self.body_managers[name]
    
    async def shutdown(self):
        """Shutdown all body file monitoring."""
        for name in list(self.body_managers.keys()):
            await self.stop_agent_monitoring(name)