"""Compute actions for Cyber cognitive loops.

These actions provide sandboxed computation capabilities to Cybers,
allowing them to execute Python code for calculations, data processing,
and general computation tasks.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

from .actions.base_actions import Action, ActionResult, ActionStatus, Priority
from .memory import ObservationMemoryBlock

logger = logging.getLogger("Cyber.compute_actions")


class ExecutePythonAction(Action):
    """Execute Python code in a sandboxed environment.
    
    This action provides general-purpose Python computation capabilities
    with the following features:
    - Safe execution in restricted namespace
    - Automatic result capture
    - Error handling and stack traces
    - Memory of execution results
    """
    
    def __init__(self):
        super().__init__(
            "execute_python",
            "Execute Python code for computation and data processing",
            Priority.MEDIUM
        )
        
        # Define safe built-ins for the execution environment
        self.safe_builtins = {
            # Math and numbers
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sum': sum, 'pow': pow, 'divmod': divmod,
            'int': int, 'float': float, 'complex': complex,
            'bin': bin, 'hex': hex, 'oct': oct,
            
            # Collections and iteration
            'len': len, 'range': range, 'enumerate': enumerate,
            'zip': zip, 'map': map, 'filter': filter,
            'sorted': sorted, 'reversed': reversed,
            'all': all, 'any': any,
            
            # Data structures
            'list': list, 'tuple': tuple, 'dict': dict, 'set': set,
            'frozenset': frozenset,
            
            # String operations
            'str': str, 'repr': repr, 'format': format,
            'ord': ord, 'chr': chr,
            
            # Type checking
            'type': type, 'isinstance': isinstance,
            'bool': bool,
            
            # Safe I/O
            'print': print,  # Output will be captured
            
            # Import (needed for module access)
            '__import__': __import__,
            
            # Constants
            'True': True, 'False': False, 'None': None,
            
            # Exceptions (for handling, not raising to system)
            'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'KeyError': KeyError,
            'IndexError': IndexError, 'ZeroDivisionError': ZeroDivisionError,
        }
        
        # Import safe modules
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
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute Python code with captured output."""
        code = self.params.get("code", "")
        description = self.params.get("description", "Python computation")
        persist_variables = self.params.get("persist_variables", False)
        
        if not code.strip():
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No code provided to execute"
            )
        
        # Set up execution environment
        namespace = {
            '__builtins__': self.safe_builtins,
            '__name__': '__agent_compute__',
            '__doc__': 'Cyber computation environment',
        }
        
        # Add safe modules
        namespace.update(self.safe_modules)
        
        # Add any persisted variables from previous executions
        if persist_variables:
            memory_manager = context.get("memory_manager")
            if memory_manager:
                # Look for previous computation results in memory
                compute_memories = [
                    m for m in memory_manager.symbolic_memory
                    if isinstance(m, ObservationMemoryBlock) 
                    and m.observation_type == "computation_result"
                    and m.metadata.get("has_variables", False)
                ]
                if compute_memories:
                    # Get the most recent computation variables
                    latest = max(compute_memories, key=lambda m: m.timestamp)
                    if "namespace" in latest.metadata:
                        # Restore previous variables (only safe types)
                        for key, value in latest.metadata["namespace"].items():
                            if self._is_safe_value(value):
                                namespace[key] = value
        
        # Capture output
        output_lines = []
        original_print = print
        
        def capture_print(*args, **kwargs):
            """Capture print output."""
            output = ' '.join(str(arg) for arg in args)
            output_lines.append(output)
        
        namespace['print'] = capture_print
        
        # Execute the code
        start_time = datetime.now()
        try:
            # Log what we're executing
            logger.info(f"Executing Python code: {len(code)} characters")
            logger.debug(f"Code preview: {code[:200]}...")
            
            # Use compile to get better error messages
            compiled_code = compile(code, '<agent_code>', 'exec')
            
            # Execute in our restricted namespace
            exec(compiled_code, namespace)
            
            # Execution successful
            duration = (datetime.now() - start_time).total_seconds()
            
            # Extract results
            result_vars = {}
            for key, value in namespace.items():
                # Skip built-ins and modules
                if (key not in self.safe_builtins 
                    and key not in self.safe_modules
                    and not key.startswith('__')
                    and self._is_safe_value(value)):
                    result_vars[key] = self._serialize_value(value)
            
            # Build result
            result = {
                "success": True,
                "output": '\n'.join(output_lines) if output_lines else "Code executed successfully (no output)",
                "variables": result_vars,
                "execution_time": f"{duration:.3f} seconds",
                "code_lines": len(code.strip().split('\n'))
            }
            
            # Store in memory if requested
            if context.get("memory_manager") and (output_lines or result_vars):
                # Write computation result to file
                from pathlib import Path
                from datetime import datetime
                import json
                
                obs_dir = Path("/personal/memory/observations/computations")
                obs_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                filename = f"compute_{timestamp}.json"
                filepath = obs_dir / filename
                
                # Write complete computation result to file
                compute_data = {
                    "observation_type": "computation_result",
                    "timestamp": datetime.now().isoformat(),
                    "description": description,
                    "code": code,
                    "output": '\n'.join(output_lines),
                    "variables": result_vars,
                    "has_variables": bool(result_vars),
                    "namespace": {k: v for k, v in namespace.items() 
                                if k not in self.safe_builtins 
                                and k not in self.safe_modules
                                and not k.startswith('__')
                                and self._is_safe_value(v, for_storage=True)},
                    "execution_time": duration,
                    "code_lines": len(code.strip().split('\n'))
                }
                
                with open(filepath, 'w') as f:
                    json.dump(compute_data, f, indent=2, default=str)
                
                # Create observation pointing to the file
                memory_block = ObservationMemoryBlock(
                    observation_type="computation_result",
                    path=str(filepath),  # Path to the actual file
                    priority=Priority.MEDIUM,
                    metadata={
                        "description": description,
                        "result_summary": output_lines[0] if output_lines else 'Computed variables',
                        "has_variables": bool(result_vars)
                    }
                )
                context["memory_manager"].add_memory(memory_block)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result=result
            )
            
        except SyntaxError as e:
            error_msg = f"Syntax error in Python code: {e.msg} at line {e.lineno}"
            logger.error(error_msg)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=error_msg,
                result={"line": e.lineno, "offset": e.offset, "text": e.text}
            )
            
        except Exception as e:
            # Get full traceback
            tb = traceback.format_exc()
            error_msg = f"Error executing Python code: {type(e).__name__}: {str(e)}"
            logger.error(f"{error_msg}\n{tb}")
            
            # Extract the relevant part of traceback (skip our exec wrapper)
            tb_lines = tb.split('\n')
            relevant_tb = []
            for line in tb_lines:
                if '<agent_code>' in line or not line.strip().startswith('File'):
                    relevant_tb.append(line)
            
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=error_msg,
                result={
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "traceback": '\n'.join(relevant_tb) if relevant_tb else tb
                }
            )
    
    def _is_safe_value(self, value: Any, for_storage: bool = False) -> bool:
        """Check if a value is safe to include in results."""
        # Basic types are always safe
        if isinstance(value, (int, float, str, bool, type(None))):
            return True
        
        # Collections are safe if not too large and contain safe values
        if isinstance(value, (list, tuple)):
            if for_storage and len(value) > 100:  # Limit size for storage
                return False
            return all(self._is_safe_value(item, for_storage) for item in value[:10])
        
        if isinstance(value, dict):
            if for_storage and len(value) > 50:  # Limit size for storage
                return False
            return all(
                isinstance(k, str) and self._is_safe_value(v, for_storage) 
                for k, v in list(value.items())[:10]
            )
        
        if isinstance(value, set):
            if for_storage and len(value) > 100:
                return False
            return all(self._is_safe_value(item, for_storage) for item in list(value)[:10])
        
        # Some safe object types
        if type(value).__module__ in ['datetime', 'math', 're']:
            return True
        
        return False
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON storage."""
        if isinstance(value, (int, float, str, bool, type(None))):
            return value
        
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value[:100]]  # Limit size
        
        if isinstance(value, dict):
            return {
                str(k): self._serialize_value(v) 
                for k, v in list(value.items())[:50]  # Limit size
            }
        
        if isinstance(value, set):
            return {"__set__": True, "values": [self._serialize_value(item) for item in list(value)[:100]]}
        
        # Try to convert to string representation
        try:
            return f"<{type(value).__name__}: {str(value)[:100]}>"
        except:
            return f"<{type(value).__name__}>"


class ChangeLocationAction(Action):
    """Change the current working location in the filesystem."""
    
    def __init__(self):
        super().__init__("change_location", "Change current working directory")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Change to a new location and update dynamic context."""
        path = self.params.get("path", "")
        
        if not path:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No path specified"
            )
        
        try:
            # Get cognitive loop for dynamic context update
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No cognitive loop available"
                )
            
            # Read current dynamic context
            if hasattr(cognitive_loop, 'dynamic_context_file'):
                with open(cognitive_loop.dynamic_context_file, 'r') as f:
                    dynamic_context = json.load(f)
                current_location = dynamic_context.get("current_location", "/personal")
            else:
                current_location = "/personal"
            
            # Resolve the new path
            from pathlib import PurePosixPath
            
            if path.startswith('/'):
                # Absolute path
                new_location = PurePosixPath(path)
            else:
                # Relative path
                current = PurePosixPath(current_location)
                new_location = (current / path).resolve()
            
            # Convert to string and ensure it starts with /
            new_location_str = str(new_location)
            if not new_location_str.startswith('/'):
                new_location_str = '/' + new_location_str
            
            # Validate the path is within allowed areas
            allowed_roots = ['/personal', '/grid']
            if not any(new_location_str.startswith(root) or new_location_str == root for root in allowed_roots):
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Cannot navigate to {new_location_str} - must be within /personal or /grid"
                )
            
            # Check if the path exists (in the cyber's view)
            if new_location_str.startswith('/personal'):
                # Map to actual personal directory
                rel_path = new_location_str[len('/personal'):]
                if rel_path:
                    actual_path = cognitive_loop.personal / rel_path.lstrip('/')
                else:
                    actual_path = cognitive_loop.personal
            elif new_location_str.startswith('/grid'):
                # Map to actual grid directory
                rel_path = new_location_str[len('/grid'):]
                grid_path = cognitive_loop.personal.parent.parent / "grid"
                if rel_path:
                    actual_path = grid_path / rel_path.lstrip('/')
                else:
                    actual_path = grid_path
            else:
                actual_path = None
            
            # Check if path exists
            if actual_path and not actual_path.exists():
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Path does not exist: {new_location_str}"
                )
            
            # Update dynamic context
            cognitive_loop._update_dynamic_context(current_location=new_location_str)
            
            logger.info(f"Changed location from {current_location} to {new_location_str}")
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "previous_location": current_location,
                    "current_location": new_location_str,
                    "absolute_path": new_location_str
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to change location: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Failed to change location: {str(e)}"
            )


class SimplifyExpressionAction(Action):
    """Simplify mathematical or logical expressions.
    
    A specialized action for quick expression evaluation without
    full Python execution overhead.
    """
    
    def __init__(self):
        super().__init__(
            "simplify_expression",
            "Evaluate simple mathematical or logical expressions",
            Priority.MEDIUM
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Evaluate a simple expression safely."""
        expression = self.params.get("expression", "")
        
        if not expression.strip():
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No expression provided"
            )
        
        try:
            # Use a very restricted evaluator for simple math
            import ast
            import operator
            
            # Define allowed operations
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.Mod: operator.mod,
                ast.FloorDiv: operator.floordiv,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }
            
            def eval_expr(node):
                if isinstance(node, ast.Num):  # <number>
                    return node.n
                elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
                    return ops[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                elif isinstance(node, ast.UnaryOp):  # <operator> <operand>
                    return ops[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(f"Unsupported expression type: {type(node)}")
            
            # Parse and evaluate
            parsed = ast.parse(expression, mode='eval')
            result = eval_expr(parsed.body)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "expression": expression,
                    "result": result,
                    "type": type(result).__name__
                }
            )
            
        except Exception as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Failed to evaluate expression: {str(e)}"
            )


# Register compute actions
def register_compute_actions(registry):
    """Register all compute actions."""
    registry.register_action("base", "execute_python", ExecutePythonAction)
    registry.register_action("base", "simplify_expression", SimplifyExpressionAction)
    registry.register_action("base", "change_location", ChangeLocationAction)