#!/usr/bin/env python3
"""
Production-Ready Multi-Process AI Agent Example

This example demonstrates a robust, production-ready implementation
of an AI agent using the multi-process cognitive loop pattern.

Features:
- Comprehensive error handling and recovery
- Structured logging and monitoring
- Configuration management
- Health checking and diagnostics
- Graceful shutdown handling
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Configuration for production AI agent."""
    agent_id: str
    max_iterations: int = 100
    iteration_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 2.0
    session_timeout: int = 3600
    health_check_interval: float = 60.0
    log_level: str = "INFO"
    workspace_dir: str = "/tmp/agent_workspace"
    
    @classmethod
    def from_file(cls, config_path: str) -> 'AgentConfig':
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return cls(**config_data)
    
    def to_file(self, config_path: str):
        """Save configuration to JSON file."""
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

@dataclass
class AgentState:
    """Current state of the AI agent."""
    session_id: Optional[str] = None
    current_task: Optional[str] = None
    iteration_count: int = 0
    last_observation: Optional[Dict] = None
    last_action: Optional[Dict] = None
    error_count: int = 0
    start_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    
    def reset(self):
        """Reset agent state for new task."""
        self.session_id = None
        self.current_task = None
        self.iteration_count = 0
        self.last_observation = None
        self.last_action = None
        self.error_count = 0
        self.start_time = datetime.now()
        self.last_health_check = datetime.now()

class ProductionAgent:
    """Production-ready multi-process AI agent."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = AgentState()
        self.workspace = Path(config.workspace_dir)
        self.workspace.mkdir(exist_ok=True)
        
        # Set up logging level
        logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))
        
        logger.info(f"Initialized agent {config.agent_id}")
    
    def create_session(self, command: str, name: Optional[str] = None) -> str:
        """Create a new terminal session with error handling."""
        session_name = name or f"{self.config.agent_id}_{int(time.time())}"
        
        for attempt in range(self.config.retry_attempts):
            try:
                logger.info(f"Creating session '{session_name}' with command: {command}")
                
                result = subprocess.run([
                    'python3', 'multi_process_workflow.py', 'create', command,
                    '--name', session_name, '--json'
                ], capture_output=True, text=True, timeout=self.config.iteration_timeout)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Session creation failed: {result.stderr}")
                
                # Parse session data
                output_lines = [line for line in result.stdout.split('\n') if line.strip()]
                session_data = json.loads(output_lines[-1])
                
                session_id = session_data['session_id']
                self.state.session_id = session_id
                
                logger.info(f"Created session {session_id}")
                return session_id
                
            except Exception as e:
                logger.warning(f"Session creation attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    raise RuntimeError(f"Failed to create session after {self.config.retry_attempts} attempts")
    
    def observe_session(self, session_id: str) -> Dict[str, Any]:
        """Observe terminal session state with comprehensive error handling."""
        for attempt in range(self.config.retry_attempts):
            try:
                logger.debug(f"Observing session {session_id}")
                
                result = subprocess.run([
                    'python3', 'multi_process_workflow.py', 'read',
                    session_id, '--json'
                ], capture_output=True, text=True, timeout=self.config.iteration_timeout)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Observation failed: {result.stderr}")
                
                # Parse observation data
                output_lines = [line for line in result.stdout.split('\n') if line.strip()]
                observation = json.loads(output_lines[-1])
                
                # Enhance observation with analysis
                enhanced_observation = self._analyze_observation(observation)
                self.state.last_observation = enhanced_observation
                
                logger.debug(f"Observation successful: {len(enhanced_observation.get('text', ''))} chars")
                return enhanced_observation
                
            except Exception as e:
                logger.warning(f"Observation attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay)
                else:
                    raise RuntimeError(f"Failed to observe session after {self.config.retry_attempts} attempts")
    
    def _analyze_observation(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze observation data for AI-friendly processing."""
        text = observation.get('text', '')
        
        # Basic pattern detection
        analysis = {
            'has_prompt': any(prompt in text for prompt in ['$', '>', '>>>', 'C:\\']),
            'has_error': any(error in text.lower() for error in ['error', 'failed', 'exception', 'traceback']),
            'appears_busy': any(indicator in text for indicator in ['...', 'loading', 'processing']),
            'line_count': len(text.split('\n')),
            'last_line': text.split('\n')[-1] if text else '',
            'word_count': len(text.split()),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add analysis to observation
        observation['analysis'] = analysis
        return observation
    
    def decide_action(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """AI decision-making process (placeholder for actual AI integration)."""
        analysis = observation.get('analysis', {})
        text = observation.get('text', '')
        
        # Simple rule-based decision making (replace with actual AI/LLM calls)
        if analysis.get('has_error'):
            return {
                'action': 'input',
                'data': 'echo "Recovering from error..."',
                'reason': 'Error recovery',
                'confidence': 0.9
            }
        
        elif analysis.get('has_prompt') and not analysis.get('appears_busy'):
            # System is ready for input
            if 'hello' not in text.lower():
                return {
                    'action': 'input',
                    'data': 'echo "Hello from production AI agent!"',
                    'reason': 'Initial greeting',
                    'confidence': 0.8
                }
            elif 'date' not in text:
                return {
                    'action': 'input',
                    'data': 'date',
                    'reason': 'Check system time',
                    'confidence': 0.7
                }
            elif 'uptime' not in text:
                return {
                    'action': 'input',
                    'data': 'uptime',
                    'reason': 'Check system uptime',
                    'confidence': 0.7
                }
            else:
                return {
                    'action': 'complete',
                    'reason': 'Task objectives completed',
                    'confidence': 0.9
                }
        
        elif analysis.get('appears_busy'):
            return {
                'action': 'wait',
                'reason': 'System appears busy',
                'confidence': 0.6
            }
        
        else:
            return {
                'action': 'wait',
                'reason': 'Unclear system state',
                'confidence': 0.3
            }
    
    def execute_action(self, session_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute decided action with comprehensive error handling."""
        action = decision.get('action')
        
        if action == 'wait':
            logger.info(f"Waiting: {decision.get('reason', 'No reason provided')}")
            time.sleep(2.0)
            return {'success': True, 'action': 'wait'}
        
        elif action == 'complete':
            logger.info(f"Task completed: {decision.get('reason', 'No reason provided')}")
            return {'success': True, 'action': 'complete'}
        
        elif action == 'input':
            data = decision.get('data', '')
            
            for attempt in range(self.config.retry_attempts):
                try:
                    logger.info(f"Executing command: {data}")
                    
                    result = subprocess.run([
                        'python3', 'multi_process_workflow.py', 'input',
                        session_id, data, '--json'
                    ], capture_output=True, text=True, timeout=self.config.iteration_timeout)
                    
                    if result.returncode != 0:
                        raise RuntimeError(f"Action execution failed: {result.stderr}")
                    
                    # Parse result
                    output_lines = [line for line in result.stdout.split('\n') if line.strip()]
                    action_result = json.loads(output_lines[-1])
                    
                    self.state.last_action = {
                        'decision': decision,
                        'result': action_result,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    logger.info(f"Action executed successfully")
                    return action_result
                    
                except Exception as e:
                    logger.warning(f"Action execution attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.retry_attempts - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise RuntimeError(f"Failed to execute action after {self.config.retry_attempts} attempts")
        
        else:
            raise ValueError(f"Unknown action type: {action}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            'agent_id': self.config.agent_id,
            'timestamp': datetime.now().isoformat(),
            'uptime': None,
            'session_status': 'unknown',
            'error_rate': 0.0,
            'iteration_count': self.state.iteration_count,
            'memory_usage': None,
            'status': 'healthy'
        }
        
        try:
            # Calculate uptime
            if self.state.start_time:
                uptime = datetime.now() - self.state.start_time
                health_status['uptime'] = str(uptime)
            
            # Check session status
            if self.state.session_id:
                try:
                    result = subprocess.run([
                        'python3', 'multi_process_workflow.py', 'list', '--json'
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        output_lines = [line for line in result.stdout.split('\n') if line.strip()]
                        sessions = json.loads(output_lines[-1])
                        
                        session_found = any(
                            s.get('session_id') == self.state.session_id 
                            for s in sessions.get('sessions', [])
                        )
                        
                        health_status['session_status'] = 'active' if session_found else 'missing'
                    else:
                        health_status['session_status'] = 'error'
                        
                except Exception as e:
                    health_status['session_status'] = f'check_failed: {e}'
            
            # Calculate error rate
            if self.state.iteration_count > 0:
                health_status['error_rate'] = self.state.error_count / self.state.iteration_count
            
            # Determine overall status
            if health_status['error_rate'] > 0.5:
                health_status['status'] = 'degraded'
            elif health_status['session_status'] == 'missing':
                health_status['status'] = 'warning'
            
            self.state.last_health_check = datetime.now()
            
        except Exception as e:
            health_status['status'] = 'error'
            health_status['error'] = str(e)
        
        return health_status
    
    def cleanup_session(self, session_id: str):
        """Clean up terminal session."""
        try:
            logger.info(f"Cleaning up session {session_id}")
            
            result = subprocess.run([
                'python3', 'multi_process_workflow.py', 'terminate', session_id
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Session {session_id} cleaned up successfully")
            else:
                logger.warning(f"Session cleanup warning: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
    
    def run_cognitive_loop(self, task_description: str, command: str = "bash"):
        """Run the main cognitive loop for a specific task."""
        logger.info(f"Starting cognitive loop for task: {task_description}")
        
        self.state.reset()
        self.state.current_task = task_description
        
        try:
            # Create session
            session_id = self.create_session(command)
            
            # Wait for session initialization
            time.sleep(2.0)
            
            # Main cognitive loop
            for iteration in range(self.config.max_iterations):
                self.state.iteration_count = iteration + 1
                
                try:
                    logger.info(f"=== Iteration {iteration + 1} ===")
                    
                    # Observe
                    observation = self.observe_session(session_id)
                    
                    # Think (decide)
                    decision = self.decide_action(observation)
                    logger.info(f"Decision: {decision['action']} - {decision.get('reason', 'No reason')}")
                    
                    # Act
                    if decision['action'] == 'complete':
                        logger.info("Task completed successfully!")
                        break
                    
                    action_result = self.execute_action(session_id, decision)
                    
                    # Brief pause between iterations
                    time.sleep(1.0)
                    
                    # Periodic health check
                    if iteration % 10 == 0:
                        health = self.health_check()
                        logger.info(f"Health check: {health['status']}")
                    
                except Exception as e:
                    self.state.error_count += 1
                    logger.error(f"Iteration {iteration + 1} failed: {e}")
                    
                    # Error recovery
                    if self.state.error_count > 5:
                        logger.error("Too many errors, aborting task")
                        break
                    
                    time.sleep(self.config.retry_delay)
            
            else:
                logger.warning(f"Task reached maximum iterations ({self.config.max_iterations})")
            
        except Exception as e:
            logger.error(f"Cognitive loop failed: {e}")
            raise
        
        finally:
            # Cleanup
            if self.state.session_id:
                self.cleanup_session(self.state.session_id)
            
            # Final health check and summary
            final_health = self.health_check()
            logger.info(f"Task completed. Final status: {final_health}")

def main():
    """Main entry point for production agent."""
    parser = argparse.ArgumentParser(description='Production Multi-Process AI Agent')
    parser.add_argument('--config', default='agent_config.json', help='Configuration file path')
    parser.add_argument('--task', default='System exploration and basic commands', help='Task description')
    parser.add_argument('--command', default='bash', help='Initial command to run')
    parser.add_argument('--agent-id', help='Agent identifier (overrides config)')
    
    args = parser.parse_args()
    
    # Load or create configuration
    config_path = Path(args.config)
    if config_path.exists():
        config = AgentConfig.from_file(str(config_path))
        logger.info(f"Loaded configuration from {config_path}")
    else:
        config = AgentConfig(
            agent_id=args.agent_id or f"agent_{int(time.time())}",
            max_iterations=50,
            iteration_timeout=30.0
        )
        config.to_file(str(config_path))
        logger.info(f"Created default configuration at {config_path}")
    
    # Override agent ID if provided
    if args.agent_id:
        config.agent_id = args.agent_id
    
    # Create and run agent
    agent = ProductionAgent(config)
    
    try:
        agent.run_cognitive_loop(args.task, args.command)
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

