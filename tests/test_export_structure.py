"""Test knowledge and CBR export structure with path-based IDs."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

# Mock ChromaDB before importing the module
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.utils'] = MagicMock()
sys.modules['chromadb.utils.embedding_functions'] = MagicMock()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.export_knowledge import KnowledgeExporter


class TestExportStructure:
    """Test that export structure correctly uses path-based IDs."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.export_dir = Path(self.temp_dir) / "exports"
        self.subspace_root = Path(self.temp_dir) / "subspace"
        yield
        # Cleanup after test
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    @patch('scripts.export_knowledge.KnowledgeHandler')
    async def test_knowledge_export_uses_path_ids(self, mock_handler_class):
        """Test that knowledge export uses path-based IDs for filenames."""
        # Create exporter
        exporter = KnowledgeExporter(self.subspace_root, self.export_dir)
        
        # Mock knowledge handler
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        # Mock ChromaDB client
        mock_handler.chroma_client = Mock()
        mock_handler.chroma_client.list_collections.return_value = []
        
        # Create mock knowledge with path-based IDs
        mock_knowledge = [
            {
                'id': 'templates/guides/onboarding.md',
                'content': '---\ntitle: Onboarding Guide\n---\nContent here',
                'metadata': {
                    'title': 'Onboarding Guide',
                    'category': 'guides',
                    'tags': ['onboarding', 'tutorial']
                },
                'collection': 'shared'
            },
            {
                'id': 'library/sections/debugging-tips',
                'content': '---\ntitle: Debugging Tips\n---\nDebugging content',
                'metadata': {
                    'title': 'Debugging Tips',
                    'category': 'development',
                    'tags': ['debugging']
                },
                'collection': 'shared'
            },
            {
                'id': 'personal/alice/notes/project-plan.md',
                'content': '---\ntitle: Project Plan\n---\nPlanning notes',
                'metadata': {
                    'title': 'Project Plan',
                    'category': 'planning',
                    'created_by': 'Alice-1'
                },
                'collection': 'personal_Alice-1'
            }
        ]
        
        # Mock export_all_knowledge
        mock_handler.export_all_knowledge = AsyncMock(return_value=mock_knowledge)
        
        # Run export
        stats = await exporter.export_all_knowledge(include_cbr=False)
        
        # Verify stats
        assert stats['total_exported'] == 3
        
        # Check that files are created with double underscore for path separators
        export_dirs = list(self.export_dir.iterdir())
        assert len(export_dirs) == 1
        
        export_subdir = export_dirs[0]
        all_knowledge_dir = export_subdir / "all"
        
        # Expected filenames use double underscore for path separators
        expected_files = [
            'templates__guides__onboarding.md.yaml',
            'library__sections__debugging-tips.yaml',
            'personal__alice__notes__project-plan.md.yaml'
        ]
        
        for expected_file in expected_files:
            file_path = all_knowledge_dir / expected_file
            assert file_path.exists(), f"Expected file {expected_file} not found"
            
            # Verify the content has the correct ID in metadata
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                assert '_export_metadata' in data
                
                # Extract original ID from filename
                original_id = expected_file.replace('__', '/').replace('.yaml', '')
                
                assert data['_export_metadata']['id'] == original_id.replace('__', '/'), \
                    f"ID mismatch in {expected_file}"

    @pytest.mark.asyncio
    @patch('scripts.export_knowledge.KnowledgeHandler')
    async def test_cbr_export_prefers_case_path(self, mock_handler_class):
        """Test that CBR export prefers case_path over case_id for filenames and IDs."""
        # Create exporter
        exporter = KnowledgeExporter(self.subspace_root, self.export_dir)
        
        # Mock knowledge handler
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        # Mock export_all_knowledge with at least one document to avoid early return
        mock_handler.export_all_knowledge = AsyncMock(return_value=[
            {'id': 'dummy', 'content': 'dummy', 'metadata': {}, 'collection': 'shared'}
        ])
        
        # Mock ChromaDB client with CBR collections
        mock_handler.chroma_client = Mock()
        
        # Create mock shared CBR collection
        mock_shared_collection = Mock()
        mock_shared_collection.name = "cbr_shared"
        
        # CBR cases with case_path in metadata
        cbr_case_with_path = {
            'problem_context': 'How to set up project',
            'solution': 'Create directory structure',
            'outcome': 'Success'
        }
        
        cbr_case_without_path = {
            'problem_context': 'Debug issue',
            'solution': 'Use debugger',
            'outcome': 'Fixed'
        }
        
        mock_shared_collection.get.return_value = {
            'ids': ['cbr_alice_abc123_1234567890', 'cbr_auto_123_456789'],
            'documents': [
                json.dumps(cbr_case_with_path),
                json.dumps(cbr_case_without_path)
            ],
            'metadatas': [
                {
                    'case_path': 'planning/project-setup',  # Has case_path
                    'cyber_id': 'Alice-1',
                    'success_score': 0.9
                },
                {
                    # No case_path - should use original ID
                    'cyber_id': 'Bob-2',
                    'success_score': 0.8
                }
            ]
        }
        
        mock_handler.chroma_client.get_collection.return_value = mock_shared_collection
        mock_handler.chroma_client.list_collections.return_value = []
        
        # Run export
        stats = await exporter.export_all_knowledge(include_personal=False, include_cbr=True)
        
        # Check CBR stats
        assert 'cbr_stats' in stats
        assert stats['cbr_stats']['shared_cbr'] == 2
        
        # Verify exported CBR files
        export_dirs = list(self.export_dir.iterdir())
        assert len(export_dirs) == 1
        
        export_subdir = export_dirs[0]
        cbr_shared_dir = export_subdir / "cbr_cases" / "shared"
        
        # Check first case (with case_path) - should use normalized path
        case1_file = cbr_shared_dir / "cases__planning__project-setup.yaml"
        assert case1_file.exists(), "CBR case with case_path should use path-based filename"
        
        with open(case1_file, 'r') as f:
            data = yaml.safe_load(f)
            assert '_export_metadata' in data
            assert data['_export_metadata']['id'] == 'cases/planning/project-setup', \
                "CBR export should use normalized path-based ID"
            assert data['_export_metadata']['case_path'] == 'planning/project-setup', \
                "CBR export should preserve original case_path"
        
        # Check second case (without case_path) - should use original ID
        case2_file = cbr_shared_dir / "cbr_auto_123_456789.yaml"
        assert case2_file.exists(), "CBR case without case_path should use original ID"
        
        with open(case2_file, 'r') as f:
            data = yaml.safe_load(f)
            assert '_export_metadata' in data
            assert data['_export_metadata']['id'] == 'cbr_auto_123_456789', \
                "CBR export should preserve auto-generated ID when no case_path"
            assert data['_export_metadata'].get('case_path') is None, \
                "No case_path should be present for auto-generated IDs"

    @pytest.mark.asyncio
    @patch('scripts.export_knowledge.KnowledgeHandler')
    async def test_cbr_personal_export_structure(self, mock_handler_class):
        """Test that personal CBR exports maintain proper structure."""
        # Create exporter
        exporter = KnowledgeExporter(self.subspace_root, self.export_dir)
        
        # Mock knowledge handler
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        # Mock export_all_knowledge with at least one document to avoid early return
        mock_handler.export_all_knowledge = AsyncMock(return_value=[
            {'id': 'dummy', 'content': 'dummy', 'metadata': {}, 'collection': 'shared'}
        ])
        
        # Mock ChromaDB client with personal CBR collection
        mock_handler.chroma_client = Mock()
        
        # Create mock personal CBR collection
        mock_personal_collection = Mock()
        mock_personal_collection.name = "cbr_personal_Alice-1"
        
        cbr_case = {
            'problem_context': 'How to use debugger',
            'solution': 'Set breakpoints and step through',
            'outcome': 'Found the bug'
        }
        
        mock_personal_collection.get.return_value = {
            'ids': ['cbr_alice_def456_1234567891'],
            'documents': [json.dumps(cbr_case)],
            'metadatas': [
                {
                    'case_path': 'tools/debugger-setup',
                    'cyber_id': 'Alice-1',
                    'success_score': 0.95
                }
            ]
        }
        
        # Mock list_collections to return personal collection
        mock_handler.chroma_client.list_collections.return_value = [mock_personal_collection]
        
        # Run export
        stats = await exporter.export_all_knowledge(include_personal=True, include_cbr=True)
        
        # Check CBR stats
        assert 'cbr_stats' in stats
        assert stats['cbr_stats']['personal_cbr']['Alice-1'] == 1
        
        # Verify exported personal CBR file
        export_dirs = list(self.export_dir.iterdir())
        assert len(export_dirs) == 1
        
        export_subdir = export_dirs[0]
        cbr_personal_dir = export_subdir / "cbr_cases" / "personal" / "Alice-1"
        
        # Check case file uses normalized path-based ID
        case_file = cbr_personal_dir / "cases__tools__debugger-setup.yaml"
        assert case_file.exists(), "Personal CBR case should use path-based filename"
        
        with open(case_file, 'r') as f:
            data = yaml.safe_load(f)
            assert '_export_metadata' in data
            assert data['_export_metadata']['id'] == 'cases/tools/debugger-setup', \
                "Personal CBR should use normalized path-based ID"
            assert data['_export_metadata']['cyber'] == 'Alice-1', \
                "Personal CBR should track cyber ownership"


# Tests can be run with: pytest tests/test_export_structure.py -v