"""
Status Manager for Cyber internal status generation.

This module is NOT accessible during execution - it's only used internally
by the cognitive loop to generate status files for monitoring.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("Cyber.status")


class StatusManager:
    """Manages cyber status display generation."""
    
    def __init__(self, cognitive_loop):
        """Initialize the Status Manager.
        
        Args:
            cognitive_loop: The cognitive loop instance
        """
        self.cognitive_loop = cognitive_loop
        self.personal = Path(cognitive_loop.personal)
        self.memory_system = cognitive_loop.memory_system
        
        # Status file paths
        self.status_dir = self.personal / '.internal' / 'memory' / 'status'
        self.status_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.status_dir / 'biofeedback_state.json'
        self.status_file = self.status_dir / 'status.txt'
        self.status_json = self.status_dir / 'status.json'
        
        # Activity log for recent entries
        self.activity_log = self.personal / '.internal' / 'memory' / 'activity.log'
        
        # Get cyber name for community task filtering
        self.cyber_name = self._get_cyber_name()
        
        # Load or initialize biofeedback state
        self.state = self._load_state()
        
        # Configuration
        self.config = {
            'boredom_increment': 5,  # Per cycle on same task
            'tiredness_increment': 2,  # Per cycle without maintenance
            'tiredness_decay': 20,  # Reduction when doing maintenance
            'duty_window_cycles': 100,  # Rolling window for duty calculation
        }
    
    def render(self):
        """Generate and save consolidated status files."""
        try:
            # Get formatted status
            status_text = self.get_formatted_status()
            
            # Debug log to see what we're writing
            logger.debug(f"Rendering status ({len(status_text)} chars)")
            
            # Save text version (atomic write)
            temp_file = self.status_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(status_text)
                f.flush()  # Ensure all data is written
                os.fsync(f.fileno())  # Force write to disk
            os.rename(temp_file, self.status_file)
            
            # Save JSON version for machine reading
            current_task = self._get_current_task()
            
            stats = self.get_biofeedback()
            status_data = {
                'cycle': self.cognitive_loop.cycle,
                'timestamp': datetime.now().isoformat(),
                'name': self._get_cyber_name(),
                'biofeedback': stats,
                'current_task': {
                    'id': current_task.get('id') if current_task else None,
                    'type': current_task.get('task_type') if current_task else None,
                    'summary': current_task.get('summary') if current_task else None
                }
            }
            
            temp_json = self.status_json.with_suffix('.tmp')
            with open(temp_json, 'w') as f:
                json.dump(status_data, f, indent=2)
            os.rename(temp_json, self.status_json)
            
            logger.debug(f"Status rendered to {self.status_file}")
            
        except Exception as e:
            # Log the error
            logger.error(f"Failed to render status: {e}", exc_info=True)
            
            # Try to write an error message to status.txt so it's visible
            try:
                error_text = f"**ERROR RENDERING STATUS**\n\n"
                error_text += f"An error occurred while generating the status display:\n"
                error_text += f"{str(e)}\n\n"
                error_text += f"Please check the logs for details.\n"
                error_text += f"Cycle: {self.cognitive_loop.cycle}\n"
                error_text += f"Time: {datetime.now().strftime('%H:%M GMT - %d/%m/%Y')}"
                
                # Write error status directly (not atomic, but better than nothing)
                with open(self.status_file, 'w') as f:
                    f.write(error_text)
                    
            except Exception as inner_e:
                # If we can't even write the error, at least log it
                logger.critical(f"Failed to write error status: {inner_e}")
    
    def get_formatted_status(self) -> str:
        """Generate formatted status text display.
        
        Returns:
            Formatted status text for display
        """
        # Get cyber name
        name = self._get_cyber_name()
        
        # Get current cycle and time
        cycle = self.cognitive_loop.cycle
        current_time = datetime.now().strftime("%H:%M GMT - %d/%m/%Y")
        
        # Get biofeedback stats
        stats = self.get_biofeedback()
        
        # Build status text
        lines = []
        lines.append(f"I am Cyber {name}.")
        
        lines.append("\n**Personal Stats:**")
        lines.append(f"- Boredom:     {self._make_bar(stats['boredom'])} ({stats['boredom']}%)")
        lines.append(f"- Tiredness:   {self._make_bar(stats['tiredness'])} ({stats['tiredness']}%)")
        lines.append(f"- Duty:        {self._make_bar(stats['duty'])} ({stats['duty']}%)")
        lines.append(f"- Restlessness:{self._make_bar(stats['restlessness'])} ({stats['restlessness']}%)")
        lines.append(f"- Cycle:       {cycle}")
        
        # Add warnings if needed
        if stats['boredom'] > 80:
            lines.append("\n⚠ High boredom - strongly consider switching to a hobby task!")
        elif stats['boredom'] > 60:
            lines.append("\n💭 Getting bored - maybe try a different task type?")
        
        if stats['tiredness'] > 80:
            lines.append("\n⚠ Very tired - maintenance tasks needed soon!")
        elif stats['tiredness'] > 60:
            lines.append("\n💭 Getting tired - consider some maintenance work")
        
        if stats['duty'] < 20:
            lines.append("\n⚠ Low duty - the community needs your help! Consider claiming a community task.")
        elif stats['duty'] < 50:
            lines.append("\n💭 Duty declining - maybe contribute to a community task?")
        
        if stats['restlessness'] > 80:
            lines.append("\n⚠ Very restless - you need to explore! Move to a new location.")
        elif stats['restlessness'] > 60:
            lines.append("\n💭 Getting restless - maybe explore a different area?")
        
        lines.append(f"\n**Environment:**")
        lines.append(f"- Time: {current_time}")
        
        # Check for messages
        messages = self._check_messages()
        if messages:
            lines.append(f"- Messages: {messages}")
        else:
            lines.append("- Messages: No new messages this cycle.")
        
        # Add location info
        location_info = self._get_location_info()
        if location_info:
            lines.append(f"\n**Location:**")
            lines.append(location_info)
        
        # Add current task and todos
        lines.append(f"\n**Tasks:**")
        current_task = self._get_current_task()
        if current_task:
            task_type = current_task.get('task_type', 'unknown').capitalize()
            task_id = current_task['id']
            summary = current_task.get('summary', 'No summary')
            description = current_task.get('description', '')
            
            # Show the full description if available, otherwise fall back to summary
            if description:
                lines.append(f"My current task is **{task_id}: {summary}**")
                lines.append(f"Description: {description}")
            else:
                lines.append(f"My current task is **{task_id}: {summary}**")
            
            todos = current_task.get('todo', [])
            if todos:
                lines.append("\n**To-Do List:**")
                for i, todo in enumerate(todos[:10], 1):  # Max 10 items
                    status = todo.get('status', 'NOT-STARTED')
                    status_icon = {
                        'DONE': '[DONE]',
                        'IN-PROGRESS': '[IN-PROGRESS]',
                        'BLOCKED': '[BLOCKED]',
                        'NOT-STARTED': '[NOT-STARTED]'
                    }.get(status, '[?]')
                    lines.append(f"{i}. {status_icon} {todo.get('title', 'Untitled')}")
                    if todo.get('notes'):
                        lines.append(f"   {todo['notes']}")
        else:
            lines.append("No current task set. Check task backlog below for available tasks.")
        
        # Add task backlog
        lines.append("\n**Task Backlog (CT = Community, MT = Maintenance, HT = Hobby):**")
        backlog = self._get_task_backlog()
        if backlog:
            # Combine all tasks into a single list
            all_tasks = []
            for category, tasks in backlog.items():
                all_tasks.extend(tasks)
            
            # Sort tasks by ID for consistent ordering
            all_tasks.sort(key=lambda x: x['id'])
            
            if all_tasks:
                for task in all_tasks:
                    summary = task.get('summary', 'No summary')
                    # Don't truncate - show full task summary
                    lines.append(f"  • {task['id']}: {summary}")
            else:
                lines.append("  • No tasks in backlog")
        else:
            lines.append("  • No tasks in backlog")
        
        # Add recent activity
        lines.append("\n**Activity Log:**")
        try:
            activity = self._get_recent_activity(10)
            if activity:
                for entry in activity:
                    lines.append(f"- {entry}")
            else:
                lines.append("- No recent activity recorded")
        except Exception as e:
            logger.warning(f"Failed to get activity log: {e}")
            lines.append(f"- Error loading activity: {e}")
        
        return '\n'.join(lines)
    
    def _get_cyber_name(self) -> str:
        """Get cyber name from identity file."""
        try:
            # Try unified state first
            unified_state_file = self.personal / '.internal' / 'memory' / 'unified_state.json'
            if unified_state_file.exists():
                with open(unified_state_file, 'r') as f:
                    state_data = json.load(f)
                    identity = state_data.get('identity', {})
                    return identity.get('name', identity.get('cyber_id', 'Unknown'))
            
            # Fallback to status.json
            status_file = self.personal / '.internal' / 'status.json'
            if status_file.exists():
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                    return status_data.get('name', 'Unknown')
        except Exception as e:
            logger.debug(f"Error getting cyber name: {e}")
        return 'Unknown'
    
    def _check_messages(self) -> str:
        """Check for new messages."""
        count = 0
        messages_dir = self.personal / '.internal' / 'messages'
        if messages_dir.exists():
            # Count unread messages (simple heuristic: created in last cycle)
            for msg_file in messages_dir.glob('*.msg'):
                if msg_file.stat().st_mtime > (datetime.now().timestamp() - 300):  # Last 5 minutes
                    count += 1
        
        if count > 0:
            return f"{count} new message{'s' if count > 1 else ''}"
        return ""
    
    def _get_location_info(self) -> str:
        """Get current location information."""
        try:
            location_file = self.personal / '.internal' / 'memory' / 'location.txt'
            if location_file.exists():
                location = location_file.read_text().strip()
                
                # Try to get description
                desc_file = Path(location) / '.description.txt'
                if desc_file.exists():
                    desc = desc_file.read_text().strip()[:100]  # First 100 chars
                    return f"{location}\n  Description: {desc}"
                
                return location
        except Exception:
            pass
        return ""
    
    def _get_current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current active task."""
        try:
            current_task_file = self.personal / '.internal' / 'tasks' / 'current_task.txt'
            if current_task_file.exists():
                task_id = current_task_file.read_text().strip()
                if not task_id:
                    return None
                
                # Determine which directory to look in based on task prefix
                tasks_base = self.personal / '.internal' / 'tasks'
                
                if task_id.startswith('HT-'):
                    task_dir = tasks_base / 'hobby'
                elif task_id.startswith('MT-'):
                    task_dir = tasks_base / 'maintenance'
                elif task_id.startswith('CT-'):
                    # Community tasks are in grid
                    task_dir = Path('/grid/community/tasks')
                else:
                    # Unknown task type, check all directories
                    for dir_name in ['hobby', 'maintenance', 'blocked']:
                        task_dir = tasks_base / dir_name
                        for task_file in task_dir.glob(f"{task_id}_*.json"):
                            with open(task_file, 'r') as f:
                                return json.load(f)
                    return None
                
                # Look for the task file
                for task_file in task_dir.glob(f"{task_id}_*.json"):
                    with open(task_file, 'r') as f:
                        return json.load(f)
        except Exception as e:
            logger.debug(f"No current task found: {e}")
        
        return None
    
    def _get_recent_activity(self, count: int = 5) -> List[str]:
        """Get recent activity log entries.
        
        Args:
            count: Number of entries to return
            
        Returns:
            List of recent activity strings
        """
        entries = []
        if self.activity_log.exists():
            try:
                with open(self.activity_log, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-count:]:
                        line = line.strip()
                        if line:
                            # Extract cycle number and summary more robustly
                            import re
                            match = re.match(r'Cycle\s+(\d+):\s*(.+)', line)
                            if match:
                                cycle = match.group(1).zfill(4)  # Pad to 4 digits
                                summary = match.group(2).strip()
                                # Handle duplicated "Cycle X:" in summary
                                summary = re.sub(r'^Cycle\s+\d+:\s*', '', summary)
                                # Don't truncate the summary - show the full activity
                                entries.append(f"**Cycle {cycle}:** {summary}")
            except Exception:
                pass
        
        return entries
    
    def _get_task_backlog(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all tasks organized by status/type.
        
        Returns:
            Dictionary with categories as keys and lists of tasks as values
        """
        backlog = {}
        
        # Get current task ID to exclude from backlog
        current_task = self._get_current_task()
        current_task_id = current_task.get('id') if current_task else None
        
        try:
            tasks_dir = self.personal / '.internal' / 'tasks'
            
            # Define task categories to scan
            categories = {
                'Hobby Tasks': 'hobby', 
                'Maintenance Tasks': 'maintenance',
                'Blocked Tasks': 'blocked',
                'Community Tasks': '/grid/community/tasks/claimed'
            }
            
            for category_name, subdir in categories.items():
                task_list = []
                
                # Handle absolute paths for community tasks
                if subdir.startswith('/'):
                    task_path = Path(subdir)
                else:
                    task_path = tasks_dir / subdir
                
                if task_path.exists():
                    for task_file in sorted(task_path.glob('*.json')):
                        try:
                            with open(task_file, 'r') as f:
                                task_data = json.load(f)
                                
                                task_id = task_data.get('id', task_file.stem.split('_')[0])
                                
                                # Skip current task
                                if task_id == current_task_id:
                                    continue
                                
                                # For community tasks, only show ones claimed by this cyber
                                if category_name == 'Community Tasks':
                                    if task_data.get('claimed_by') != self.cyber_name:
                                        continue  # Skip tasks not claimed by this cyber
                                
                                # Only include basic info to keep status concise
                                task_list.append({
                                    'id': task_id,
                                    'summary': task_data.get('summary', 'No summary')
                                })
                        except Exception:
                            pass
                
                if task_list:
                    backlog[category_name] = task_list
                    
        except Exception as e:
            logger.warning(f"Failed to get task backlog: {e}")
        
        return backlog
    
    def _load_state(self) -> Dict[str, Any]:
        """Load persisted biofeedback state or create default."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        
        # Default state
        return {
            'boredom': 0,
            'tiredness': 0,
            'duty': 100,  # Start at 100% (fully dutiful)
            'restlessness': 0,  # Increases when staying in one place
            'current_task_id': None,
            'current_task_type': None,
            'cycles_on_current_task': 0,
            'cycles_since_maintenance': 0,
            'cycles_since_move': 0,  # Track cycles since last location change
            'current_location': None,  # Track current location
            'last_duty_decrement_cycle': 0,  # Track when duty was last decremented
            'credited_community_tasks': [],  # List of community task IDs we've credited
            'credited_maintenance_tasks': [],  # List of maintenance task IDs we've credited
            'last_update_cycle': 0
        }
    
    def _save_state(self):
        """Persist biofeedback state to disk."""
        try:
            # Atomic write
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            os.rename(temp_file, self.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def get_biofeedback(self) -> Dict[str, int]:
        """Calculate current biofeedback stats.
        
        Returns:
            Dict with boredom, tiredness, and duty percentages (0-100)
        """
        # Update state based on current task and activity
        self._update_biofeedback()
        
        # Manage maintenance tasks based on tiredness
        self._manage_maintenance_tasks()
        
        return {
            'boredom': min(100, max(0, self.state['boredom'])),
            'tiredness': min(100, max(0, self.state['tiredness'])),
            'duty': min(100, max(0, self.state['duty'])),
            'restlessness': min(100, max(0, self.state.get('restlessness', 0)))
        }
    
    def _manage_maintenance_tasks(self):
        """Manage maintenance tasks based on tiredness level.
        
        Maintenance tasks start in completed state and get reactivated based on tiredness:
        - Every 10% tiredness above 30% adds one maintenance task back to the backlog
        - Tasks are moved from completed to maintenance directory
        """
        try:
            tasks_dir = self.personal / '.internal' / 'tasks'
            maintenance_dir = tasks_dir / 'maintenance'
            completed_dir = tasks_dir / 'completed'
            
            if not maintenance_dir.exists() or not completed_dir.exists():
                return
            
            # Get current tiredness
            tiredness = self.state['tiredness']
            
            # Calculate how many maintenance tasks should be active
            # For every 10% above 30%, add one task
            if tiredness <= 30:
                target_maintenance_count = 0
            else:
                excess_tiredness = tiredness - 30
                target_maintenance_count = min(5, (excess_tiredness // 10) + 1)  # Cap at 5
            
            # Count current maintenance tasks in backlog
            current_maintenance_tasks = list(maintenance_dir.glob("MT-*.json"))
            current_count = len(current_maintenance_tasks)
            
            # If we need more maintenance tasks, move them from completed
            if current_count < target_maintenance_count:
                # Find completed maintenance tasks
                completed_maintenance = sorted(completed_dir.glob("MT-*.json"))
                
                # Move tasks from completed to maintenance
                tasks_to_activate = target_maintenance_count - current_count
                for task_file in completed_maintenance[:tasks_to_activate]:
                    try:
                        import json
                        # Load task data
                        with open(task_file, 'r') as f:
                            task_data = json.load(f)
                        
                        # Reset task status
                        task_data['status'] = 'pending'
                        if 'completed_at' in task_data:
                            del task_data['completed_at']
                        
                        # Reset todos if present
                        if 'todo' in task_data:
                            for todo in task_data['todo']:
                                todo['status'] = 'NOT-STARTED'
                                if 'notes' in todo and 'Completed' in todo.get('notes', ''):
                                    todo['notes'] = ''
                        
                        # Write to maintenance directory
                        new_path = maintenance_dir / task_file.name
                        with open(new_path, 'w') as f:
                            json.dump(task_data, f, indent=2)
                        
                        # Remove from completed
                        task_file.unlink()
                        
                        logger.debug(f"Reactivated maintenance task {task_file.name} due to tiredness")
                    except Exception as e:
                        logger.error(f"Failed to reactivate maintenance task {task_file.name}: {e}")
            
            # If tiredness is low and we have too many maintenance tasks, they'll naturally
            # move back to completed when the cyber completes them
            
        except Exception as e:
            logger.error(f"Failed to manage maintenance tasks: {e}")
    
    def _check_maintenance_completions(self):
        """Check for recently completed maintenance tasks and reduce tiredness."""
        try:
            completed_dir = self.personal / '.internal' / 'tasks' / 'completed'
            if not completed_dir.exists():
                return
            
            # Track which maintenance tasks we've already credited
            if 'credited_maintenance_tasks' not in self.state:
                self.state['credited_maintenance_tasks'] = []
            
            # Check for completed maintenance tasks
            for task_file in completed_dir.glob("MT-*.json"):
                try:
                    import json
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                    
                    task_id = task_data.get('id')
                    if not task_id:
                        continue
                    
                    # If this task was completed recently and we haven't credited it yet
                    if task_id not in self.state['credited_maintenance_tasks']:
                        # Check if it was completed recently (has completed_at field)
                        if 'completed_at' in task_data:
                            # Reduce tiredness by 15% for completing a maintenance task
                            self.state['tiredness'] = max(0, self.state['tiredness'] - 15)
                            self.state['credited_maintenance_tasks'].append(task_id)
                            logger.info(f"Completed maintenance task {task_id}, reduced tiredness by 15%")
                            
                            # Keep only last 10 credited tasks to avoid memory bloat
                            if len(self.state['credited_maintenance_tasks']) > 10:
                                self.state['credited_maintenance_tasks'] = self.state['credited_maintenance_tasks'][-10:]
                                
                except Exception as e:
                    logger.error(f"Failed to check maintenance task {task_file.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to check maintenance completions: {e}")
    
    def _update_biofeedback(self):
        """Update biofeedback metrics based on current activity."""
        # Get current cycle from cognitive loop
        current_cycle = self.cognitive_loop.cycle
        
        # Skip if same cycle
        if current_cycle <= self.state['last_update_cycle']:
            return
        
        # Check current task
        current_task = self._get_current_task()
        
        # Update boredom based on task continuity
        if current_task:
            if current_task['id'] == self.state['current_task_id']:
                # Same task
                self.state['cycles_on_current_task'] += 1
                if current_task.get('task_type') != 'hobby':
                    # Increase boredom for non-hobby tasks
                    self.state['boredom'] += self.config['boredom_increment']
            else:
                # Task changed
                self.state['current_task_id'] = current_task['id']
                self.state['current_task_type'] = current_task.get('task_type', 'general')
                self.state['cycles_on_current_task'] = 1
                # Reset boredom when switching tasks
                self.state['boredom'] = max(0, self.state['boredom'] - 20)
        
        # Check for recently completed maintenance tasks
        self._check_maintenance_completions()
        
        # Update tiredness based on maintenance activity
        if current_task and current_task.get('task_type') == 'maintenance':
            # Doing maintenance reduces tiredness gradually
            self.state['tiredness'] = max(0, self.state['tiredness'] - self.config['tiredness_decay'])
            self.state['cycles_since_maintenance'] = 0
        else:
            # Not doing maintenance increases tiredness
            self.state['cycles_since_maintenance'] += 1
            self.state['tiredness'] += self.config['tiredness_increment']
        
        # Update restlessness based on location changes
        self._update_restlessness()
        
        # Update duty based on community completions
        self._update_duty_metric(current_cycle)
        
        self.state['last_update_cycle'] = current_cycle
        self._save_state()
    
    def _update_restlessness(self):
        """Update restlessness based on location changes.
        
        Restlessness increases by 10% for every 10 cycles without moving.
        Moving to a new location decreases restlessness by 10%.
        """
        try:
            # Get current location from dynamic context
            dynamic_context_file = self.personal / ".internal" / "memory" / "dynamic_context.json"
            if dynamic_context_file.exists():
                with open(dynamic_context_file, 'r') as f:
                    context = json.load(f)
                    current_location = context.get('current_location', '/grid/library/knowledge')
            else:
                current_location = '/grid/library/knowledge'
            
            # Check if location has changed
            if self.state.get('current_location') != current_location:
                # Location changed - decrease restlessness
                self.state['restlessness'] = max(0, self.state.get('restlessness', 0) - 10)
                self.state['cycles_since_move'] = 0
                self.state['current_location'] = current_location
                logger.debug(f"Location changed to {current_location}, restlessness decreased")
            else:
                # Same location - increment counter
                self.state['cycles_since_move'] = self.state.get('cycles_since_move', 0) + 1
                
                # Every 10 cycles without moving increases restlessness by 10%
                if self.state['cycles_since_move'] >= 10:
                    self.state['restlessness'] = min(100, self.state.get('restlessness', 0) + 10)
                    self.state['cycles_since_move'] = 0  # Reset counter but keep tracking
                    logger.debug(f"No movement for 10 cycles, restlessness increased")
                    
        except Exception as e:
            logger.error(f"Failed to update restlessness: {e}")
    
    def _update_duty_metric(self, current_cycle: int):
        """Update duty metric using increment/decrement bucket system.
        
        Duty starts at 100% and:
        - Decreases by 5% every 20 cycles (neglect)
        - Increases by 20% when completing a community task
        - Capped between 0 and 100
        """
        # Initialize duty tracking if needed
        if 'last_duty_decrement_cycle' not in self.state:
            self.state['last_duty_decrement_cycle'] = current_cycle
            self.state['duty'] = 100  # Start at 100%
        
        # Check if 20 cycles have passed since last decrement
        cycles_since_decrement = current_cycle - self.state['last_duty_decrement_cycle']
        if cycles_since_decrement >= 20:
            # Decrease duty by 5% for every 20 cycles
            decrements = cycles_since_decrement // 20
            self.state['duty'] = max(0, self.state['duty'] - (5 * decrements))
            self.state['last_duty_decrement_cycle'] = current_cycle - (cycles_since_decrement % 20)
            logger.debug(f"Duty decreased by {5 * decrements}% after {cycles_since_decrement} cycles")
        
        # Check for recently completed community tasks to increase duty
        self._check_community_task_completions()
        
        # Ensure duty stays within bounds
        self.state['duty'] = min(100, max(0, self.state['duty']))
    
    def _check_community_task_completions(self):
        """Check for completed community tasks and increase duty."""
        try:
            completed_dir = self.personal / '.internal' / 'tasks' / 'completed'
            if not completed_dir.exists():
                return
            
            # Track which community tasks we've already credited
            if 'credited_community_tasks' not in self.state:
                self.state['credited_community_tasks'] = []
            
            # Check for completed community tasks
            for task_file in completed_dir.glob("CT-*.json"):
                try:
                    import json
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                    
                    task_id = task_data.get('id')
                    if not task_id:
                        continue
                    
                    # If this task was completed recently and we haven't credited it yet
                    if task_id not in self.state['credited_community_tasks']:
                        # Check if it was completed recently (has completed_at field)
                        if 'completed_at' in task_data:
                            # Increase duty by 20% for completing a community task
                            self.state['duty'] = min(100, self.state['duty'] + 20)
                            self.state['credited_community_tasks'].append(task_id)
                            logger.info(f"Completed community task {task_id}, increased duty by 20%")
                            
                            # Keep only last 10 credited tasks to avoid memory bloat
                            if len(self.state['credited_community_tasks']) > 10:
                                self.state['credited_community_tasks'] = self.state['credited_community_tasks'][-10:]
                                
                except Exception as e:
                    logger.error(f"Failed to check community task {task_file.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to check community task completions: {e}")
    
    def _make_bar(self, percentage: int) -> str:
        """Create a visual progress bar.
        
        Args:
            percentage: Value from 0-100
            
        Returns:
            Visual bar like [####______]
        """
        filled = int(percentage / 10)
        empty = 10 - filled
        return f"[{'#' * filled}{'_' * empty}]"