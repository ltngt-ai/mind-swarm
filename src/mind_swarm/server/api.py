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
class SpawnAgentRequest(BaseModel):
    """Request to spawn a new agent."""
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
            
            return StatusResponse(
                agents=agent_states,
                plaza_questions=len(questions),
                server_uptime=uptime,
                server_start_time=self.start_time.isoformat()
            )
        
        @self.app.post("/agents/spawn")
        async def spawn_agent(request: SpawnAgentRequest):
            """Spawn a new agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                agent_id = await self.coordinator.spawn_agent(
                    name=request.name,
                    use_premium=request.use_premium,
                    config=request.config
                )
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_spawned",
                    "agent_id": agent_id,
                    "name": request.name,
                    "use_premium": request.use_premium,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"agent_id": agent_id}
            except Exception as e:
                logger.error(f"Failed to spawn agent: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/agents/{agent_id}")
        async def terminate_agent(agent_id: str):
            """Terminate an agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                await self.coordinator.terminate_agent(agent_id)
                
                # Notify websocket clients
                await self._broadcast_event({
                    "type": "agent_terminated",
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                return {"message": f"Agent {agent_id} terminated"}
            except Exception as e:
                logger.error(f"Failed to terminate agent {agent_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/agents/{agent_id}/command")
        async def send_command(agent_id: str, request: CommandRequest):
            """Send a command to an agent."""
            if not self.coordinator:
                raise HTTPException(status_code=503, detail="Server not initialized")
            
            try:
                await self.coordinator.send_command(
                    agent_id, 
                    request.command, 
                    request.params
                )
                return {"message": f"Command sent to {agent_id}"}
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