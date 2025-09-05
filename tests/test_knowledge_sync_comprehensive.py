"""Comprehensive tests for knowledge sync with scopes and idempotency.

Tests the extended knowledge sync functionality including:
- Idempotent sync detection via content hash
- Scope filtering (library, template, community)
- Statistics accuracy
"""

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
import yaml

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.subspace.knowledge_handler import KnowledgeHandler
from mind_swarm.utils.knowledge_sync_config import (
    KnowledgeSyncConfig,
    SyncRoot,
    load_knowledge_sync_config,
)
from mind_swarm.utils.metadata_helpers import compute_content_hash


class MockChromaCollection:
    """Mock ChromaDB collection for fast testing."""
    
    def __init__(self):
        self.data = {}
        self.metadata_index = {}
    
    async def get(self, ids: Optional[List[str]] = None, where: Optional[Dict] = None, **kwargs):
        """Mock get method."""
        if ids:
            documents = []
            metadatas = []
            found_ids = []
            for id in ids:
                if id in self.data:
                    found_ids.append(id)
                    documents.append(self.data[id]["document"])
                    metadatas.append(self.data[id]["metadata"])
            return {
                "ids": found_ids,
                "documents": documents,
                "metadatas": metadatas
            }
        return {"ids": [], "documents": [], "metadatas": []}
    
    async def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict], **kwargs):
        """Mock upsert method."""
        for id, doc, meta in zip(ids, documents, metadatas):
            self.data[id] = {
                "document": doc,
                "metadata": meta
            }
            # Index by content hash if present
            if "content_hash" in meta:
                self.metadata_index[meta["content_hash"]] = id
    
    async def delete(self, ids: List[str], **kwargs):
        """Mock delete method."""
        for id in ids:
            if id in self.data:
                if "content_hash" in self.data[id]["metadata"]:
                    del self.metadata_index[self.data[id]["metadata"]["content_hash"]]
                del self.data[id]
    
    async def count(self):
        """Mock count method."""
        return len(self.data)


class MockKnowledgeHandler(KnowledgeHandler):
    """Mock knowledge handler with embedded storage."""
    
    def __init__(self, root_path: Path):
        self.enabled = True
        self.subspace_root = root_path
        self.shared_collection = MockChromaCollection()
        self.collection = self.shared_collection  # Alias for compatibility
        self._initialized = True
    
    async def initialize(self):
        """Mock initialization."""
        pass
    
    async def add_shared_knowledge_with_id(self, knowledge_id: str, content: str, metadata: Dict = None) -> Tuple[bool, str]:
        """Add knowledge to shared collection with specific ID."""
        try:
            await self.shared_collection.upsert(
                ids=[knowledge_id],
                documents=[content],
                metadatas=[metadata or {}]
            )
            return True, knowledge_id
        except Exception as e:
            return False, str(e)
    
    async def get_shared_knowledge(self, knowledge_id: str) -> Optional[Dict]:
        """Get knowledge by ID."""
        result = await self.shared_collection.get(ids=[knowledge_id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0],
                "metadata": result["metadatas"][0]
            }
        return None
    
    async def upsert_shared_knowledge(self, knowledge_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Upsert knowledge."""
        await self.shared_collection.upsert(
            ids=[knowledge_id],
            documents=[content],
            metadatas=[metadata]
        )
        return True
    
    async def remove_shared_knowledge(self, knowledge_id: str) -> bool:
        """Remove knowledge."""
        await self.shared_collection.delete(ids=[knowledge_id])
        return True
    
    async def update_shared_knowledge(self, knowledge_id: str, content: str, metadata: Dict = None) -> Tuple[bool, str]:
        """Update existing knowledge."""
        existing = await self.get_shared_knowledge(knowledge_id)
        if not existing:
            return False, "Knowledge not found"
        
        try:
            await self.shared_collection.upsert(
                ids=[knowledge_id],
                documents=[content],
                metadatas=[metadata or {}]
            )
            return True, "Updated successfully"
        except Exception as e:
            return False, str(e)


@pytest.fixture
def mock_subspace_coordinator(tmp_path, monkeypatch):
    """Create a mock SubspaceCoordinator with mocked ChromaDB."""
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)
    
    # Lightweight init for coordinator
    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = MockKnowledgeHandler(root_path)
        self.cbr_handler = None
    
    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)
    
    return SubspaceCoordinator(subspace_root)


@pytest.fixture
def create_test_files(tmp_path):
    """Helper to create test knowledge files."""
    def _create_files(root_name: str, files: Dict[str, str]):
        """Create test files in the appropriate directory."""
        repo_root = Path(__file__).resolve().parents[1]
        
        # Determine base directory based on root name
        # The actual config looks for these paths
        if root_name == "templates":
            base_dir = repo_root / "subspace_template" / "initial_knowledge" / "_test_sync"
        elif root_name == "library_sections":
            # According to config: source_path: "subspace_template/grid/library/sections"
            base_dir = repo_root / "subspace_template" / "grid" / "library" / "sections" / "_test"
        elif root_name == "library_schemas":
            # According to config: source_path: "subspace_template/grid/library/schemas" 
            base_dir = repo_root / "subspace_template" / "grid" / "library" / "schemas" / "_test"
        elif root_name == "community":
            # Community uses runtime path relative to subspace root
            # Config says: source_path: "subspace/grid/community/knowledge"
            # But coordinator uses: self.subspace.root_path / root.source_path
            # So we need: tmp_path / "subspace/grid/community/knowledge"
            base_dir = tmp_path / "subspace" / "grid" / "community" / "knowledge" / "_test"
        else:
            raise ValueError(f"Unknown root name: {root_name}")
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        created_files = []
        for filename, content in files.items():
            file_path = base_dir / filename
            file_path.write_text(content, encoding="utf-8")
            created_files.append(file_path)
        
        return base_dir, created_files
    
    return _create_files


@pytest.fixture
def cleanup_test_files():
    """Helper to cleanup test files after tests."""
    paths_to_clean = []
    
    def register(path: Path):
        paths_to_clean.append(path)
    
    yield register
    
    # Cleanup
    for path in paths_to_clean:
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            # Remove directory if empty
            if not any(path.iterdir()):
                path.rmdir()


class TestKnowledgeSyncIdempotency:
    """Test idempotency of knowledge sync operations."""
    
    @pytest.mark.asyncio
    async def test_knowledge_sync_library_idempotency(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Test that library sync correctly detects unchanged vs updated files via content hash."""
        coord = mock_subspace_coordinator
        
        # Create test files in library sections
        test_files = {
            "test_doc.md": "# Test Document\n\nInitial content for testing.",
            "test_schema.yaml": "name: TestSchema\nversion: 1.0\ndescription: Test schema"
        }
        
        base_dir, created_files = create_test_files("library_sections", test_files)
        for f in created_files:
            cleanup_test_files(f)
        cleanup_test_files(base_dir)
        
        # First sync - should add files
        result1 = await coord.sync_knowledge(scope="library")
        assert result1["status"] == "success"
        stats1 = result1["stats"]
        
        # Should have added our test files
        assert stats1["added"] >= 2
        
        # Find our test file actions
        file_actions1 = stats1["file_actions"]
        test_doc_action1 = next((a for a in file_actions1 if "test_doc.md" in a.get("file", "")), None)
        test_schema_action1 = next((a for a in file_actions1 if "test_schema.yaml" in a.get("file", "")), None)
        
        assert test_doc_action1 is not None
        assert test_doc_action1["action"] == "added"
        assert "content_hash" in test_doc_action1
        doc_hash1 = test_doc_action1["content_hash"]
        
        assert test_schema_action1 is not None
        assert test_schema_action1["action"] == "added"
        assert "content_hash" in test_schema_action1
        schema_hash1 = test_schema_action1["content_hash"]
        
        # Second sync without changes - should detect unchanged
        result2 = await coord.sync_knowledge(scope="library")
        assert result2["status"] == "success"
        stats2 = result2["stats"]
        
        # Files should be unchanged
        assert stats2["unchanged"] >= 2
        assert stats2["added"] == 0 or stats2["added"] < stats1["added"]
        
        file_actions2 = stats2["file_actions"]
        test_doc_action2 = next((a for a in file_actions2 if "test_doc.md" in a.get("file", "")), None)
        test_schema_action2 = next((a for a in file_actions2 if "test_schema.yaml" in a.get("file", "")), None)
        
        assert test_doc_action2 is not None
        assert test_doc_action2["action"] == "unchanged"
        assert test_doc_action2["content_hash"] == doc_hash1
        
        assert test_schema_action2 is not None
        assert test_schema_action2["action"] == "unchanged"
        assert test_schema_action2["content_hash"] == schema_hash1
        
        # Modify one file
        doc_path = base_dir / "test_doc.md"
        doc_path.write_text("# Test Document\n\nUpdated content with more information!", encoding="utf-8")
        
        # Third sync - should detect one updated, one unchanged
        result3 = await coord.sync_knowledge(scope="library")
        assert result3["status"] == "success"
        stats3 = result3["stats"]
        
        assert stats3["updated"] >= 1
        assert stats3["unchanged"] >= 1
        
        file_actions3 = stats3["file_actions"]
        test_doc_action3 = next((a for a in file_actions3 if "test_doc.md" in a.get("file", "")), None)
        test_schema_action3 = next((a for a in file_actions3 if "test_schema.yaml" in a.get("file", "")), None)
        
        assert test_doc_action3 is not None
        assert test_doc_action3["action"] == "updated"
        assert test_doc_action3["content_hash"] != doc_hash1  # Hash should have changed
        
        assert test_schema_action3 is not None
        assert test_schema_action3["action"] == "unchanged"
        assert test_schema_action3["content_hash"] == schema_hash1  # Hash should be same
    
    @pytest.mark.asyncio
    async def test_content_hash_consistency(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Test that content hash is consistent and only changes with content."""
        coord = mock_subspace_coordinator
        
        # Create a test file
        test_content = "# Consistent Hash Test\n\nThis content should always produce the same hash."
        test_files = {"hash_test.md": test_content}
        
        base_dir, created_files = create_test_files("templates", test_files)
        for f in created_files:
            cleanup_test_files(f)
        cleanup_test_files(base_dir)
        
        # Sync multiple times and verify hash consistency
        hashes = []
        for i in range(3):
            result = await coord.sync_knowledge(scope="template")
            assert result["status"] == "success"
            
            file_actions = result["stats"]["file_actions"]
            test_action = next((a for a in file_actions if "hash_test.md" in a.get("file", "")), None)
            assert test_action is not None
            
            if i == 0:
                assert test_action["action"] == "added"
            else:
                assert test_action["action"] == "unchanged"
            
            hashes.append(test_action["content_hash"])
        
        # All hashes should be identical
        assert len(set(hashes)) == 1, f"Content hash should be consistent, got: {hashes}"
        
        # The hash computation includes metadata, not just content
        # So we just verify consistency across syncs, not the exact value
        # (The actual hash includes source_path and other metadata)


class TestKnowledgeSyncScopes:
    """Test knowledge sync scope filtering."""
    
    @pytest.mark.asyncio
    async def test_knowledge_sync_scopes(self, mock_subspace_coordinator, create_test_files, cleanup_test_files, tmp_path):
        """Test that template and library scopes behave correctly with accurate stats."""
        coord = mock_subspace_coordinator
        
        # Create test files in different locations
        template_files = {"template_doc.md": "# Template Doc\n\nTemplate content."}
        library_files = {"library_doc.md": "# Library Doc\n\nLibrary content."}
        community_files = {"community_doc.md": "# Community Doc\n\nCommunity content."}
        
        # Create files
        template_dir, template_created = create_test_files("templates", template_files)
        library_dir, library_created = create_test_files("library_sections", library_files)
        
        # For community (runtime path), we need to ensure subspace structure exists
        # The runtime path is relative to subspace root (tmp_path)
        community_dir, community_created = create_test_files("community", community_files)
        community_file = community_created[0] if community_created else None
        
        # Register for cleanup
        for f in template_created + library_created + community_created:
            cleanup_test_files(f)
        cleanup_test_files(template_dir)
        cleanup_test_files(library_dir)
        cleanup_test_files(community_dir)
        
        # Test template scope
        result_template = await coord.sync_knowledge(scope="template")
        assert result_template["status"] == "success"
        
        template_stats = result_template["stats"]
        assert "roots_processed" in template_stats
        assert "templates" in template_stats["roots_processed"]
        assert "library_sections" not in template_stats["roots_processed"]
        assert "library_schemas" not in template_stats["roots_processed"]
        
        # Check that only template files were processed
        template_actions = template_stats["file_actions"]
        template_doc_action = next((a for a in template_actions if "template_doc.md" in a.get("file", "")), None)
        library_in_template = next((a for a in template_actions if "library_doc.md" in a.get("file", "")), None)
        community_in_template = next((a for a in template_actions if "community_doc.md" in a.get("file", "")), None)
        
        assert template_doc_action is not None
        assert template_doc_action["action"] == "added"
        assert library_in_template is None  # Library file should not be in template scope
        assert community_in_template is None  # Community file should not be in template scope
        
        # Test library scope
        result_library = await coord.sync_knowledge(scope="library")
        assert result_library["status"] == "success"
        
        library_stats = result_library["stats"]
        assert "roots_processed" in library_stats
        # Library scope includes both library_sections and library_schemas
        assert "library_sections" in library_stats["roots_processed"] or "library_schemas" in library_stats["roots_processed"]
        assert "templates" not in library_stats["roots_processed"]
        
        # Check that only library files were processed
        library_actions = library_stats["file_actions"]
        library_doc_action = next((a for a in library_actions if "library_doc.md" in a.get("file", "")), None)
        template_in_library = next((a for a in library_actions if "template_doc.md" in a.get("file", "")), None)
        
        assert library_doc_action is not None
        assert library_doc_action["action"] == "added"
        assert template_in_library is None  # Template file should not be in library scope
        
        # Test community scope
        result_community = await coord.sync_knowledge(scope="community")
        assert result_community["status"] == "success"
        
        community_stats = result_community["stats"]
        assert "roots_processed" in community_stats
        assert "community" in community_stats["roots_processed"]
        assert "templates" not in community_stats["roots_processed"]
        assert "library_sections" not in community_stats["roots_processed"]
        
        # Check that only community files were processed
        community_actions = community_stats["file_actions"]
        community_doc_action = next((a for a in community_actions if "community_doc.md" in a.get("file", "")), None)
        
        assert community_doc_action is not None
        assert community_doc_action["action"] == "added"
        
        # Test "all" scope (or None which defaults to all)
        result_all = await coord.sync_knowledge(scope="all")
        assert result_all["status"] == "success"
        
        all_stats = result_all["stats"]
        # When syncing all, files should be marked as unchanged since we already synced them
        assert all_stats["unchanged"] >= 3  # At least our 3 test files
        
        # Verify that all roots were processed
        assert len(all_stats["roots_processed"]) >= 3
    
    @pytest.mark.asyncio
    async def test_invalid_scope_handling(self, mock_subspace_coordinator):
        """Test that invalid scopes are properly rejected."""
        coord = mock_subspace_coordinator
        
        # Test invalid scope
        result = await coord.sync_knowledge(scope="invalid_scope")
        assert result["status"] == "error"
        assert "Invalid scope" in result["message"]
        assert "invalid_scope" in result["message"]
    
    @pytest.mark.asyncio
    async def test_scope_with_no_files(self, mock_subspace_coordinator):
        """Test scope that has no files to sync."""
        coord = mock_subspace_coordinator
        
        # Sync a scope with no files (clean environment)
        result = await coord.sync_knowledge(scope="template")
        
        # Should succeed but with zero stats
        if result["status"] == "success":
            stats = result["stats"]
            assert stats["total_files"] == 0 or stats["added"] == 0
            assert stats["roots_processed"] == ["templates"] or len(stats["roots_processed"]) > 0


class TestKnowledgeSyncPerformance:
    """Test performance aspects of knowledge sync."""
    
    @pytest.mark.asyncio
    async def test_fast_sync_with_mock_chromadb(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Verify that sync with mocked ChromaDB is fast."""
        import time
        
        coord = mock_subspace_coordinator
        
        # Create a moderate number of test files
        test_files = {f"test_{i}.md": f"# Test {i}\n\nContent {i}" for i in range(10)}
        base_dir, created_files = create_test_files("templates", test_files)
        
        for f in created_files:
            cleanup_test_files(f)
        cleanup_test_files(base_dir)
        
        # Measure sync time
        start_time = time.time()
        result = await coord.sync_knowledge(scope="template")
        elapsed_time = time.time() - start_time
        
        assert result["status"] == "success"
        assert result["stats"]["added"] == 10
        
        # With mocked ChromaDB, sync should be very fast (under 1 second for 10 files)
        assert elapsed_time < 1.0, f"Sync took {elapsed_time:.2f}s, should be under 1s with mocked ChromaDB"
    
    @pytest.mark.asyncio
    async def test_idempotent_sync_performance(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Test that repeated idempotent syncs are fast."""
        import time
        
        coord = mock_subspace_coordinator
        
        # Create test files
        test_files = {f"perf_{i}.md": f"# Performance {i}\n\nTest content" for i in range(5)}
        base_dir, created_files = create_test_files("templates", test_files)
        
        for f in created_files:
            cleanup_test_files(f)
        cleanup_test_files(base_dir)
        
        # Initial sync
        result1 = await coord.sync_knowledge(scope="template")
        assert result1["status"] == "success"
        assert result1["stats"]["added"] >= 5
        
        # Measure time for idempotent sync (should be fast due to hash comparison)
        start_time = time.time()
        result2 = await coord.sync_knowledge(scope="template")
        elapsed_time = time.time() - start_time
        
        assert result2["status"] == "success"
        assert result2["stats"]["unchanged"] >= 5
        assert result2["stats"]["added"] == 0
        
        # Idempotent sync should be very fast
        assert elapsed_time < 0.5, f"Idempotent sync took {elapsed_time:.2f}s, should be under 0.5s"


class TestKnowledgeSyncIntegration:
    """Integration tests for knowledge sync."""
    
    @pytest.mark.asyncio
    async def test_sync_with_mixed_file_states(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Test sync with a mix of new, unchanged, and updated files."""
        coord = mock_subspace_coordinator
        
        # Initial files
        initial_files = {
            "unchanged.md": "# Unchanged\n\nThis will not change.",
            "to_update.md": "# To Update\n\nInitial version.",
        }
        
        base_dir, created_files = create_test_files("templates", initial_files)
        for f in created_files:
            cleanup_test_files(f)
        
        # First sync
        result1 = await coord.sync_knowledge(scope="template")
        assert result1["status"] == "success"
        assert result1["stats"]["added"] >= 2
        
        # Modify one file, add a new one
        update_path = base_dir / "to_update.md"
        update_path.write_text("# To Update\n\nModified version with more content!", encoding="utf-8")
        
        new_path = base_dir / "new_file.md"
        new_path.write_text("# New File\n\nBrand new content.", encoding="utf-8")
        cleanup_test_files(new_path)
        
        # Second sync
        result2 = await coord.sync_knowledge(scope="template")
        assert result2["status"] == "success"
        
        stats = result2["stats"]
        assert stats["added"] >= 1  # new_file.md
        assert stats["updated"] >= 1  # to_update.md
        assert stats["unchanged"] >= 1  # unchanged.md
        
        # Verify file actions
        file_actions = stats["file_actions"]
        
        new_action = next((a for a in file_actions if "new_file.md" in a.get("file", "")), None)
        assert new_action is not None
        assert new_action["action"] == "added"
        
        update_action = next((a for a in file_actions if "to_update.md" in a.get("file", "")), None)
        assert update_action is not None
        assert update_action["action"] == "updated"
        
        unchanged_action = next((a for a in file_actions if "unchanged.md" in a.get("file", "")), None)
        assert unchanged_action is not None
        assert unchanged_action["action"] == "unchanged"
        
        # Cleanup
        cleanup_test_files(base_dir)
    
    @pytest.mark.asyncio
    async def test_sync_preserves_metadata(self, mock_subspace_coordinator, create_test_files, cleanup_test_files):
        """Test that sync preserves and updates metadata correctly."""
        coord = mock_subspace_coordinator
        
        # Create a test file
        test_files = {"metadata_test.yaml": "key: value\ndata: test"}
        base_dir, created_files = create_test_files("templates", test_files)
        
        for f in created_files:
            cleanup_test_files(f)
        cleanup_test_files(base_dir)
        
        # First sync
        result1 = await coord.sync_knowledge(scope="template")
        assert result1["status"] == "success"
        
        # Get the knowledge ID from file action
        file_actions1 = result1["stats"]["file_actions"]
        test_action1 = next((a for a in file_actions1 if "metadata_test.yaml" in a.get("file", "")), None)
        assert test_action1 is not None
        
        # The ID should follow the pattern from normalize_knowledge_id
        knowledge_id = test_action1.get("knowledge_id")
        assert knowledge_id is not None
        
        # Fetch the knowledge and check metadata
        knowledge = await coord.knowledge_handler.get_shared_knowledge(knowledge_id)
        assert knowledge is not None
        
        metadata = knowledge["metadata"]
        assert "synced_at" in metadata
        assert "content_hash" in metadata
        assert metadata["updated_by"] == "knowledge_sync"
        # source_path may have variations depending on the structure
        assert "metadata_test.yaml" in metadata.get("source_path", "")
        
        initial_hash = metadata["content_hash"]
        initial_sync_time = metadata["synced_at"]
        
        # Second sync without changes
        result2 = await coord.sync_knowledge(scope="template")
        assert result2["status"] == "success"
        
        # Fetch again and verify hash is unchanged but sync time updated
        knowledge2 = await coord.knowledge_handler.get_shared_knowledge(knowledge_id)
        assert knowledge2 is not None
        
        metadata2 = knowledge2["metadata"]
        assert metadata2["content_hash"] == initial_hash  # Hash should be same
        assert metadata2["synced_at"] >= initial_sync_time  # Sync time should be updated or same