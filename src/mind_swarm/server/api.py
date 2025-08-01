"""Mind-Swarm server API using FastAPI."""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.utils.logging import logger


# API Models
class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""
    name: Optional[str] = None
    use_premium: bool = False
    config: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    """Request to send a command to an agent."""
    command: str
    params: Optional[Dict[str, Any]] = None


class QuestionRequest(BaseModel):
    """Request to create a plaza question."""
    text: str
    created_by: str = "user"


class StatusResponse(BaseModel):
    """Server status response."""
    agents: Dict[str, Dict[str, Any]]
    plaza_questions: int
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
        
        # Set up routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.on_event("startup")
        async def startup():
            """Initialize the coordinator on startup."""
            logger.info(f"Starting Mind-Swarm server on {self.host}:{self.port}")
            self.coordinator = SubspaceCoordinator()
            
            # Check bubblewrap
            if not await self.coordinator.subspace.check_bubblewrap():
                logger.error("Bubblewrap not available!")
                raise RuntimeError("Bubblewrap (bwrap) is required but not found")
            
            # Check local LLM server if using local models
            from mind_swarm.ai.providers.local_llm_check import check_local_llm_server, format_server_status
            from mind_swarm.core.config import settings
            
            # Check if any preset uses local model
            using_local = False
            local_url = None
            try:
                from mind_swarm.ai.presets import preset_manager
                for preset_name in ["local_explorer", "local_smart", "local_code"]:
                    preset = preset_manager.get_preset(preset_name)
                    if preset and preset.provider in ["openai_compatible", "local", "ollama"]:
                        # Get URL from api_settings
                        if preset.api_settings and "host" in preset.api_settings:
                            url = preset.api_settings["host"]
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
                    logger.warning("Local LLM server not available - agents using local models may not function properly")
            
            await self.coordinator.start()
            logger.info("Server initialized successfully")
        
        @self.app.on_event("shutdown")
        async def shutdown():
            """Clean shutdown."""
            logger.info("Shutting down Mind-Swarm server")
            if self.coordinator:
                await self.coordinator.stop()
            
            # Close all websocket connections
            for client in self.clients:
                await client.close()
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"name": "Mind-Swarm Server", "version": "0.1.0", "status": "running"}
        
        @self.app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Get server and agent status."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            agent_states = await self.coordinator.get_agent_states()
            questions = self.coordinator.get_plaza_questions()
            
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            # Check local LLM status
            local_llm_status = None
            try:
                from mind_swarm.ai.providers.local_llm_check import check_local_llm_server
                from mind_swarm.ai.presets import preset_manager
                
                # Check if using local models
                for preset_name in ["local_explorer", "local_smart", "local_code"]:
                    preset = preset_manager.get_preset(preset_name)
                    if preset and preset.provider in ["openai_compatible", "local", "ollama"]:
                        # Get URL from api_settings
                        if preset.api_settings and "host" in preset.api_settings:
                            url = preset.api_settings["host"]
                            is_healthy, model_info = await check_local_llm_server(url)
                            local_llm_status = {
                                "healthy": is_healthy,
                                "url": url,
                                **model_info
                            } if model_info else {"healthy": is_healthy, "url": url}
                            break
            except Exception as e:
                logger.debug(f"Could not check local LLM status: {e}")
            
            return StatusResponse(
                agents=agent_states,
                plaza_questions=len(questions),
                server_uptime=uptime,
                server_start_time=self.start_time.isoformat(),
                local_llm_status=local_llm_status
            )
        
        @self.app.post("/agents/create")
        async def create_agent(request: CreateAgentRequest):
            """Create a new agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                name = await self.coordinator.create_agent(
                    name=request.name,
                    use_premium=request.use_premium,
                    config=request.config
                )
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_created",
                    "name": name,
                    "use_premium": request.use_premium,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"name": name}
            except Exception as e:
                import traceback
                logger.error(f"Failed to create agent: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/agents/{name}")
        async def terminate_agent(name: str):
            """Terminate an agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                await self.coordinator.terminate_agent(name)
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_terminated",
                    "name": name,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"message": f"Agent {name} terminated"}
            except Exception as e:
                logger.error(f"Failed to terminate agent {name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/agents/{name}/command")
        async def send_command(name: str, request: CommandRequest):
            """Send a command to an agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
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
        
        @self.app.post("/plaza/questions")
        async def create_question(request: QuestionRequest):
            """Create a new plaza question."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                question_id = self.coordinator.create_plaza_question(
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
        
        @self.app.get("/plaza/questions")
        async def get_questions():
            """Get all plaza questions."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            questions = self.coordinator.get_plaza_questions()
            return {"questions": questions}
        
        @self.app.get("/agents/all")
        async def list_all_agents():
            """List all known agents including hibernating ones."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            agents = self.coordinator.list_all_agents()
            return {"agents": agents}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.clients.append(websocket)
            
            try:
                # Send initial status
                status = await get_status()
                await websocket.send_json({
                    "type": "status",
                    "data": status.dict()
                })
                
                # Keep connection alive
                while True:
                    # Could handle incoming messages here
                    data = await websocket.receive_text()
                    # For now, just echo
                    await websocket.send_text(f"Echo: {data}")
                    
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
    
    async def run(self):
        """Run the server."""
        import uvicorn
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    import asyncio
    server = MindSwarmServer()
    asyncio.run(server.run())