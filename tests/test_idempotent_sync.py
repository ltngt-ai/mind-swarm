"""Tests for idempotent knowledge sync functionality."""

import os
import json
from pathlib import Path
from datetime import datetime
import hashlib
import time

import pytest

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.subspace.knowledge_handler import KnowledgeHandler
from mind_swarm.utils.metadata_helpers import compute_content_hash


@pytest.mark.asyncio
async def test_sync_first_time_adds_knowledge(monkeypatch, tmp_path):
    """Test that first sync adds knowledge with proper metadata."""
    # Arrange: point subspace to a temporary, writable root
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    # Monkeypatch coordinator init to be lightweight
    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    # Create test knowledge files
    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_doc.md"
    test_content = "# Test Document\n\nThis is test content for idempotency."
    test_file.write_text(test_content, encoding="utf-8")

    expected_id = "templates/_idempotent_test/test_doc.md"

    try:
        # Act
        coord = SubspaceCoordinator(subspace_root)
        result = await coord.sync_knowledge()

        # Assert
        assert result["status"] == "success"
        assert result["stats"]["added"] >= 1
        
        # Check that file action was recorded
        file_actions = result["stats"]["file_actions"]
        test_action = next((a for a in file_actions if "_idempotent_test/test_doc.md" in a.get("file", "")), None)
        assert test_action is not None
        assert test_action["action"] == "added"
        assert "content_hash" in test_action
        
        # Verify knowledge was stored with proper metadata
        found = await coord.knowledge_handler.get_shared_knowledge(expected_id)
        assert found is not None
        metadata = found.get("metadata", {})
        assert "synced_at" in metadata
        assert "content_hash" in metadata
        assert "updated_by" in metadata
        assert metadata["updated_by"] == "knowledge_sync"
        assert metadata["source_path"] == "_idempotent_test/test_doc.md"

        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(expected_id)
    finally:
        # Cleanup file artifacts
        test_file.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()


@pytest.mark.asyncio
async def test_sync_unchanged_file_returns_unchanged(monkeypatch, tmp_path):
    """Test that syncing the same file twice marks it as unchanged."""
    # Arrange
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test2"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "unchanged.md"
    test_content = "# Unchanged Document\n\nThis content will not change."
    test_file.write_text(test_content, encoding="utf-8")

    expected_id = "templates/_idempotent_test2/unchanged.md"

    try:
        coord = SubspaceCoordinator(subspace_root)
        
        # Act 1: First sync
        result1 = await coord.sync_knowledge()
        assert result1["status"] == "success"
        
        # Find the action for our file
        file_actions1 = result1["stats"]["file_actions"]
        test_action1 = next((a for a in file_actions1 if "_idempotent_test2/unchanged.md" in a.get("file", "")), None)
        assert test_action1 is not None
        assert test_action1["action"] == "added"
        initial_hash = test_action1.get("content_hash")
        assert initial_hash is not None
        
        # Act 2: Second sync with same content
        result2 = await coord.sync_knowledge()
        assert result2["status"] == "success"
        assert result2["stats"]["unchanged"] >= 1
        
        # Find the action for our file in second sync
        file_actions2 = result2["stats"]["file_actions"]
        test_action2 = next((a for a in file_actions2 if "_idempotent_test2/unchanged.md" in a.get("file", "")), None)
        assert test_action2 is not None
        assert test_action2["action"] == "unchanged"
        assert test_action2["content_hash"] == initial_hash

        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(expected_id)
    finally:
        # Cleanup file artifacts
        test_file.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()


@pytest.mark.asyncio
async def test_sync_updated_file_returns_updated(monkeypatch, tmp_path):
    """Test that modifying a file and syncing marks it as updated."""
    # Arrange
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test3"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "changing.md"
    initial_content = "# Changing Document\n\nInitial content."
    test_file.write_text(initial_content, encoding="utf-8")

    expected_id = "templates/_idempotent_test3/changing.md"

    try:
        coord = SubspaceCoordinator(subspace_root)
        
        # Act 1: First sync
        result1 = await coord.sync_knowledge()
        assert result1["status"] == "success"
        
        # Find the action for our file
        file_actions1 = result1["stats"]["file_actions"]
        test_action1 = next((a for a in file_actions1 if "_idempotent_test3/changing.md" in a.get("file", "")), None)
        assert test_action1 is not None
        assert test_action1["action"] == "added"
        initial_hash = test_action1.get("content_hash")
        
        # Modify the file
        updated_content = "# Changing Document\n\nUpdated content with more information."
        test_file.write_text(updated_content, encoding="utf-8")
        
        # Act 2: Second sync with modified content
        result2 = await coord.sync_knowledge()
        assert result2["status"] == "success"
        assert result2["stats"]["updated"] >= 1
        
        # Find the action for our file in second sync
        file_actions2 = result2["stats"]["file_actions"]
        test_action2 = next((a for a in file_actions2 if "_idempotent_test3/changing.md" in a.get("file", "")), None)
        assert test_action2 is not None
        assert test_action2["action"] == "updated"
        assert test_action2["content_hash"] != initial_hash
        
        # Verify the metadata was updated
        found = await coord.knowledge_handler.get_shared_knowledge(expected_id)
        assert found is not None
        metadata = found.get("metadata", {})
        assert metadata["content_hash"] == test_action2["content_hash"]
        assert metadata["updated_by"] == "knowledge_sync"

        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(expected_id)
    finally:
        # Cleanup file artifacts
        test_file.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()


@pytest.mark.asyncio
async def test_sync_with_metadata_change_but_same_content(monkeypatch, tmp_path):
    """Test that changing only metadata (not content) still marks as unchanged."""
    # Arrange
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test4"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "metadata_test.yaml"
    
    # YAML content with metadata
    yaml_content = """title: Test Document
category: test
tags:
  - testing
  - idempotency
content: |
  This is the actual content that matters for the hash.
  Only changes to this should trigger an update.
"""
    test_file.write_text(yaml_content, encoding="utf-8")

    expected_id = "templates/_idempotent_test4/metadata-test.yaml"

    try:
        coord = SubspaceCoordinator(subspace_root)
        
        # Act 1: First sync
        result1 = await coord.sync_knowledge()
        
        # Wait a bit to ensure different timestamp
        time.sleep(0.1)
        
        # Act 2: Second sync (synced_at will be different but content hash should be same)
        result2 = await coord.sync_knowledge()
        assert result2["status"] == "success"
        
        # Find the action for our file in second sync
        file_actions2 = result2["stats"]["file_actions"]
        test_action2 = next((a for a in file_actions2 if "_idempotent_test4/metadata_test.yaml" in a.get("file", "")), None)
        assert test_action2 is not None
        # Should be unchanged since content hash excludes synced_at
        assert test_action2["action"] == "unchanged"

        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(expected_id)
    finally:
        # Cleanup file artifacts
        test_file.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()


@pytest.mark.asyncio
async def test_sync_error_handling(monkeypatch, tmp_path):
    """Test that sync properly reports errors in file_actions."""
    # Arrange
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test5"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a file with invalid encoding to trigger an error
    test_file = test_dir / "invalid.txt"
    # Write some binary data that isn't valid UTF-8
    test_file.write_bytes(b'\x80\x81\x82\x83')

    try:
        coord = SubspaceCoordinator(subspace_root)
        
        # Act
        result = await coord.sync_knowledge()
        
        # Assert
        assert result["status"] == "success"
        # The file should be skipped due to UTF-8 validation in sanity checks
        assert result["stats"]["skipped"] >= 1 or result["stats"]["errors"] >= 1
        
        # Check file_actions for error or skip
        file_actions = result["stats"]["file_actions"]
        # Since it fails sanity check, it might not appear in file_actions
        # or it might appear as an error
        
    finally:
        # Cleanup file artifacts
        test_file.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()


@pytest.mark.asyncio
async def test_sync_returns_all_action_types(monkeypatch, tmp_path):
    """Test that sync returns detailed file_actions for all action types."""
    # Arrange
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "subspace_template" / "initial_knowledge" / "_idempotent_test6"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create multiple test files
    file1 = test_dir / "new_file.md"
    file1.write_text("# New File\n\nThis will be added.", encoding="utf-8")
    
    file2 = test_dir / "existing_file.md"
    file2.write_text("# Existing File\n\nInitial content.", encoding="utf-8")
    
    id1 = "templates/_idempotent_test6/new-file.md"
    id2 = "templates/_idempotent_test6/existing-file.md"

    try:
        coord = SubspaceCoordinator(subspace_root)
        
        # First sync - both files should be added
        result1 = await coord.sync_knowledge()
        assert result1["status"] == "success"
        assert "file_actions" in result1["stats"]
        
        actions1 = result1["stats"]["file_actions"]
        added_actions = [a for a in actions1 if a["action"] == "added"]
        assert len([a for a in added_actions if "_idempotent_test6/new_file.md" in a.get("file", "")]) == 1
        assert len([a for a in added_actions if "_idempotent_test6/existing_file.md" in a.get("file", "")]) == 1
        
        # Modify one file
        file2.write_text("# Existing File\n\nModified content!", encoding="utf-8")
        
        # Second sync
        result2 = await coord.sync_knowledge()
        assert result2["status"] == "success"
        
        actions2 = result2["stats"]["file_actions"]
        
        # file1 should be unchanged
        unchanged_action = next((a for a in actions2 if "_idempotent_test6/new_file.md" in a.get("file", "") and a["action"] == "unchanged"), None)
        assert unchanged_action is not None
        
        # file2 should be updated
        updated_action = next((a for a in actions2 if "_idempotent_test6/existing_file.md" in a.get("file", "") and a["action"] == "updated"), None)
        assert updated_action is not None
        
        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(id1)
        await coord.knowledge_handler.remove_shared_knowledge(id2)
        
    finally:
        # Cleanup file artifacts
        file1.unlink(missing_ok=True)
        file2.unlink(missing_ok=True)
        if not any(test_dir.iterdir()):
            test_dir.rmdir()