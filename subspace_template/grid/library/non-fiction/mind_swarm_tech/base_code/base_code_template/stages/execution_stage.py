"""Execution Stage - Python script execution with elegant memory API.

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
from ..memory import Priority, ContentType
from ..memory.tag_filter import TagFilter

logger = logging.getLogger("Cyber.stages.execution")


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
        self._extract_and_save_module_docs(self.environment_api, "environment_api_docs")
        self._extract_and_save_module_docs(self.cbr_api, "cbr_api_docs")
        self._extract_and_save_module_docs(self.communication_api, "communication_api_docs")
        self._extract_and_save_module_docs(self.tasks_api, "tasks_api_docs")
        self._extract_and_save_module_docs(self.terminal_api, "terminal_api_docs")
        
        # Initialize error case tracking
        self.error_case_ids = []  # Track current cycle's error cases for cleanup
    
    def _load_stage_instructions(self):
        """Load stage instructions from knowledge into memory."""
        stage_data = self.knowledge_manager.get_stage_instructions('execution')
        if stage_data:
            from ..memory.memory_blocks import MemoryBlock
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
            stage_memory = MemoryBlock(
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
            
            # Create MemoryBlock exactly like ROM loader does
            from ..memory import MemoryBlock
            
            metadata = api_data.get("metadata", {})
            content = api_data.get("content", "")
            
            # Add content to metadata for brain access (like ROM does)
            if not metadata:
                metadata = {}
            metadata["content"] = content
            metadata["is_api_docs"] = True
            
            api_memory = MemoryBlock(
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
            logger.info(f"Loaded {docs_name} documentation into working memory")
            
        except Exception as e:
            logger.warning(f"Failed to load API docs into memory: {e}")
    
    # Old hardcoded documentation methods removed - now using generic _extract_and_save_module_docs
    def _setup_execution_environment(self):
        """Set up the Python execution environment with APIs.
        
        IMPORTANT: When adding a new module:
        1. Import and initialize it here in _setup_execution_environment()
        2. Add documentation extraction in __init__ with _extract_and_save_module_docs()
        3. Both steps are required for the API to work and be documented for cybers
        """
        # Safe built-ins for script execution
        # Get builtins properly - it might be a dict or module depending on context
        import builtins
        # Create safe import wrapper
        def safe_import(name, *args, **kwargs):
            """Restricted __import__ that blocks dangerous modules."""
            # Block dangerous modules that could exit or harm the system
            blocked_modules = {
                'sys',  # Can call sys.exit()
                'os',   # Can call os._exit() and other dangerous operations
                'subprocess',  # Can spawn processes
                'multiprocessing',  # Can spawn processes
                'signal',  # Can send signals
                'atexit',  # Can register exit handlers
                '__main__',  # Could interfere with main process
                'builtins',  # Could bypass restrictions
                'importlib',  # Could bypass import restrictions
                'imp',  # Deprecated import machinery
                'code',  # Interactive interpreter
                'eval',  # Could bypass restrictions
                'exec',  # Could bypass restrictions
            }
            
            # Check if module or any parent module is blocked
            module_parts = name.split('.')
            for i in range(len(module_parts)):
                module_check = '.'.join(module_parts[:i+1])
                if module_check in blocked_modules:
                    logger.warning(f"🚫 BLOCKED dangerous import attempt: '{name}' (blocked module: {module_check})")
                    raise ImportError(f"Import of '{name}' is not allowed (blocked module: {module_check})")
            
            # Allow the import for safe modules
            return builtins.__import__(name, *args, **kwargs)
        
        self.safe_builtins = {
            # Python internals needed for class definitions
            '__build_class__': builtins.__build_class__,
            '__import__': safe_import,  # Use our safe wrapper
            
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
            'chr': chr, 'ord': ord, 'ascii': ascii,
            
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
            'FileNotFoundError': FileNotFoundError,
            'IOError': IOError,
            'OSError': OSError,
            
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
        from ..python_modules.environment import Environment
        from ..python_modules.cbr import CBR
        from ..python_modules.communication import Communication
        
        # Create context for the APIs
        context = {
            'cognitive_loop': self.cognitive_loop,
            'memory_system': self.memory_system,
            'brain_interface': self.brain_interface,
            'state_manager': self.cognitive_loop.state_manager,  # Add state manager
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
        self.environment_api = Environment(context)
        self.cbr_api = CBR(self.memory_api)  # CBR uses Memory instance
        self.communication_api = Communication(context)
        
        # Import and initialize Tasks API
        from ..python_modules.tasks import Tasks
        self.tasks_api = Tasks(context)
        
        # Import Terminal API
        from ..python_modules.terminal import Terminal
        self.terminal_api = Terminal(context)
    
    async def execute(self):
        """Run the execution stage."""
        logger.info("=== EXECUTION STAGE V3 ===")
        
        # Reset error case tracking for this cycle
        self.error_case_ids = []
        
        try:
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
            
        except Exception as e:
            # Catch ANY exception to prevent cyber crash
            logger.error(f"Execution stage failed with unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
            
            # Write a failure to the execution buffer so the cyber knows something went wrong
            try:
                execution_content = {
                    "timestamp": datetime.now().isoformat(),
                    "cycle_count": self.cognitive_loop.cycle_count,
                    "script": "Failed to execute",
                    "results": [{
                        "status": "failed",
                        "error": f"Execution stage crashed: {str(e)}",
                        "error_type": type(e).__name__
                    }],
                    "success": False,
                    "attempts": 0
                }
                
                execution_buffer = self.cognitive_loop.get_current_pipeline("execution")
                buffer_file = self.cognitive_loop.personal.parent / execution_buffer.location
                
                with open(buffer_file, 'w') as f:
                    json.dump(execution_content, f, indent=2)
                    
                self.cognitive_loop.memory_system.touch_memory(execution_buffer.id, self.cognitive_loop.cycle_count)
            except Exception as buffer_error:
                logger.error(f"Failed to write error to execution buffer: {buffer_error}")
        
        finally:
            # Always clean up stage instructions
            try:
                self._cleanup_stage_instructions()
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup stage instructions: {cleanup_error}")
        
    
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
                # Log a preview of the generated script
                formatted_preview = self._format_script_for_logging(script, max_lines=8)
                logger.debug(f"📋 Generated script:\n{formatted_preview}")
                return script
        
        return None
    
    async def _request_script_generation(self, working_memory: str) -> Optional[Dict[str, Any]]:
        """Request script generation from brain with full working memory context."""
        # Try to augment with concise knowledge based on the current intention
        try:
            # Read intention from decision buffer
            decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
            decision_file = self.cognitive_loop.personal.parent / decision_buffer.location
            intention_text = ""
            try:
                with open(decision_file, 'r') as f:
                    decision_data = json.load(f)
                    intention_text = str(decision_data.get("intention", ""))
            except Exception:
                intention_text = ""

            helpful_refs = self.cognitive_loop.knowledge_context.build(
                stage="execution",
                queries=[intention_text] if intention_text else [working_memory[:300]],
                limit=2,
                budget_chars=700,
                blacklist_tags=self.KNOWLEDGE_BLACKLIST,
            )
        except Exception:
            helpful_refs = ""
        thinking_request = {
            "signature": {
                "instruction": """
Generate Python code based on the current intentions to mutate the Mind-Swarm memory.
system:personal/.internal/memory/pipeline/current_decision_pipe_stage.json has the current intention.
If there's no clear intention, return an empty script.

The provided API docs describe the available operations and their usage.
""",
                "inputs": {
                    "working_memory": "Full working memory context including decision buffer with intention",
                    "helpful_references": "Concise relevant knowledge to guide script authoring (may be empty)"
                },
                "outputs": {
                    "script": "Python script using Cyber API's (or empty if no intention)"
                },
                "display_field": "script"
            },
            "input_values": {
                "working_memory": working_memory,
                "helpful_references": helpful_refs
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
    
    def _format_script_for_logging(self, script: str, max_lines: int = 10) -> str:
        """Format a script nicely for logging with proper indentation."""
        try:
            lines = script.split('\n')
            if len(lines) <= max_lines:
                # Show the entire script if it's short
                formatted = '\n'.join(f"    {line}" for line in lines)
            else:
                # Show first max_lines with truncation indicator
                preview_lines = lines[:max_lines]
                formatted = '\n'.join(f"    {line}" for line in preview_lines)
                formatted += f"\n    ... ({len(lines) - max_lines} more lines)"
            return formatted
        except Exception:
            return "    <unable to format script>"
    
    async def execute_script(self, script: str) -> List[Dict[str, Any]]:
        """Execute the generated Python script with new memory API."""
        try:
            logger.info(f"⚡ Executing Python script ({len(script)} characters, {len(script.split(chr(10)))} lines)")
            # Log formatted script preview
            formatted_script = self._format_script_for_logging(script)
            logger.info(f"📝 Script preview:\n{formatted_script}")
        except Exception:
            # Even logging the script failed
            logger.info("⚡ Executing Python script...")
        
        # Update phase
        try:
            self.cognitive_loop._update_dynamic_context(stage="EXECUTION", phase="EXECUTE")
        except Exception as e:
            logger.warning(f"Failed to update dynamic context: {e}")
        
        max_attempts = 3
        current_script = script
        attempt = 0
        final_results = []
        
        try:
            while attempt < max_attempts and not final_results:
                attempt += 1
                logger.info(f"⚡ Execution attempt {attempt}/{max_attempts}")
                
                try:
                    result = await self._run_script(current_script, attempt)
                except Exception as run_error:
                    logger.error(f"Script execution crashed: {run_error}", exc_info=True)
                    result = {
                        "status": "failed",
                        "error": f"Script execution crashed: {str(run_error)}",
                        "error_type": "CrashError",
                        "attempt": attempt
                    }
                
                if result["status"] == "completed":
                    final_results = [result]
                    break
                
                # If we have more attempts left, try to fix the error
                if attempt < max_attempts:
                    try:
                        logger.info(f"⚠️ Script error: {result.get('error_type', 'Unknown')}, attempting fix...")
                        
                        # First try to find similar past errors and their solutions
                        similar_solutions = await self._search_similar_error_cases(result, current_script)
                        
                        fixed_script = await self._fix_script_error(current_script, result, similar_solutions)
                        
                        if fixed_script and fixed_script != current_script:
                            # Store this as a potential solution (will be confirmed later)
                            case_id = await self._store_error_case(
                                script=current_script,
                                error=result,
                                solution=fixed_script,
                                status="pending"  # Will update to success/fail later
                            )
                            if case_id:
                                self.error_case_ids.append(case_id)
                            
                            current_script = fixed_script
                            # Log formatted fixed script for debugging
                            formatted_fixed = self._format_script_for_logging(fixed_script, max_lines=8)
                            logger.info(f"📝 Generated fixed script, retrying...\n{formatted_fixed}")
                        else:
                            logger.warning(f"❌ Could not fix {result.get('error_type', 'Unknown')} error, attempt {attempt}/{max_attempts}")
                    except Exception as fix_error:
                        logger.error(f"Failed to fix script error: {fix_error}")
                        # Continue with next attempt anyway
                else:
                    # No more attempts left
                    final_results = [result]
            
            if not final_results:
                final_results = [{
                    "status": "failed",
                    "error": "Max retries exceeded without success",
                    "attempts": attempt
                }]
        
        except Exception as loop_error:
            logger.error(f"Execution loop crashed: {loop_error}", exc_info=True)
            final_results = [{
                "status": "failed",
                "error": f"Execution loop crashed: {str(loop_error)}",
                "error_type": "LoopCrashError",
                "attempts": attempt
            }]
        
        # Try to write to execution pipeline buffer
        try:
            # Note: We don't need separate script_execution memory files anymore
            # The pipeline buffer contains all the execution information
            execution_content = {
                "timestamp": datetime.now().isoformat(),
                "cycle_count": self.cognitive_loop.cycle_count,
                "script": current_script if 'current_script' in locals() else script,
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
            
            # Update CBR case scores based on final outcome
            if self.error_case_ids:
                await self._update_error_case_scores(
                    case_ids=self.error_case_ids,
                    success=execution_content["success"]
                )

            # On successful execution, store a concise result as personal knowledge
            try:
                if execution_content.get("success"):
                    # Read intention from decision buffer
                    decision_buffer = self.cognitive_loop.get_current_pipeline("decision")
                    decision_file = self.cognitive_loop.personal.parent / decision_buffer.location
                    intention_text = ""
                    try:
                        with open(decision_file, 'r') as f:
                            decision_data = json.load(f)
                            intention_text = str(decision_data.get("intention", "")).strip()
                    except Exception:
                        intention_text = ""

                    # Summarize outcome
                    result_summary = execution_content["results"][0] if execution_content.get("results") else {}
                    status = result_summary.get("status", "completed")
                    output_excerpt = result_summary.get("output", "")
                    if isinstance(output_excerpt, str):
                        output_excerpt = output_excerpt[:300]
                    else:
                        output_excerpt = str(output_excerpt)[:300]

                    note = "Execution succeeded."
                    if intention_text:
                        note += f" Intention: {intention_text}"
                    if output_excerpt:
                        note += f"\nOutput: {output_excerpt}"

                    # Store as personal knowledge (small, concise)
                    _ = self.cognitive_loop.knowledge_manager.store_knowledge(
                        content=note,
                        metadata={
                            "personal": True,
                            "category": "execution_result",
                            "tags": ["execution", "result", "autolog"],
                            "confidence": 0.8,
                        },
                    )
            except Exception as e:
                logger.debug(f"Failed to store execution result knowledge: {e}")
            
            # Record stage data for cycle history
            try:
                # Get current working memory snapshot
                working_memory_snapshot = self.memory_system.create_snapshot()
                
                # Record the stage completion
                self.cognitive_loop.cycle_recorder.record_stage(
                    stage_name="execution",
                    working_memory=working_memory_snapshot,
                    llm_input=None,  # Could capture script generation request if needed
                    llm_output=None,  # Could capture script generation response if needed
                    stage_output=execution_content,
                    token_usage={}  # Could track if brain was used for fixes
                )
            except Exception as e:
                logger.debug(f"Failed to record execution stage: {e}")
        
        except Exception as buffer_error:
            logger.error(f"Failed to write execution results to buffer: {buffer_error}")
        
        return final_results
    
    async def _run_script(self, script: str, attempt: int) -> Dict[str, Any]:
        """Execute a Python script with the new memory API."""
        # Create execution context
        context = {
            'cognitive_loop': self.cognitive_loop,
            'memory_system': self.memory_system,
            'brain_interface': self.brain_interface,
            'state_manager': self.cognitive_loop.state_manager,  # Add state manager
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
        
        # Import and initialize the Knowledge API
        from ..python_modules.knowledge import Knowledge
        
        # Create knowledge instance (uses Memory instance)
        knowledge_instance = Knowledge(memory_instance)
        namespace['knowledge'] = knowledge_instance
        
        # Import and initialize the Environment API
        from ..python_modules.environment import Environment, EnvironmentError, EnvironmentTimeoutError
        
        # Create environment instance
        environment_instance = Environment(context)
        namespace['environment'] = environment_instance
        namespace['EnvironmentError'] = EnvironmentError
        namespace['EnvironmentTimeoutError'] = EnvironmentTimeoutError
        
        # Import and initialize the CBR API
        from ..python_modules.cbr import CBR, CBRError
        
        # Create CBR instance (uses Memory instance)
        cbr_instance = CBR(memory_instance)
        namespace['cbr'] = cbr_instance
        namespace['CBRError'] = CBRError
        
        # Import and initialize the Communication API
        from ..python_modules.communication import Communication, CommunicationError
        
        # Create communication instance
        communication_instance = Communication(context)
        namespace['communication'] = communication_instance
        namespace['CommunicationError'] = CommunicationError
        
        # Import and initialize the Tasks API
        from ..python_modules.tasks import Tasks, TasksError
        
        # Create tasks instance
        tasks_instance = Tasks(context)
        namespace['tasks'] = tasks_instance
        namespace['TasksError'] = TasksError
        
        # Import and initialize the Terminal API
        from ..python_modules.terminal import Terminal, TerminalError
        
        # Create terminal instance
        terminal_instance = Terminal(context)
        namespace['terminal'] = terminal_instance
        namespace['TerminalError'] = TerminalError
        
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
            # Safely handle ALL exceptions, even nested ones
            try:
                tb = traceback.format_exc()
            except Exception as tb_error:
                # Even traceback formatting failed - create a minimal error report
                logger.error(f"Failed to format traceback: {tb_error}")
                tb = f"Error formatting traceback: {tb_error}\nOriginal error: {type(e).__name__}: {str(e)}"
            
            try:
                error_msg = f"Execution error: {type(e).__name__}: {str(e)}"
            except Exception:
                # Even getting the error message failed
                error_msg = "Execution error: Unknown error (failed to get details)"
            
            # Safely try to extract line number from traceback
            line_num = None
            try:
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
            except Exception as parse_error:
                logger.warning(f"Could not parse line number from traceback: {parse_error}")
            
            # Safely log the error
            try:
                logger.error(f"Attempt {attempt}: {error_msg}\n{tb}")
            except Exception:
                logger.error(f"Attempt {attempt}: Error logging failed")
            
            # Safely determine error type
            try:
                error_type = type(e).__name__
                if 'Memory' in error_type:
                    error_type = 'MemoryError'
            except Exception:
                error_type = 'UnknownError'
            
            # Safely get partial output
            try:
                partial_output = output_lines[:20] if output_lines else []
            except Exception:
                partial_output = []
            
            return {
                "status": "failed",
                "error": error_msg,
                "error_type": error_type,
                "line": line_num,
                "traceback": tb,
                "partial_output": partial_output,
                "attempt": attempt
            }
    
    async def _fix_script_error(self, script: str, error: Dict[str, Any], similar_solutions: List[Dict[str, Any]] = None) -> Optional[str]:
        """Try to fix an error in the script using similar past solutions and AI analysis."""
        
        # Create tag filter - allow execution-related knowledge
        tag_filter = TagFilter(blacklist=self.KNOWLEDGE_BLACKLIST)
        
        # Get the SAME working memory view as the original script generation
        # This ensures the recovery stage sees exactly what the initial stage saw
        working_memory_context = self.memory_system.build_context(
            max_tokens=self.cognitive_loop.max_context_tokens // 2,
            current_task="Fix Python script error based on error details and past solutions",
            selection_strategy="balanced",
            tag_filter=tag_filter,
            exclude_content_types=[]
        )
        
        # API documentation is already in working memory as pinned MemoryBlocks
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
        
        # Format similar solutions if available
        similar_solutions_text = ""
        if similar_solutions:
            similar_solutions_text = "\n\nSIMILAR PAST ERRORS AND SOLUTIONS:\n"
            for i, case in enumerate(similar_solutions[:3], 1):  # Limit to top 3
                similar_solutions_text += f"\n{i}. Similar Error (Score: {case.get('metadata', {}).get('success_score', 0):.2f}):\n"
                similar_solutions_text += f"   Problem: {case.get('problem_context', 'N/A')}\n"
                similar_solutions_text += f"   Solution: {case.get('solution', 'N/A')}\n"
                similar_solutions_text += f"   Outcome: {case.get('outcome', 'N/A')}\n"
        
        instruction = f"""
The Python script failed with an error. Analyze the error and fix the script.

The API documentation is in your working memory.
The error details show exactly what went wrong.
{similar_solutions_text}

CRITICAL: Output ONLY the corrected Python code - no markdown, no explanations, just Python.
Remember: NO async/await, all operations are synchronous.
If similar past solutions exist, consider adapting them to the current context.
"""
        
        fix_request = {
            "signature": {
                "instruction": instruction,
                "inputs": {
                    "script": "The script that failed",
                    "error_details": "Full error information including traceback",
                    "working_memory": "Complete memory context including API documentation",
                    "partial_output": "Any output before the error",
                    "similar_solutions": "Past solutions to similar errors (if any)"
                },
                "outputs": {
                    "fixed_script": "The corrected Python script"
                }
            },
            "input_values": {
                "script": script,
                "error_details": json.dumps(error_context, indent=2),
                "working_memory": working_memory_context,
                "partial_output": "\n".join(error.get("partial_output", [])),
                "similar_solutions": similar_solutions_text if similar_solutions else "No similar solutions found"
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
    
    async def _search_similar_error_cases(self, error: Dict[str, Any], script: str) -> List[Dict[str, Any]]:
        """Search for similar past errors and their solutions using CBR."""
        try:
            # Build a context string that describes the error
            error_context = f"Error type: {error.get('error_type', 'Unknown')}\n"
            error_context += f"Error message: {error.get('error', '')}\n"
            
            # Include relevant parts of traceback if available
            if "traceback" in error:
                # Extract the most relevant line from traceback
                tb_lines = error["traceback"].split('\n')
                for line in tb_lines:
                    if 'File "<cyber_script>"' in line or error.get("error", "") in line:
                        error_context += f"Traceback: {line}\n"
                        break
            
            # Add script context (first few lines to understand what was being attempted)
            script_lines = script.split('\n')[:5]
            error_context += f"Script context: {' '.join(script_lines)}"
            
            # Search for similar cases
            similar_cases = self.cbr_api.retrieve_similar_cases(
                context=error_context,
                limit=5,
                min_score=0.3,  # Lower threshold to catch more potential matches
                timeout=3.0  # Quick timeout to not delay execution
            )
            
            if similar_cases:
                logger.info(f"🔍 Found {len(similar_cases)} similar error cases from CBR")
                for case in similar_cases[:2]:  # Log top 2 for debugging
                    logger.debug(f"  - Similar case (score {case.get('similarity', 0):.2f}): {case.get('problem_context', '')[:100]}")
            
            return similar_cases
            
        except Exception as e:
            logger.warning(f"Failed to search CBR for similar errors: {e}")
            return []
    
    async def _store_error_case(self, script: str, error: Dict[str, Any], solution: str, status: str = "pending") -> Optional[str]:
        """Store an error and its solution as a CBR case."""
        try:
            # Build problem description
            problem = f"Script execution failed with {error.get('error_type', 'Unknown')} error: {error.get('error', '')[:200]}"
            
            # Build solution description
            solution_desc = f"Fixed script by modifying the code (see solution field for details)"
            
            # Extract key differences if possible (simplified)
            script_lines = script.split('\n')
            solution_lines = solution.split('\n')
            if len(script_lines) != len(solution_lines):
                solution_desc += f" - Changed from {len(script_lines)} to {len(solution_lines)} lines"
            
            # Prepare metadata
            tags = [
                f"error_{error.get('error_type', 'Unknown').lower()}",
                "execution_fix",
                f"attempt_{error.get('attempt', 1)}"
            ]
            
            # Store the case
            case_id = self.cbr_api.store_case(
                problem=problem,
                solution=solution_desc,
                outcome=f"Status: {status}",
                success_score=0.5,  # Initial neutral score, will be updated
                tags=tags,
                metadata={
                    "original_script": script[:500],  # Store first 500 chars
                    "fixed_script": solution[:500],
                    "error_details": {
                        "type": error.get("error_type"),
                        "message": error.get("error", "")[:200],
                        "line": error.get("line")
                    },
                    "cycle_count": self.cognitive_loop.cycle_count
                },
                timeout=3.0
            )
            
            if case_id:
                logger.debug(f"📝 Stored error case: {case_id}")
            
            return case_id
            
        except Exception as e:
            logger.warning(f"Failed to store error case in CBR: {e}")
            return None
    
    async def _update_error_case_scores(self, case_ids: List[str], success: bool):
        """Update the scores of error cases based on final execution outcome."""
        try:
            for case_id in case_ids:
                # Update score based on success
                new_score = 0.85 if success else 0.15
                
                success_text = "successfully" if success else "unsuccessfully"
                logger.debug(f"📊 Updating case {case_id} score to {new_score:.2f} ({success_text} resolved error)")
                
                # Update the case
                updated = self.cbr_api.update_case_score(
                    case_id=case_id,
                    new_score=new_score,
                    reused=True,  # Mark as used
                    timeout=2.0
                )
                
                if not updated:
                    logger.warning(f"Failed to update score for case {case_id}")
                    
        except Exception as e:
            logger.warning(f"Failed to update error case scores: {e}")
    
