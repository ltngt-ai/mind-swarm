"""Mind-Swarm server API using FastAPI."""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.utils.logging import logger
from mind_swarm.server.monitoring_events import set_server_reference, get_event_emitter


# API Models
class CreateAgentRequest(BaseModel):
    """Request to create a new Cyber."""
    name: Optional[str] = None
    cyber_type: str = "general"
    config: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    """Request to send a command to an Cyber."""
    command: str
    params: Optional[Dict[str, Any]] = None


class MessageRequest(BaseModel):
    """Request to send a message to an Cyber."""
    content: str
    message_type: str = "text"


class QuestionRequest(BaseModel):
    """Request to create a community question."""
    text: str
    created_by: str = "user"


class RegisterDeveloperRequest(BaseModel):
    """Request model for registering a developer."""
    name: str
    full_name: Optional[str] = None
    email: Optional[str] = None


class SetCurrentDeveloperRequest(BaseModel):
    """Request model for setting current developer."""
    name: str


class MarkMessageReadRequest(BaseModel):
    """Request model for marking message as read."""
    message_index: int


class StatusResponse(BaseModel):
    """Server status response."""
    Cybers: Dict[str, Dict[str, Any]]
    community_questions: int
    server_uptime: float
    server_start_time: str
    local_llm_status: Optional[Dict[str, Any]] = None


class MindSwarmServer:
    """Main server for Mind-Swarm system."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        """Initialize the server.
        
        Args:
            host: Server host address
            port: Server port
        """
        self.host = host
        self.port = port
        self.app = FastAPI(title="Mind-Swarm Server", version="0.1.0")
        self.coordinator: Optional[SubspaceCoordinator] = None
        self.start_time = datetime.now()
        self.clients: List[WebSocket] = []
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176"],  # Vite dev servers
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Set up routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.on_event("startup")
        async def startup():
            """Initialize the coordinator on startup."""
            logger.info(f"Starting Mind-Swarm server on {self.host}:{self.port}")
            self.coordinator = SubspaceCoordinator()
            self._coordinator_ready = False
            
            # Set server reference for monitoring events
            set_server_reference(self)
            
            # Start the coordinator initialization in background
            # This prevents blocking the HTTP server startup
            asyncio.create_task(_initialize_coordinator())
            logger.info("Server startup initiated, coordinator initializing in background")
        
        async def _initialize_coordinator():
            """Initialize coordinator in background to not block HTTP server."""
            try:
                # Check bubblewrap
                if not await self.coordinator.subspace.check_bubblewrap():
                    logger.error("Bubblewrap not available!")
                    raise RuntimeError("Bubblewrap (bwrap) is required but not found")
                
                # Check local LLM server if using local models
                from mind_swarm.ai.providers.local_llm_check import check_local_llm_server, format_server_status
                from mind_swarm.core.config import settings
                
                # Check if any model in pool uses local OpenAI server
                using_local = False
                local_url = None
                try:
                    from mind_swarm.ai.model_pool import model_pool
                    for model in model_pool.list_models(include_paid=True):
                        if model.provider == "openai" and model.api_settings and "host" in model.api_settings:
                            # This is a local OpenAI-compatible server
                            url = model.api_settings["host"]
                            using_local = True
                            local_url = url
                            break
                except:
                    pass
                
                if using_local and local_url:
                    is_healthy, model_info = await check_local_llm_server(local_url)
                    status = format_server_status(is_healthy, model_info)
                    logger.info(f"Local LLM check: {status}")
                    
                    if not is_healthy:
                        logger.warning("Local LLM server not available - Cybers using local models may not function properly")
                
                await self.coordinator.start()
                self._coordinator_ready = True
                logger.info("Server initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize coordinator: {e}", exc_info=True)
                # Store the error so we can report it in status
                self._initialization_error = str(e)
        
        @self.app.on_event("shutdown")
        async def shutdown():
            """Clean shutdown."""
            logger.info("FastAPI shutdown event triggered")
            # The actual shutdown is handled by the daemon's shutdown method
            # We just need to close websocket connections here
            for client in self.clients:
                try:
                    await client.close()
                except:
                    pass
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"name": "Mind-Swarm Server", "version": "0.1.0", "status": "running"}
        
        @self.app.get("/status", response_model=StatusResponse)
        async def get_status(check_llm: bool = True):
            """Get server and Cyber status.
            
            Args:
                check_llm: Whether to check local LLM status (can be slow)
            """
            import time
            endpoint_start = time.time()
            logger.info(f"STATUS: /status endpoint called (check_llm={check_llm})")
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            # If coordinator is not ready yet, return minimal status
            if not getattr(self, '_coordinator_ready', False):
                return StatusResponse(
                    Cybers={},
                    community_questions=0,
                    server_uptime=(datetime.now() - self.start_time).total_seconds(),
                    server_start_time=self.start_time.isoformat(),
                    local_llm_status=None
                )
            
            cyber_states = await self.coordinator.get_cyber_states()
            questions = await self.coordinator.get_community_questions()
            
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            # Check local LLM status with timeout
            local_llm_status = None
            if check_llm:
                try:
                    from mind_swarm.ai.providers.local_llm_check import check_local_llm_server
                    from mind_swarm.ai.model_pool import model_pool
                    import asyncio
                    
                    # Check if using local models (OpenAI with custom host)
                    for model in model_pool.list_models(include_paid=True):
                        if model.provider == "openai" and model.api_settings and "host" in model.api_settings:
                            # This is a local OpenAI-compatible server
                            url = model.api_settings["host"]
                            logger.info(f"STATUS: Checking local LLM server at {url}")
                            start_time = time.time()
                            
                            # Add timeout to prevent hanging
                            try:
                                is_healthy, model_info = await asyncio.wait_for(
                                        check_local_llm_server(url),
                                        timeout=2.0  # 2 second timeout for status checks
                                )
                                elapsed = time.time() - start_time
                                logger.info(f"STATUS: Local LLM check completed in {elapsed:.2f}s - healthy={is_healthy}")
                                local_llm_status = {
                                        "healthy": is_healthy,
                                        "url": url,
                                        **model_info
                                } if model_info else {"healthy": is_healthy, "url": url}
                            except asyncio.TimeoutError:
                                elapsed = time.time() - start_time
                                logger.warning(f"STATUS: Local LLM check timed out after {elapsed:.2f}s")
                                local_llm_status = {"healthy": False, "url": url, "error": "Timeout checking LLM server"}
                            break
                except Exception as e:
                    logger.warning(f"STATUS: Local LLM check failed with exception: {e}")
            
            response = StatusResponse(
                Cybers=cyber_states,
                community_questions=len(questions),
                server_uptime=uptime,
                server_start_time=self.start_time.isoformat(),
                local_llm_status=local_llm_status
            )
            logger.info(f"STATUS: /status endpoint completed in {time.time() - endpoint_start:.2f}s total")
            return response
        
        @self.app.post("/Cybers/create")
        async def create_agent(request: CreateAgentRequest):
            """Create a new Cyber."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                name = await self.coordinator.create_agent(
                    name=request.name,
                    cyber_type=request.cyber_type,
                    config=request.config
                )
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_created",
                    "name": name,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"name": name}
            except Exception as e:
                import traceback
                logger.error(f"Failed to create Cyber: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/Cybers/{name}")
        async def terminate_agent(name: str):
            """Terminate an Cyber."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                await self.coordinator.terminate_agent(name)
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_terminated",
                    "name": name,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"message": f"Cyber {name} terminated"}
            except Exception as e:
                logger.error(f"Failed to terminate Cyber {name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/Cybers/{name}/command")
        async def send_command(name: str, request: CommandRequest):
            """Send a command to an Cyber."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                await self.coordinator.send_command(
                    name, 
                    request.command, 
                    request.params
                )
                return {"message": f"Command sent to {name}"}
            except Exception as e:
                logger.error(f"Failed to send command: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/Cybers/{name}/message")
        async def send_message(name: str, request: MessageRequest):
            """Send a message to an Cyber."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                await self.coordinator.send_message(
                    name, 
                    request.content,
                    request.message_type
                )
                return {"message": f"Message sent to {name}"}
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/community/questions")
        async def create_question(request: QuestionRequest):
            """Create a new community question."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                question_id = await self.coordinator.create_community_question(
                    request.text, 
                    request.created_by
                )
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "question_created",
                    "question_id": question_id,
                    "text": request.text,
                    "created_by": request.created_by,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"question_id": question_id}
            except Exception as e:
                logger.error(f"Failed to create question: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/community/questions")
        async def get_questions():
            """Get all community questions."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                return {"questions": []}
            
            questions = await self.coordinator.get_community_questions()
            return {"questions": questions}
        
        @self.app.get("/Cybers/all")
        async def list_all_agents():
            """List all known Cybers including hibernating ones."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                return {"cybers": []}
            
            Cybers = await self.coordinator.list_all_agents()
            return {"cybers": Cybers}
        
        @self.app.post("/developers/register")
        async def register_developer(request: RegisterDeveloperRequest):
            """Register a new developer."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                cyber_name = await self.coordinator.register_developer(
                    request.name,
                    request.full_name,
                    request.email
                )
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "developer_registered",
                    "name": request.name,
                    "cyber_name": cyber_name,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"cyber_name": cyber_name}
            except Exception as e:
                logger.error(f"Failed to register developer: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/developers/current")
        async def set_current_developer(request: SetCurrentDeveloperRequest):
            """Set the current developer."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                success = await self.coordinator.set_current_developer(request.name)
                if not success:
                    raise HTTPException(status_code=404, detail=f"Developer {request.name} not found")
                
                return {"success": success}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to set current developer: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/developers/current")
        async def get_current_developer():
            """Get the current developer."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                return {"developer": None}
            
            try:
                developer = await self.coordinator.get_current_developer()
                return {"developer": developer}
            except Exception as e:
                logger.error(f"Failed to get current developer: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/developers")
        async def list_developers():
            """List all registered developers."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                return {"developers": {}}
            
            try:
                developers = await self.coordinator.list_developers()
                return {"developers": developers}
            except Exception as e:
                logger.error(f"Failed to list developers: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/developers/mailbox")
        async def check_mailbox(include_read: bool = False):
            """Check current developer's mailbox."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                return {"messages": []}
            
            try:
                messages = await self.coordinator.check_developer_mailbox(include_read=include_read)
                return {"messages": messages}
            except Exception as e:
                logger.error(f"Failed to check mailbox: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/developers/mailbox/read")
        async def mark_message_read(request: MarkMessageReadRequest):
            """Mark a message as read."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                success = await self.coordinator.mark_developer_message_read(request.message_index)
                return {"success": success}
            except Exception as e:
                logger.error(f"Failed to mark message as read: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/filesystem/structure")
        async def get_filesystem_structure():
            """Get the subspace filesystem structure."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            if not getattr(self, '_coordinator_ready', False):
                raise HTTPException(status_code=503, detail="Server still initializing, please wait")
            
            try:
                from pathlib import Path
                import os
                
                # Get the actual subspace root
                subspace_root = self.coordinator.subspace.root_path
                
                def build_directory_tree(path: Path, max_depth: int = 3, current_depth: int = 0):
                    """Recursively build directory tree structure."""
                    if current_depth >= max_depth:
                        return None
                        
                    if not path.exists() or not path.is_dir():
                        return None
                    
                    node = {
                        "name": path.name,
                        "path": str(path.relative_to(subspace_root.parent)) if subspace_root.parent in path.parents or path == subspace_root else path.name,
                        "type": "directory",
                        "children": []
                    }
                    
                    try:
                        # Get subdirectories only (not files)
                        for item in sorted(path.iterdir()):
                            if item.is_dir() and not item.name.startswith('.'):
                                child = build_directory_tree(item, max_depth, current_depth + 1)
                                if child:
                                    node["children"].append(child)
                    except PermissionError:
                        pass
                    
                    return node
                
                # Build the grid structure
                grid_path = subspace_root / "grid"
                grid_structure = None
                if grid_path.exists():
                    grid_structure = build_directory_tree(grid_path, max_depth=3)
                
                # Get cyber home directories
                cyber_homes = []
                cybers_path = subspace_root / "cybers"
                if cybers_path.exists():
                    try:
                        for cyber_home in sorted(cybers_path.iterdir()):
                            if cyber_home.is_dir() and not cyber_home.name.startswith('.'):
                                cyber_homes.append({
                                    "name": cyber_home.name,
                                    "path": str(cyber_home.relative_to(subspace_root.parent)),
                                    "type": "directory"
                                })
                    except PermissionError:
                        pass
                
                return {
                    "grid": grid_structure,
                    "cyber_homes": cyber_homes
                }
                
            except Exception as e:
                logger.error(f"Failed to get filesystem structure: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.clients.append(websocket)
            
            try:
                # Send a simple connection confirmation instead of full status
                await websocket.send_json({
                    "type": "connected",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Keep connection alive
                while True:
                    try:
                        # Wait for client messages with timeout
                        data = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=300.0  # 5 minute timeout
                        )
                        # Handle ping messages
                        if data == "ping":
                            await websocket.send_text("pong")
                        else:
                            # Echo other messages
                            await websocket.send_text(f"Echo: {data}")
                    except asyncio.TimeoutError:
                        # Send periodic ping to keep connection alive
                        try:
                            await websocket.send_text("ping")
                        except:
                            break  # Connection is dead
                    
            except WebSocketDisconnect:
                self.clients.remove(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.clients.remove(websocket)
    
    async def _broadcast_event(self, event: Dict[str, Any]):
        """Broadcast an event to all connected WebSocket clients."""
        disconnected = []
        for client in self.clients:
            try:
                await client.send_json(event)
            except:
                disconnected.append(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            self.clients.remove(client)
    
    async def shutdown(self):
        """Shutdown the server and coordinator gracefully."""
        logger.info("Shutting down Mind-Swarm server")
        if self.coordinator:
            logger.info("Stopping coordinator...")
            await self.coordinator.stop()
            logger.info("Coordinator stopped")
        
        # Close all websocket connections
        logger.info(f"Closing {len(self.clients)} websocket connections...")
        for client in self.clients:
            try:
                await client.close()
            except:
                pass
        self.clients.clear()
        logger.info("Server shutdown method complete")
    
    async def run(self):
        """Run the server."""
        import uvicorn
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()


if __name__ == "__main__":
    import asyncio
    server = MindSwarmServer()
    asyncio.run(server.run())