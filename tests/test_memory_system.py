"""Tests for the new memory system components."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

# Note: These imports may need to be adjusted based on actual module structure
# Currently assuming the test can access the subspace_template modules
from mind_swarm.agent_sandbox.memory import (
    MemoryBlock, Priority, MemoryType,
    FileMemoryBlock, ObservationMemoryBlock,
    WorkingMemoryManager, ContentLoader, ContextBuilder, MemorySelector
)
from mind_swarm.agent_sandbox.perception import EnvironmentScanner


class TestMemoryBlocks:
    """Test memory block creation and properties."""
    
    def test_file_memory_block(self):
        """Test FileMemoryBlock creation."""
        memory = FileMemoryBlock(
            location="/test/file.py",
            start_line=10,
            end_line=20,
            priority=Priority.HIGH
        )
        
        assert memory.type == MemoryType.FILE
        # ID is now just the normalized path with line range suffix
        assert memory.id == "personal/test/file.py#L10-20"
        assert memory.priority == Priority.HIGH
        assert memory.confidence == 1.0
    
    # MessageMemoryBlock removed - no longer exists in current codebase
    # Messages are now handled as FileMemoryBlock with appropriate content_type
    
    def test_observation_memory_block(self):
        """Test ObservationMemoryBlock."""
        memory = ObservationMemoryBlock(
            observation_type="file_changed",
            path="/shared/test.txt",
            message="File was modified",
            cycle_count=1
        )
        
        assert memory.type == MemoryType.OBSERVATION
        assert memory.priority == Priority.HIGH
        assert memory.observation_type == "file_changed"
        # ID should now be a path with hash suffix
        assert memory.id.startswith("personal/observations/") or memory.id.startswith("grid/")
        assert "#" in memory.id  # Should have hash suffix for uniqueness


class TestWorkingMemoryManager:
    """Test the working memory manager."""
    
    def test_add_and_retrieve_memory(self):
        """Test adding and retrieving memories."""
        manager = WorkingMemoryManager()
        
        # Add a file memory
        file_mem = FileMemoryBlock(
            location="/test/file.py",
            priority=Priority.MEDIUM
        )
        manager.add_memory(file_mem)
        
        # Check it's stored
        assert len(manager.symbolic_memory) == 1
        assert file_mem.id in manager.memory_index
        
        # Retrieve by type
        file_memories = manager.get_memories_by_type(MemoryType.FILE)
        assert len(file_memories) == 1
        assert file_memories[0] == file_mem
    
    def test_unread_messages(self):
        """Test unread message tracking."""
        manager = WorkingMemoryManager()
        
        # Test with file memory instead (MessageMemoryBlock no longer exists)
        file1 = FileMemoryBlock(
            location="personal/inbox/msg1.json",
            priority=Priority.HIGH
        )
        manager.add_memory(file1)
        
        # Add another file memory
        msg2 = MessageMemoryBlock(
            from_agent="Cyber-002",
            to_agent="me",
            subject="Test 2",
            preview="...",
            full_path="/msg2.json",
            read=True
        )
        manager.add_memory(msg2)
        
        # Check unread
        unread = manager.get_unread_messages()
        assert len(unread) == 1
        assert unread[0] == msg1
        
        # Mark as read
        manager.mark_message_read(msg1.id)
        assert msg1.read
        assert msg1.priority == Priority.MEDIUM  # Lowered priority
        
        unread = manager.get_unread_messages()
        assert len(unread) == 0
    
    def test_memory_stats(self):
        """Test memory statistics."""
        manager = WorkingMemoryManager()
        
        # Add various memories
        manager.add_memory(FileMemoryBlock(location="/file1.py"))
        manager.add_memory(FileMemoryBlock(location="/file2.py"))
        manager.add_memory(MessageMemoryBlock(
            from_agent="test", to_agent="me", subject="Test",
            preview="...", full_path="/msg.json", read=False
        ))
        
        stats = manager.get_memory_stats()
        assert stats["total_memories"] == 3
        assert stats["by_type"]["file"] == 2
        assert stats["by_type"]["message"] == 1
        assert stats["unread_messages"] == 1


class TestContentLoader:
    """Test content loading from filesystem."""
    
    def test_load_file_content(self):
        """Test loading file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
            
            # Create loader
            loader = ContentLoader(filesystem_root=tmpdir)
            
            # Test full file load
            memory = FileMemoryBlock(location=str(test_file))
            content = loader.load_file_content(memory)
            assert content == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
            
            # Test line range
            memory = FileMemoryBlock(
                location=str(test_file),
                start_line=2,
                end_line=4
            )
            content = loader.load_file_content(memory)
            assert content == "Line 2\nLine 3\nLine 4"
    
    def test_load_message_content(self):
        """Test loading message content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create message file
            msg_file = Path(tmpdir) / "message.msg"
            msg_data = {
                "from": "Cyber-001",
                "to": "Cyber-002",
                "subject": "Test Subject",
                "content": "This is the message content",
                "timestamp": datetime.now().isoformat()
            }
            msg_file.write_text(json.dumps(msg_data))
            
            # Create loader
            loader = ContentLoader(filesystem_root=tmpdir)
            
            # Test message load
            memory = MessageMemoryBlock(
                from_agent="Cyber-001",
                to_agent="Cyber-002",
                subject="Test Subject",
                preview="This is...",
                full_path=str(msg_file)
            )
            content = loader.load_message_content(memory)
            
            assert "From: Cyber-001" in content
            assert "To: Cyber-002" in content
            assert "Subject: Test Subject" in content
            assert "This is the message content" in content


class TestMemorySelector:
    """Test memory selection algorithms."""
    
    def test_priority_selection(self):
        """Test that critical memories are always selected."""
        # Create memories with different priorities
        memories = [
            FileMemoryBlock(location="/critical.py", priority=Priority.CRITICAL),
            FileMemoryBlock(location="/high.py", priority=Priority.HIGH),
            FileMemoryBlock(location="/medium.py", priority=Priority.MEDIUM),
            FileMemoryBlock(location="/low.py", priority=Priority.LOW),
        ]
        
        # Create selector with minimal token budget
        loader = ContentLoader(filesystem_root="/")
        builder = ContextBuilder(loader)
        selector = MemorySelector(builder)
        
        # Select with very small budget (should still include critical)
        selected = selector.select_memories(memories, max_tokens=100)
        
        # Critical should always be included
        assert any(m.priority == Priority.CRITICAL for m in selected)
    
    def test_relevance_scoring(self):
        """Test relevance-based selection."""
        memories = [
            FileMemoryBlock(location="/auth/login.py"),
            FileMemoryBlock(location="/database/models.py"),
            FileMemoryBlock(location="/auth/permissions.py"),
        ]
        
        loader = ContentLoader(filesystem_root="/")
        builder = ContextBuilder(loader)
        selector = MemorySelector(builder)
        
        # Select with task context
        selected = selector.select_memories(
            memories,
            max_tokens=1000,
            current_task="implement authentication system",
            selection_strategy="relevant"
        )
        
        # Auth-related files should score higher
        auth_files = [m for m in selected if "auth" in m.location]
        assert len(auth_files) >= 1


class TestEnvironmentScanner:
    """Test filesystem environment scanning."""
    
    def test_scan_inbox(self):
        """Test scanning inbox for messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "Cyber-001"
            shared = Path(tmpdir) / "shared"
            inbox = home / "inbox"
            inbox.mkdir(parents=True)
            shared.mkdir(parents=True)
            
            # Create a message
            msg_file = inbox / "msg001.msg"
            msg_data = {
                "from": "subspace",
                "to": "Cyber-001",
                "subject": "Test Task",
                "content": "Please analyze this"
            }
            msg_file.write_text(json.dumps(msg_data))
            
            # Scan
            scanner = EnvironmentScanner(home, shared)
            memories = scanner.scan_environment()
            
            # Should find message
            message_memories = [m for m in memories if isinstance(m, MessageMemoryBlock)]
            assert len(message_memories) == 1
            assert message_memories[0].subject == "Test Task"
            assert not message_memories[0].read
            
            # Should also create observation
            observations = [m for m in memories if isinstance(m, ObservationMemoryBlock)]
            message_observations = [o for o in observations if o.observation_type == "message_arrived"]
            assert len(message_observations) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])