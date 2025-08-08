#!/usr/bin/env python3
"""Demo script showing the new memory system in action."""

import sys
from pathlib import Path
import tempfile
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mind_swarm.agent_sandbox.memory import (
    WorkingMemoryManager, ContentLoader, ContextBuilder, MemorySelector,
    FileMemoryBlock, MessageMemoryBlock, ObservationMemoryBlock,
    Priority, MemoryType
)
from mind_swarm.agent_sandbox.perception import EnvironmentScanner


def demo_memory_system():
    """Demonstrate the memory system capabilities."""
    print("=== Mind-Swarm Memory System Demo ===\n")
    
    # Create temporary directories to simulate Cyber environment
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Set up directory structure
        cyber_personal = tmpdir / "cybers" / "Cyber-001"
        shared_dir = tmpdir / "shared"
        inbox = cyber_personal / "inbox"
        
        for d in [cyber_personal, shared_dir, inbox, shared_dir / "community", shared_dir / "knowledge"]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Create some test files
        code_file = cyber_personal / "project.py"
        code_file.write_text("""def hello_world():
    print("Hello from the Mind Swarm!")
    
def process_data(data):
    return [x * 2 for x in data]
""")
        
        # Create a message
        msg_file = inbox / "msg001.msg"
        msg_data = {
            "from": "subspace",
            "to": "Cyber-001",
            "subject": "Analyze the project code",
            "content": "Please analyze the project.py file and explain what it does.",
            "timestamp": datetime.now().isoformat()
        }
        msg_file.write_text(json.dumps(msg_data))
        
        # Create shared knowledge
        knowledge_file = shared_dir / "knowledge" / "python_tips.md"
        knowledge_file.write_text("# Python Tips\n\nAlways use list comprehensions for simple transformations.")
        
        print("1. Setting up memory system...")
        
        # Initialize memory system
        memory_manager = WorkingMemoryManager(max_tokens=10000)
        content_loader = ContentLoader(filesystem_root=tmpdir)
        context_builder = ContextBuilder(content_loader)
        memory_selector = MemorySelector(context_builder)
        
        # Initialize environment scanner
        scanner = EnvironmentScanner(
            home_path=cyber_personal,
            shared_path=shared_dir
        )
        
        print("2. Scanning environment...")
        
        # Scan environment
        observations = scanner.scan_environment(full_scan=True)
        print(f"   Found {len(observations)} observations:")
        
        for obs in observations:
            memory_manager.add_memory(obs)
            if hasattr(obs, 'description'):
                print(f"   - {obs.description}")
        
        print("\n3. Adding file memories...")
        
        # Add file memory
        file_memory = FileMemoryBlock(
            location=str(code_file),
            priority=Priority.HIGH,
            confidence=0.9
        )
        memory_manager.add_memory(file_memory)
        print(f"   Added: {file_memory.id}")
        
        print("\n4. Memory statistics:")
        stats = memory_manager.get_memory_stats()
        print(f"   Total memories: {stats['total_memories']}")
        print(f"   By type: {stats['by_type']}")
        print(f"   Unread messages: {stats['unread_messages']}")
        
        print("\n5. Selecting memories for task...")
        
        # Select memories for a task
        task = "Analyze the project code and explain what it does"
        selected = memory_selector.select_memories(
            memory_manager.symbolic_memory,
            max_tokens=5000,
            current_task=task,
            selection_strategy="relevant"
        )
        
        print(f"   Selected {len(selected)} memories for task: '{task}'")
        for mem in selected:
            print(f"   - {mem.type.value}: {mem.id} (priority={mem.priority.name})")
        
        print("\n6. Building context for LLM...")
        
        # Build context
        context = context_builder.build_context(selected, format_type="structured")
        print(f"   Context preview (first 500 chars):")
        print("   " + "-" * 60)
        print(context[:500] + "...")
        
        print("\n7. Processing a message...")
        
        # Get unread messages
        unread = memory_manager.get_unread_messages()
        if unread:
            msg = unread[0]
            print(f"   Processing message: {msg.subject}")
            print(f"   From: {msg.from_agent}")
            
            # Mark as read
            memory_manager.mark_message_read(msg.id)
            print(f"   Marked as read, priority changed to: {msg.priority.name}")
        
        print("\n=== Demo Complete ===")


if __name__ == "__main__":
    demo_memory_system()