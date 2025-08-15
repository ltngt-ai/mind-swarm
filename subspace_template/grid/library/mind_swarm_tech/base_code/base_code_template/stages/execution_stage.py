"""Execution Stage V3 - Python script execution with elegant memory API.

This stage generates and executes Python scripts using the new memory-centric API
where everything is accessed as memory through a unified interface.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json
import traceback
import yaml  # Still needed for reading the file

from ..memory import Priority, ObservationMemoryBlock
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
    
    def __init__(self, cognitive_loop):
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
        
        # Generate API documentation as knowledge (once)
        self._ensure_api_docs_knowledge()
        self._ensure_location_api_docs_knowledge()
        self._ensure_events_api_docs_knowledge()
    
    def _ensure_api_docs_knowledge(self):
        """Ensure API documentation is in working memory."""
        api_docs_path = self.personal / ".internal" / "knowledge" / "memory_api_docs.yaml"
        
        # First, create the file if it doesn't exist
        if not api_docs_path.exists():
            logger.info("Generating Memory API documentation from Python module...")
            try:
                # Extract documentation from the actual memory module
                docs = self._extract_api_documentation()
                
                # Create clean YAML with pipe syntax for content
                api_docs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(api_docs_path, 'w') as f:
                    # Write YAML manually for clean formatting
                    f.write("knowledge_version: '1.0'\n")
                    f.write("title: Memory API v3 - Python Module Documentation\n")
                    f.write("content: |\n")
                    # Indent content properly for YAML pipe syntax
                    for line in docs.split('\n'):
                        f.write(f"  {line}\n")
                    f.write("metadata:\n")
                    f.write("  category: execution\n")
                    f.write("  tags:\n")
                    f.write("    - execution\n")
                    f.write("    - memory\n")
                    f.write("    - api\n")
                    f.write("    - reference\n")
                    f.write("    - execution_only\n")
                    f.write("    - python\n")
                    f.write("  confidence: 1.0\n")
                    f.write("  priority: 1\n")
                    f.write("  source: memory.py\n")
                    f.write(f"  created: '{datetime.now().isoformat()}'\n")
                    f.write("  auto_generated: true\n")
                logger.info(f"Created Memory API documentation at {api_docs_path}")
            except Exception as e:
                logger.warning(f"Failed to generate API docs: {e}")
                return
        
        # Now load it into working memory like ROM does
        try:
            # Load the YAML file
            file_content = api_docs_path.read_text()
            api_data = yaml.safe_load(file_content)
            
            # Create FileMemoryBlock exactly like ROM loader does
            from ..memory import FileMemoryBlock, MemoryType
            
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
                block_type=MemoryType.KNOWLEDGE
            )
            
            # Add it to the memory system
            self.memory_system.add_memory(api_memory)
            logger.info("Loaded Memory API documentation into working memory")
            
        except Exception as e:
            logger.warning(f"Failed to load API docs into memory: {e}")
    
    def _extract_api_documentation(self) -> str:
        """Extract documentation from the memory module using AST."""
        import ast
        import inspect
        from ..python_modules import memory
        
        # Get the source file path
        source_file = inspect.getsourcefile(memory)
        if not source_file:
            return "Failed to locate memory source file"
        
        # Read and parse the source
        with open(source_file, 'r') as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        
        docs = []
        docs.append("# Memory API v3 - Extracted from Python Module")
        docs.append("")
        
        # Get module docstring
        module_doc = ast.get_docstring(tree)
        if module_doc:
            docs.append("## Module Overview")
            docs.append(module_doc)
            docs.append("")
        
        # Process all classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get class docstring
                class_doc = ast.get_docstring(node)
                if class_doc:
                    docs.append(f"## {node.name} Class")
                    docs.append(class_doc)
                    docs.append("")
                    
                    # Get methods
                    docs.append(f"### {node.name} Methods\n")
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                            method_doc = ast.get_docstring(item)
                            
                            # Build signature
                            args = []
                            for arg in item.args.args:
                                if arg.arg != 'self':
                                    args.append(arg.arg)
                            signature = f"({', '.join(args)})"
                            
                            docs.append(f"#### {item.name}{signature}")
                            if method_doc:
                                docs.append(method_doc)
                            docs.append("")
            
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                # Module-level function
                func_doc = ast.get_docstring(node)
                if func_doc and not node.name.startswith('_'):
                    args = []
                    for arg in node.args.args:
                        args.append(arg.arg)
                    signature = f"({', '.join(args)})"
                    
                    docs.append(f"## {node.name}{signature}")
                    docs.append(func_doc)
                    docs.append("")
        
        # Add practical usage examples from actual usage patterns
        docs.append("## Common Usage Patterns\n")
        docs.append("```python")
        docs.append("# The memory object is pre-initialized for you")
        docs.append("")
        docs.append("# READING FILES")
        docs.append("# Text files:")
        docs.append("content = memory.personal.notes.txt.content")
        docs.append("content = memory['/personal/notes.txt'].content")
        docs.append("")
        docs.append("# JSON files (automatically parsed):")
        docs.append("data = memory.personal.config.json.content")
        docs.append("value = memory.personal.config.json['key']  # Direct access to JSON fields")
        docs.append("")
        docs.append("# WRITING FILES")
        docs.append('memory.personal.output = "Result"')
        docs.append('memory["/personal/log.txt"] = "Log entry"')
        docs.append("")
        docs.append("# JSON data:")
        docs.append("memory.personal.data.json = {'key': 'value', 'count': 42}")
        docs.append("memory.personal.data.json['count'] = 43  # Update JSON field")
        docs.append("")
        docs.append("# CREATE DIRECTORIES")
        docs.append('memory.make_memory_group("/personal/project")')
        docs.append("")
        docs.append("# SEND MESSAGES")
        docs.append('memory.outbox.new(to="user", content="Done!", msg_type="CONFIRMATION")')
        docs.append("")
        docs.append("# TRANSACTIONS")
        docs.append("with memory.transaction():")
        docs.append('    memory.personal.critical = "data"')
        docs.append('    memory.personal.backup = memory.personal.critical.content')
        docs.append("")
        docs.append("# ERROR HANDLING")
        docs.append("try:")
        docs.append("    content = memory.personal.missing.content")
        docs.append("except MemoryNotFoundError:")
        docs.append('    memory.personal.missing = "default"')
        docs.append("```")
        
        return "\n".join(docs)
    
    def _ensure_location_api_docs_knowledge(self):
        """Ensure Location API documentation is in working memory."""
        api_docs_path = self.personal / ".internal" / "knowledge" / "location_api_docs.yaml"
        
        # First, create the file if it doesn't exist
        if not api_docs_path.exists():
            logger.info("Generating Location API documentation from Python module...")
            try:
                # Extract documentation from the actual location module
                docs = self._extract_location_api_documentation()
                
                # Create clean YAML with pipe syntax for content
                api_docs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(api_docs_path, 'w') as f:
                    # Write YAML manually for clean formatting
                    f.write("knowledge_version: '1.0'\n")
                    f.write("title: Location API - Python Module Documentation\n")
                    f.write("content: |\n")
                    # Indent content properly for YAML pipe syntax
                    for line in docs.split('\n'):
                        f.write(f"  {line}\n")
                    f.write("metadata:\n")
                    f.write("  category: execution\n")
                    f.write("  tags:\n")
                    f.write("    - execution\n")
                    f.write("    - location\n")
                    f.write("    - navigation\n")
                    f.write("    - api\n")
                    f.write("    - reference\n")
                    f.write("    - execution_only\n")
                    f.write("    - python\n")
                    f.write("  confidence: 1.0\n")
                    f.write("  priority: 1\n")
                    f.write("  source: location.py\n")
                    f.write(f"  created: '{datetime.now().isoformat()}'\n")
                    f.write("  auto_generated: true\n")
                logger.info(f"Created Location API documentation at {api_docs_path}")
            except Exception as e:
                logger.warning(f"Failed to generate Location API docs: {e}")
                return
        
        # Now load it into working memory like ROM does
        try:
            # Load the YAML file
            file_content = api_docs_path.read_text()
            api_data = yaml.safe_load(file_content)
            
            # Create FileMemoryBlock exactly like ROM loader does
            from ..memory import FileMemoryBlock, MemoryType
            
            metadata = api_data.get("metadata", {})
            content = api_data.get("content", "")
            
            # Add content to metadata for brain access (like ROM does)
            if not metadata:
                metadata = {}
            metadata["content"] = content
            metadata["is_location_api_docs"] = True
            
            api_memory = FileMemoryBlock(
                location=str(api_docs_path),  # Use the actual file path
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,  # High priority so it's always included
                metadata=metadata,
                pinned=True,  # Pin it so it's never removed
                cycle_count=0,
                block_type=MemoryType.KNOWLEDGE
            )
            
            # Add it to the memory system
            self.memory_system.add_memory(api_memory)
            logger.info("Loaded Location API documentation into working memory")
            
        except Exception as e:
            logger.warning(f"Failed to load Location API docs into memory: {e}")
    
    def _extract_location_api_documentation(self) -> str:
        """Extract documentation from the location module using AST."""
        import ast
        import inspect
        from ..python_modules import location
        
        # Get the source file path
        source_file = inspect.getsourcefile(location)
        if not source_file:
            return "Failed to locate location source file"
        
        # Read and parse the source
        with open(source_file, 'r') as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        
        docs = []
        docs.append("# Location API - Extracted from Python Module")
        docs.append("")
        
        # Get module docstring
        module_doc = ast.get_docstring(tree)
        if module_doc:
            docs.append("## Module Overview")
            docs.append(module_doc)
            docs.append("")
        
        # Process all classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get class docstring
                class_doc = ast.get_docstring(node)
                if class_doc:
                    docs.append(f"## {node.name} Class")
                    docs.append(class_doc)
                    docs.append("")
                    
                    # Get methods
                    docs.append(f"### {node.name} Methods\n")
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                            method_doc = ast.get_docstring(item)
                            
                            # Build signature
                            args = []
                            for arg in item.args.args:
                                if arg.arg != 'self':
                                    args.append(arg.arg)
                            signature = f"({', '.join(args)})"
                            
                            docs.append(f"#### {item.name}{signature}")
                            if method_doc:
                                docs.append(method_doc)
                            docs.append("")
        
        # Add practical usage examples
        docs.append("## Common Usage Patterns\n")
        docs.append("```python")
        docs.append("# The location object is pre-initialized for you")
        docs.append("")
        docs.append("# GET CURRENT LOCATION")
        docs.append("current = location.current")
        docs.append("print(f'Currently at: {current}')")
        docs.append("")
        docs.append("# CHANGE LOCATION")
        docs.append("location.current = '/grid/library/knowledge'")
        docs.append("# Or use the change method")
        docs.append("location.change('/personal/workspace')")
        docs.append("")
        docs.append("# CHECK IF LOCATION EXISTS")
        docs.append("if location.exists('/grid/workshop'):")
        docs.append("    location.current = '/grid/workshop'")
        docs.append("else:")
        docs.append("    print('Workshop does not exist')")
        docs.append("")
        docs.append("# ERROR HANDLING")
        docs.append("try:")
        docs.append("    location.current = '/invalid/path'")
        docs.append("except LocationError as e:")
        docs.append("    print(f'Invalid location: {e}')")
        docs.append("```")
        
        return "\n".join(docs)
    
    def _ensure_events_api_docs_knowledge(self):
        """Ensure Events API documentation is in working memory."""
        api_docs_path = self.personal / ".internal" / "knowledge" / "events_api_docs.yaml"
        
        # First, create the file if it doesn't exist
        if not api_docs_path.exists():
            logger.info("Generating Events API documentation from Python module...")
            try:
                # Generate documentation from the events module
                docs_content = self._generate_events_api_docs()
                
                # Create clean YAML with pipe syntax for content
                api_docs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(api_docs_path, 'w') as f:
                    # Write YAML manually for clean formatting
                    f.write("knowledge_version: '1.0'\n")
                    f.write("knowledge:\n")
                    f.write("  - id: events_api\n")
                    f.write("    type: api_documentation\n")
                    f.write("    name: Events API Documentation\n")
                    f.write("    tags:\n")
                    f.write("      - events\n")
                    f.write("      - api\n")
                    f.write("      - python\n")
                    f.write("      - sleep\n")
                    f.write("      - idle\n")
                    f.write("      - mail\n")
                    f.write("    content: |\n")
                    # Indent content for YAML
                    for line in docs_content.split('\n'):
                        f.write(f"      {line}\n")
                    f.write("metadata:\n")
                    f.write("  source: python_modules.events\n")
                    f.write(f"  created: '{datetime.now().isoformat()}'\n")
                    f.write("  auto_generated: true\n")
                logger.info(f"Created Events API documentation at {api_docs_path}")
            except Exception as e:
                logger.warning(f"Failed to generate Events API docs: {e}")
        
        # Now load it into working memory as a FileMemoryBlock
        if api_docs_path.exists():
            self._add_events_api_to_memory(api_docs_path)
    
    def _add_events_api_to_memory(self, api_docs_path: Path):
        """Add Events API documentation to working memory."""
        try:
            # Load the YAML file
            file_content = api_docs_path.read_text()
            api_data = yaml.safe_load(file_content)
            
            # Extract the content
            if api_data and 'knowledge' in api_data:
                knowledge_item = api_data['knowledge'][0]
                content = knowledge_item.get('content', '')
                metadata = knowledge_item.copy()
                metadata.pop('content', None)
            else:
                # Fallback to raw content
                content = file_content
                metadata = {}
            metadata["content"] = content
            metadata["is_events_api_docs"] = True
            
            api_memory = FileMemoryBlock(
                location=str(api_docs_path),  # Use the actual file path
                confidence=1.0,
                priority=Priority.FOUNDATIONAL,  # High priority so it's always included
                metadata=metadata
            )
            
            # Check if already in memory
            existing_api_docs = [
                m for m in self.cognitive_loop.memory_system.working_memory.memories
                if isinstance(m, FileMemoryBlock) and 
                m.metadata.get("is_events_api_docs", False)
            ]
            
            if not existing_api_docs:
                self.cognitive_loop.memory_system.working_memory.add_memory(api_memory)
                logger.debug("Added Events API documentation to working memory")
                
        except Exception as e:
            logger.warning(f"Failed to add Events API docs to memory: {e}")
    
    def _generate_events_api_docs(self) -> str:
        """Generate documentation from the events module."""
        docs = []
        docs.append("# Events API - Efficient Idle and Wake Functionality")
        docs.append("")
        docs.append("The Events API allows cybers to sleep efficiently and wake on events.")
        docs.append("")
        docs.append("## Key Features")
        docs.append("- Timer-based sleep with interruption support")
        docs.append("- Wake on new mail arrival")
        docs.append("- Combined sleep with mail monitoring")
        docs.append("- Automatic shutdown detection")
        docs.append("")
        docs.append("## Quick Examples")
        docs.append("")
        docs.append("```python")
        docs.append("# TIMER SLEEP")
        docs.append("# Sleep for 30 seconds")
        docs.append("result = events.sleep(30)")
        docs.append("if result == 'completed':")
        docs.append("    print('Slept for full duration')")
        docs.append("elif result == 'shutdown':")
        docs.append("    print('Shutdown requested')")
        docs.append("")
        docs.append("# WAIT FOR MAIL")
        docs.append("# Wait up to 60 seconds for new mail")
        docs.append("new_mail = events.wait_for_mail(60)")
        docs.append("if new_mail:")
        docs.append("    print(f'Got {len(new_mail)} new messages:')")
        docs.append("    for mail_file in new_mail:")
        docs.append("        print(f'  - {mail_file}')")
        docs.append("")
        docs.append("# COMBINED SLEEP AND MAIL CHECK")
        docs.append("# Sleep 30 seconds but wake if mail arrives")
        docs.append("new_mail = events.wait_for_mail(30)")
        docs.append("if new_mail:")
        docs.append("    print(f'New mail arrived: {new_mail}')")
        docs.append("else:")
        docs.append("    print('No mail in 30 seconds')")
        docs.append("")
        docs.append("# SMART IDLE DURATION")
        docs.append("# Get recommended idle duration")
        docs.append("duration = events.get_idle_duration()")
        docs.append("print(f'Sleeping for {duration} seconds')")
        docs.append("events.sleep(duration)")
        docs.append("")
        docs.append("# EFFICIENT IDLE LOOP")
        docs.append("idle_count = 0")
        docs.append("while idle_count < 10:")
        docs.append("    # Wait for mail with 10 second timeout")
        docs.append("    new_mail = events.wait_for_mail(10)")
        docs.append("    ")
        docs.append("    if new_mail:")
        docs.append("        print(f'Processing {len(new_mail)} messages...')")
        docs.append("        idle_count = 0  # Reset idle")
        docs.append("    else:")
        docs.append("        idle_count += 1")
        docs.append("        print(f'Idle cycle {idle_count}')")
        docs.append("")
        docs.append("print('Been idle too long, exploring!')")
        docs.append("```")
        docs.append("")
        docs.append("## Important Notes")
        docs.append("- Maximum sleep duration is 300 seconds (5 minutes)")
        docs.append("- Sleep can be interrupted by shutdown signals")
        docs.append("- Mail checks look for .msg and .json files in inbox")
        docs.append("- All durations are in seconds")
        docs.append("- **WARNING**: Only wait ONCE per script execution")
        docs.append("  Multiple waits in the same script are ineffective")
        docs.append("  Return to cognitive loop to think between waits")
        
        return "\n".join(docs)
    
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
    
    async def run(self) -> List[Dict[str, Any]]:
        """Run the execution stage."""
        logger.info("=== EXECUTION STAGE V3 ===")
        
        # The decision is already in working memory - just generate and execute
        # The brain will see the decision buffer content in working memory context
        
        # Phase 1: Generate Python script from working memory context
        script = await self.generate_script()
        
        if not script:
            logger.info("⚡ No script generated - likely no intention to execute")
            return []
        
        # Phase 2: Execute the generated script
        results = await self.execute_script(script)
        
        return results
    
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
            exclude_types=[]  # Include all memory types
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
                    "script": "Python script using memory API (or empty if no intention)"
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
            exclude_types=[]
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