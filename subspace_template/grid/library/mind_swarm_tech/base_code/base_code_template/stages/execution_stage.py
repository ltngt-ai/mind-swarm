"""Execution Stage V3 - Python script execution with elegant memory API.

This stage generates and executes Python scripts using the new memory-centric API
where everything is accessed as memory through a unified interface.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
import json
import traceback
import yaml  # Still needed for reading the file

if TYPE_CHECKING:
    from ..cognitive_loop import CognitiveLoop
from ..memory import Priority, ContentType, ObservationMemoryBlock
from ..memory.tag_filter import TagFilter

logger = logging.getLogger("Cyber.stages.execution_v3")


class ExecutionStage:
    """Execution stage using the new memory-centric API.
    
    Key features:
    - Unified memory interface for all operations
    - Dictionary and attribute access to memories
    - Transaction support with rollback
    - Everything is memory - files, messages, goals
    - Auto-generates API documentation as knowledge
    """
    
    # Knowledge tags to exclude during execution
    KNOWLEDGE_BLACKLIST = {
        "observation",
        "decision_only", 
        "reflection_only",
        "background",
        "philosophy",
        "raw_perception"
    }
    
    def __init__(self, cognitive_loop: 'CognitiveLoop'):
        """Initialize the execution stage."""
        self.cognitive_loop = cognitive_loop
        self.memory_system = cognitive_loop.memory_system
        self.brain_interface = cognitive_loop.brain_interface
        self.knowledge_manager = cognitive_loop.knowledge_manager
        self.execution_tracker = cognitive_loop.execution_tracker
        
        # Paths
        self.cyber_id = cognitive_loop.cyber_id
        self.cyber_type = getattr(cognitive_loop, 'cyber_type', 'general')
        self.personal = cognitive_loop.personal
        self.outbox_dir = cognitive_loop.outbox_dir
        self.memory_dir = cognitive_loop.memory_dir
        
        # Set up Python execution environment
        self._setup_execution_environment()
        
        # Generate API documentation as knowledge for all modules
        self._extract_and_save_module_docs(self.memory_api, "memory_api_docs")
        self._extract_and_save_module_docs(self.location_api, "location_api_docs")
        self._extract_and_save_module_docs(self.events, "events_api_docs")
        self._extract_and_save_module_docs(self.knowledge_api, "knowledge_api_docs")
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        stage_data = self.knowledge_manager.get_stage_instructions('execution')
        if stage_data:
            from ..memory.memory_blocks import FileMemoryBlock
            from ..memory.memory_types import Priority, ContentType
            
            import yaml
            
            # stage_data has: content (YAML string), metadata (DB metadata), id, source
            # Parse the YAML content to get the actual knowledge fields
            try:
                yaml_content = yaml.safe_load(stage_data['content'])
                # yaml_content now has: title, category, tags, content (the actual instructions)
            except Exception as e:
                logger.error(f"Failed to parse stage instructions YAML: {e}")
                return
            
            # Pass the parsed YAML content as metadata for validation
            stage_memory = FileMemoryBlock(
                location="/personal/.internal/knowledge_execution_stage",
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,
                metadata=yaml_content,  # This has title, category, tags, content fields
                pinned=False,
                cycle_count=self.cognitive_loop.cycle_count,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            self.memory_system.add_memory(stage_memory)
            self.stage_knowledge_id = stage_memory.id
            logger.debug("Loaded execution stage instructions into memory")
        else:
            self.stage_knowledge_id = None
    
    def _cleanup_stage_instructions(self):
        """Remove stage instructions from working memory."""
        if hasattr(self, 'stage_knowledge_id') and self.stage_knowledge_id:
            if self.memory_system.remove_memory(self.stage_knowledge_id):
                logger.debug("Removed execution stage instructions from memory")
            self.stage_knowledge_id = None
    
    def _extract_and_save_module_docs(self, module_instance, docs_name: str):
        """Extract API documentation from a module and save to knowledge."""
        import inspect
        import sys
        
        api_docs_path = self.personal / ".internal" / "knowledge" / f"{docs_name}.yaml"
        
        # Always regenerate docs to pick up any changes
        # (or check if source module is newer than docs file)
        regenerate = True  # For now, always regenerate to ensure latest docs
        
        if regenerate:
            logger.info(f"Generating {docs_name} documentation from Python module...")
            try:
                # Extract documentation from the module
                docs = []
                
                # Get the actual module (not the class instance)
                module_obj = sys.modules[module_instance.__class__.__module__]
                
                # Get module docstring (this has the important examples!)
                if module_obj.__doc__:
                    docs.append(f"# {module_instance.__class__.__name__} API Documentation")
                    docs.append("")
                    docs.append(module_obj.__doc__.strip())
                    docs.append("")
                
                # Extract all public methods and their docs from the instance
                docs.append("## Available Methods")
                docs.append("")
                
                for name in dir(module_instance):
                    if not name.startswith('_'):  # Public methods only
                        attr = getattr(module_instance, name)
                        if callable(attr) and hasattr(attr, '__doc__') and attr.__doc__:
                            # Get signature if possible
                            try:
                                sig = inspect.signature(attr)
                                docs.append(f"### {name}{sig}")
                            except:
                                docs.append(f"### {name}()")
                            
                            docs.append(attr.__doc__.strip())
                            docs.append("")
                
                docs_content = "\n".join(docs)
                
                # Create pure YAML format matching the schema
                api_docs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(api_docs_path, 'w') as f:
                    # Write pure YAML format with metadata and content sections
                    f.write("metadata:\n")
                    f.write(f"  title: {docs_name.replace('_', ' ').title()} - Auto-extracted Documentation\n")
                    f.write("  category: action_guide\n")  # Use allowed category
                    f.write("  tags:\n")
                    f.write("    - execution\n")
                    f.write("    - api\n")
                    f.write("    - reference\n")
                    f.write("    - execution_only\n")
                    f.write("    - python\n")
                    f.write(f"  source: {module_instance.__class__.__module__}\n")
                    f.write(f"  created: '{datetime.now().isoformat()}'\n")
                    f.write("  auto_generated: true\n")
                    f.write("\n")
                    f.write("content: |\n")
                    # Indent content properly for YAML pipe syntax
                    for line in docs_content.split('\n'):
                        f.write(f"  {line}\n")
                logger.info(f"Created {docs_name} documentation at {api_docs_path}")
            except Exception as e:
                logger.warning(f"Failed to generate API docs: {e}")
                return
        
        # Now load it into working memory like ROM does
        try:
            # Load the YAML file
            file_content = api_docs_path.read_text()
            api_data = yaml.safe_load(file_content)
            
            # Create FileMemoryBlock exactly like ROM loader does
            from ..memory import FileMemoryBlock
            
            metadata = api_data.get("metadata", {})
            content = api_data.get("content", "")
            
            # Add content to metadata for brain access (like ROM does)
            if not metadata:
                metadata = {}
            metadata["content"] = content
            metadata["is_api_docs"] = True
            
            api_memory = FileMemoryBlock(
                location=str(api_docs_path),  # Use the actual file path
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,  # High priority so it's always included
                metadata=metadata,
                pinned=True,  # Pin it so it's never removed
                cycle_count=0,
                content_type=ContentType.MINDSWARM_KNOWLEDGE
            )
            
            # Add it to the memory system
            self.memory_system.add_memory(api_memory)
            logger.info("Loaded Memory API documentation into working memory")
            
        except Exception as e:
            logger.warning(f"Failed to load API docs into memory: {e}")
    
    # Old hardcoded documentation methods removed - now using generic _extract_and_save_module_docs
    def _setup_execution_environment(self):
        """Set up the Python execution environment with new Memory API."""
        # Safe built-ins for script execution
        self.safe_builtins = {
            # Math and numbers
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sum': sum, 'pow': pow, 'divmod': divmod,
            'int': int, 'float': float, 'complex': complex,
            
            # Collections and iteration
            'len': len, 'range': range, 'enumerate': enumerate,
            'zip': zip, 'map': map, 'filter': filter,
            'sorted': sorted, 'reversed': reversed,
            'all': all, 'any': any,
            
            # Data structures
            'list': list, 'tuple': tuple, 'dict': dict, 'set': set,
            
            # String operations
            'str': str, 'repr': repr, 'format': format,
            
            # Type checking
            'type': type, 'isinstance': isinstance, 'hasattr': hasattr,
            'bool': bool,
            
            # Constants
            'True': True, 'False': False, 'None': None,
            
            # Safe exceptions for the memory API
            'Exception': Exception, 
            'ValueError': ValueError,
            'TypeError': TypeError, 
            'KeyError': KeyError,
            
            # Import capability
            '__import__': __import__,
        }
        
        # Import safe standard library modules
        import math
        import statistics
        import json as json_module
        import re
        import datetime as dt
        import itertools
        import functools
        import collections
        
        self.safe_modules = {
            'math': math,
            'statistics': statistics,
            'json': json_module,
            're': re,
            'datetime': dt,
            'itertools': itertools,
            'functools': functools,
            'collections': collections,
        }
        
        # Import and create API instances for documentation
        from ..python_modules.memory import Memory
        from ..python_modules.location import Location
        from ..python_modules.events import Events
        from ..python_modules.knowledge import Knowledge
        
        # Create context for the APIs
        context = {
            'cognitive_loop': self.cognitive_loop,
            'memory_system': self.memory_system,
            'brain_interface': self.brain_interface,
            'cyber_id': self.cyber_id,
            'personal_dir': self.personal,
            'outbox_dir': self.outbox_dir,
            'memory_dir': self.memory_dir,
            'current_location': '/personal'
        }
        
        # Create instances for documentation extraction
        self.memory_api = Memory(context)
        self.location_api = Location(context)
        self.events = Events(context)
        self.knowledge_api = Knowledge(self.memory_api)  # Knowledge uses Memory instance
    
    async def execute(self):
        """Run the execution stage."""
        logger.info("=== EXECUTION STAGE V3 ===")
        
        # Load stage instructions
        self._load_stage_instructions()
        
        # The decision is already in working memory - just generate and execute
        # The brain will see the decision buffer content in working memory context
        
        # Phase 1: Generate Python script from working memory context
        script = await self.generate_script()
        
        if not script:
            logger.info("⚡ No script generated - likely no intention to execute")
            self._cleanup_stage_instructions()
            return
        
        # Phase 2: Execute the generated script
        await self.execute_script(script)
        
        # Clean up stage instructions
        self._cleanup_stage_instructions()
        
    
    async def generate_script(self) -> Optional[str]:
        """Generate Python script from working memory context."""
        logger.info("📋 Generating Python script from working memory...")
        
        # Update phase
        self.cognitive_loop._update_dynamic_context(stage="EXECUTION", phase="GENERATE")
        
        # Create tag filter - allow execution-related knowledge
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Build full working memory context including decision buffer
        current_task = "Generate Python script based on the current decision/intention in working memory"
        
        # Build full working memory context, not just filtered execution knowledge
        # This ensures the execution stage can see everything other stages can see
        working_memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,  # Half tokens for working memory
            current_task=current_task,
            selection_strategy="balanced",  # Balanced selection like other stages
            tag_filter=tag_filter,
            exclude_content_types=[]  # Include all memory types
        )
        
        # Use brain to generate script with full working memory context
        script_response = await self._request_script_generation(working_memory_context)
        
        if script_response:
            script = script_response.get("output_values", {}).get("script", "")
            
            if script:
                script = self._clean_script(script)
                logger.info(f"📋 Generated {len(script.split(chr(10)))} lines of Python code")
                return script
        
        return None
    
    async def _request_script_generation(self, working_memory: str) -> Optional[Dict[str, Any]]:
        """Request script generation from brain with full working memory context."""
        thinking_request = {
            "signature": {
                "instruction": """
Generate Python code based on the current intentions to mutate the Mind-Swarm memory.
system:personal/.internal/memory/pipeline/current_decision_pipe_stage.json has the current intention.
If there's no clear intention, return an empty script.

The provided API docs describe the available operations and their usage.
""",
                "inputs": {
                    "working_memory": "Full working memory context including decision buffer with intention"
                },
                "outputs": {
                    "script": "Python script using Cyber API's (or empty if no intention)"
                },
                "display_field": "script"
            },
            "input_values": {
                "working_memory": working_memory
            },
            "request_id": f"generate_script_{int(datetime.now().timestamp()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.brain_interface._use_brain(json.dumps(thinking_request))
        return json.loads(response)
    
    def _clean_script(self, script: str) -> str:
        """Clean up generated script."""
        if not script:
            return script
            
        lines = script.split('\n')
        cleaned_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                if line.strip() == '```' or line.strip().startswith('```python'):
                    in_code_block = not in_code_block
                    continue
            else:
                cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines).strip()
        
        if not cleaned and '```' not in script:
            return script
            
        return cleaned
    
    async def execute_script(self, script: str) -> List[Dict[str, Any]]:
        """Execute the generated Python script with new memory API."""
        logger.info(f"⚡ Executing Python script ({len(script)} characters)...")
        
        # Update phase
        self.cognitive_loop._update_dynamic_context(stage="EXECUTION", phase="EXECUTE")
        
        max_attempts = 3
        current_script = script
        attempt = 0
        final_results = []
        
        while attempt < max_attempts and not final_results:
            attempt += 1
            logger.info(f"⚡ Execution attempt {attempt}/{max_attempts}")
            
            result = await self._run_script(current_script, attempt)
            
            if result["status"] == "completed":
                final_results = [result]
                break
            
            # If we have more attempts left, try to fix the error
            if attempt < max_attempts:
                logger.info(f"⚠️ Script error: {result['error_type']}, attempting fix...")
                fixed_script = await self._fix_script_error(current_script, result)
                
                if fixed_script and fixed_script != current_script:
                    current_script = fixed_script
                    logger.info("📝 Generated fixed script, retrying...")
                else:
                    logger.warning(f"❌ Could not fix {result['error_type']} error, attempt {attempt}/{max_attempts}")
            else:
                # No more attempts left
                final_results = [result]
        
        if not final_results:
            final_results = [{
                "status": "failed",
                "error": "Max retries exceeded without success",
                "attempts": attempt
            }]
        
        # Save execution results
        await self._save_execution_results(final_results, current_script)
        
        # Write to execution pipeline buffer
        execution_content = {
            "timestamp": datetime.now().isoformat(),
            "cycle_count": self.cognitive_loop.cycle_count,
            "script": current_script,
            "results": final_results,
            "success": final_results[0]["status"] == "completed" if final_results else False,
            "attempts": attempt
        }
        
        execution_buffer = self.cognitive_loop.get_current_pipeline("execution")
        buffer_file = self.cognitive_loop.personal.parent / execution_buffer.location
        
        with open(buffer_file, 'w') as f:
            json.dump(execution_content, f, indent=2)
        
        self.cognitive_loop.memory_system.touch_memory(execution_buffer.id, self.cognitive_loop.cycle_count)
        
        logger.info(f"⚡ Execution complete after {attempt} attempt(s)")
        
        return final_results
    
    async def _run_script(self, script: str, attempt: int) -> Dict[str, Any]:
        """Execute a Python script with the new memory API."""
        # Create execution context
        context = {
            'cognitive_loop': self.cognitive_loop,
            'memory_system': self.memory_system,
            'brain_interface': self.brain_interface,
            'cyber_id': self.cyber_id,
            'personal_dir': self.personal,
            'outbox_dir': self.outbox_dir,
            'memory_dir': self.memory_dir,
            'current_location': self.cognitive_loop.get_dynamic_context().get('current_location', '/personal')
        }
        
        # Set up execution namespace
        namespace = {
            '__builtins__': self.safe_builtins,
            '__name__': '__cyber_script__',
            '__doc__': 'Cyber execution script',
        }
        
        # Add safe modules
        namespace.update(self.safe_modules)
        
        # Import and initialize the new Memory API
        from ..python_modules.memory import Memory, MemoryError, MemoryNotFoundError, MemoryPermissionError
        
        # Create memory instance
        memory_instance = Memory(context)
        namespace['memory'] = memory_instance
        namespace['MemoryError'] = MemoryError
        namespace['MemoryNotFoundError'] = MemoryNotFoundError
        namespace['MemoryPermissionError'] = MemoryPermissionError
        
        # Import and initialize the Location API
        from ..python_modules.location import Location, LocationError
        
        # Create location instance
        location_instance = Location(context)
        namespace['location'] = location_instance
        namespace['LocationError'] = LocationError
        
        # Import and initialize the Events API
        from ..python_modules.events import Events, EventsError
        
        # Create events instance
        events_instance = Events(context)
        namespace['events'] = events_instance
        namespace['EventsError'] = EventsError
        
        # Capture output
        output_lines = []
        
        def capture_print(*args, **kwargs):
            output = ' '.join(str(arg) for arg in args)
            output_lines.append(output)
        
        namespace['print'] = capture_print
        
        # Execute the script
        start_time = datetime.now()
        
        try:
            # Start a transaction for automatic rollback on error
            with memory_instance.transaction():
                # Compile and execute
                compiled = compile(script, '<cyber_script>', 'exec')
                exec(compiled, namespace)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "status": "completed",
                "output": '\n'.join(output_lines) if output_lines else "Script executed successfully",
                "execution_time": f"{duration:.3f} seconds",
                "script_lines": len(script.strip().split('\n')),
                "attempt": attempt
            }
            
        except SyntaxError as e:
            error_msg = f"Syntax error: {e.msg} at line {e.lineno}"
            logger.error(f"Attempt {attempt}: {error_msg}")
            return {
                "status": "failed",
                "error": error_msg,
                "error_type": "SyntaxError",
                "line": e.lineno,
                "text": e.text,
                "attempt": attempt
            }
            
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Execution error: {type(e).__name__}: {str(e)}"
            
            # Try to extract line number from traceback
            line_num = None
            tb_lines = tb.split('\n')
            for line in tb_lines:
                if '<cyber_script>' in line and 'line' in line:
                    # Extract line number from traceback
                    import re
                    match = re.search(r'line (\d+)', line)
                    if match:
                        line_num = int(match.group(1))
                        break
            
            if line_num:
                error_msg += f" at line {line_num}"
            
            logger.error(f"Attempt {attempt}: {error_msg}\n{tb}")
            
            # Check if it's a memory-specific error
            error_type = type(e).__name__
            if 'Memory' in error_type:
                error_type = 'MemoryError'
            
            return {
                "status": "failed",
                "error": error_msg,
                "error_type": error_type,
                "line": line_num,
                "traceback": tb,
                "partial_output": output_lines,
                "attempt": attempt
            }
    
    async def _fix_script_error(self, script: str, error: Dict[str, Any]) -> Optional[str]:
        """Try to fix an error in the script by showing the full error context to the AI."""
        
        # Create tag filter - allow execution-related knowledge
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Get the SAME working memory view as the original script generation
        # This ensures the recovery stage sees exactly what the initial stage saw
        working_memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Fix Python script error based on error details",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_content_types=[]
        )
        
        # API documentation is already in working memory as pinned FileMemoryBlocks
        # No need to extract it again - it will be included in working_memory_context
        
        # Build full error context
        error_context = {
            "error_type": error.get("error_type", "Unknown"),
            "error_message": error.get("error", ""),
            "line_number": error.get("line"),
            "partial_output": error.get("partial_output", [])
        }
        
        # Include traceback if available (often has the real error details)
        if "traceback" in error:
            error_context["traceback"] = error["traceback"]
        
        instruction = """
The Python script failed with an error. Analyze the error and fix the script.

You have access to the SAME memory and location objects as before:
- memory: Provides filesystem access through attribute notation
- location: Provides navigation capabilities

The API documentation is in your working memory (look for Memory API and Location API docs).
The error details show exactly what went wrong.

CRITICAL: Output ONLY the corrected Python code - no markdown, no explanations, just Python.
Remember: NO async/await, all operations are synchronous.
"""
        
        fix_request = {
            "signature": {
                "instruction": instruction,
                "inputs": {
                    "script": "The script that failed",
                    "error_details": "Full error information including traceback",
                    "working_memory": "Complete memory context including API documentation",
                    "partial_output": "Any output before the error"
                },
                "outputs": {
                    "fixed_script": "The corrected Python script"
                }
            },
            "input_values": {
                "script": script,
                "error_details": json.dumps(error_context, indent=2),
                "working_memory": working_memory_context,
                "partial_output": "\n".join(error.get("partial_output", []))
            }
        }
        
        try:
            response = await self.brain_interface._use_brain(json.dumps(fix_request))
            result = json.loads(response)
            fixed = result.get("output_values", {}).get("fixed_script", "")
            
            if fixed:
                return self._clean_script(fixed)
        except Exception as e:
            logger.error(f"Failed to fix script error: {e}")
        
        return None
    
    async def _save_execution_results(self, results: List[Dict], script: str):
        """Save execution results as memory observations."""
        results_dir = Path("/personal/.internal/memory/action_results")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        filename = f"script_execution_{timestamp}.json"
        filepath = results_dir / filename
        
        result_data = {
            "observation_type": "script_execution",
            "timestamp": datetime.now().isoformat(),
            "script": script,
            "results": results,
            "cycle_count": self.cognitive_loop.cycle_count,
            "api_version": "v3_memory"
        }
        
        with open(filepath, 'w') as f:
            json.dump(result_data, f, indent=2, default=str)
        
        # Create observation
        success = results[0]["status"] == "completed" if results else False
        message = f"Script execution {'succeeded' if success else 'failed'}"
        
        observation = ObservationMemoryBlock(
            observation_type="script_execution",
            path=str(filepath),
            message=message,
            cycle_count=self.cognitive_loop.cycle_count,
            priority=Priority.HIGH if not success else Priority.MEDIUM
        )
        
        if self.memory_system:
            self.memory_system.add_memory(observation)