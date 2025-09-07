"""Test knowledge and CBR export structure with path-based IDs."""

import unittest
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
from src.mind_swarm.utils.id_policy import normalize_knowledge_id, normalize_cbr_case_id


class TestExportStructure(unittest.TestCase):
    """Test export structure for knowledge and CBR."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.subspace_root = Path(self.temp_dir) / "subspace"
        self.export_dir = Path(self.temp_dir) / "exports"
        self.subspace_root.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('scripts.export_knowledge.KnowledgeHandler')
    async def test_knowledge_export_preserves_path_ids(self, mock_handler_class):
        """Test that knowledge export preserves path-based IDs in filenames and metadata."""
        # Mock knowledge handler
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        # Create test documents with path-based IDs
        test_docs = [
            {
                'id': 'templates/guides/onboarding.md',
                'content': 'title: Onboarding Guide\ncontent: Welcome to the system',
                'metadata': {
                    'category': 'guides',
                    'tags': ['onboarding', 'tutorial'],
                    'created_by': 'system'
                },
                'collection': 'shared'
            },
            {
                'id': 'library/sections/python/asyncio.md',
                'content': 'title: AsyncIO Guide\ncontent: Python async programming',
                'metadata': {
                    'category': 'python',
                    'tags': ['python', 'async'],
                    'created_by': 'cyber-1'
                },
                'collection': 'shared'
            },
            {
                'id': 'community/prompts/summarization',
                'content': 'title: Summarization Prompts\ncontent: Effective summarization techniques',
                'metadata': {
                    'category': 'prompts',
                    'tags': ['prompts', 'nlp'],
                    'created_by': 'cyber-2'
                },
                'collection': 'shared'
            }
        ]
        
        # Configure mock to return test docs
        mock_handler.export_all_knowledge = AsyncMock(return_value=test_docs)
        
        # Create exporter and run export
        exporter = KnowledgeExporter(self.subspace_root, self.export_dir)
        stats = await exporter.export_all_knowledge(include_personal=False, include_cbr=False)
        
        # Verify export created files with path-based IDs as filenames
        export_subdir = Path(stats['export_dir'])
        all_knowledge_dir = export_subdir / 'all'
        
        # Check that files were created with proper naming
        expected_files = [
            'templates__guides__onboarding.md.yaml',
            'library__sections__python__asyncio.md.yaml',
            'community__prompts__summarization.yaml'
        ]
        
        for expected_file in expected_files:
            file_path = all_knowledge_dir / expected_file
            self.assertTrue(file_path.exists(), f"Expected file {expected_file} not found")
            
            # Verify metadata contains original path-based ID
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                self.assertIn('_export_metadata', data)
                
                # Extract original ID from filename
                original_id = expected_file.replace('__', '/').replace('.yaml', '')
                if original_id.endswith('.md'):
                    # Keep the .md extension in the ID
                    pass
                
                self.assertEqual(
                    data['_export_metadata']['id'],
                    original_id.replace('__', '/'),
                    f"ID mismatch in {expected_file}"
                )

    @patch('scripts.export_knowledge.KnowledgeHandler')
    async def test_cbr_export_prefers_case_path(self, mock_handler_class):
        """Test that CBR export prefers case_path over case_id for filenames and IDs."""
        # Mock knowledge handler
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        mock_handler.export_all_knowledge = AsyncMock(return_value=[])
        
        # Mock ChromaDB client and collections
        mock_client = Mock()
        mock_handler.chroma_client = mock_client
        
        # Create mock shared CBR collection
        mock_shared_collection = Mock()
        mock_client.get_collection.return_value = mock_shared_collection
        
        # Test cases with both case_path and regular IDs
        test_cases = {
            'ids': [
                'cbr_cyber1_abc123_1234567890',  # Generated ID
                'cbr_cyber2_def456_1234567891',  # Generated ID with case_path
                'cases/devops/deploy/rollout-v1'  # Path-based ID
            ],
            'documents': [
                json.dumps({
                    'problem_context': 'System slow',
                    'solution': 'Optimize queries',
                    'outcome': 'Performance improved'
                }),
                json.dumps({
                    'problem_context': 'Deploy failed',
                    'solution': 'Fix config',
                    'outcome': 'Deploy successful'
                }),
                json.dumps({
                    'problem_context': 'Rollout strategy',
                    'solution': 'Blue-green deployment',
                    'outcome': 'Zero downtime'
                })
            ],
            'metadatas': [
                {'success_score': 0.9},  # No case_path
                {'success_score': 0.8, 'case_path': 'DevOps/Deploy/Fix Config v2'},  # Has case_path
                {'success_score': 0.95, 'case_path': 'DevOps/Deploy/Rollout v1'}  # Has case_path
            ]
        }
        
        mock_shared_collection.get.return_value = test_cases
        
        # Create exporter and run export
        exporter = KnowledgeExporter(self.subspace_root, self.export_dir)
        stats = await exporter.export_all_knowledge(include_personal=False, include_cbr=True)
        
        # Verify CBR export structure
        export_subdir = Path(stats['export_dir'])
        cbr_shared_dir = export_subdir / 'cbr_cases' / 'shared'
        
        # Check expected files based on ID normalization
        expected_files = [
            ('cbr_cyber1_abc123_1234567890.yaml', 'cbr_cyber1_abc123_1234567890'),  # No case_path, use original
            ('cases__devops__deploy__fix-config-v2.yaml', 'cases/devops/deploy/fix-config-v2'),  # Normalized from case_path
            ('cases__devops__deploy__rollout-v1.yaml', 'cases/devops/deploy/rollout-v1')  # Already normalized
        ]
        
        for filename, expected_id in expected_files:
            file_path = cbr_shared_dir / filename
            self.assertTrue(file_path.exists(), f"Expected CBR file {filename} not found")
            
            # Verify metadata
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                self.assertIn('_export_metadata', data)
                self.assertEqual(
                    data['_export_metadata']['id'],
                    expected_id,
                    f"ID mismatch in {filename}"
                )
                
                # Verify case_path is preserved in metadata when present
                if 'Fix Config' in filename or 'rollout' in filename:
                    self.assertIsNotNone(data['_export_metadata'].get('case_path'))

    def test_id_normalization(self):
        """Test ID normalization functions."""
        # Test knowledge ID normalization
        self.assertEqual(
            normalize_knowledge_id('templates', 'Guides/Onboarding.md'),
            'templates/guides/onboarding.md'
        )
        self.assertEqual(
            normalize_knowledge_id('library/sections', 'Python/AsyncIO.md'),
            'library/sections/python/asyncio.md'
        )
        
        # Test CBR case ID normalization
        self.assertEqual(
            normalize_cbr_case_id('DevOps/Deploy/Rollout Strategy v1'),
            'cases/devops/deploy/rollout-strategy-v1'
        )
        self.assertEqual(
            normalize_cbr_case_id('cases/devops/deploy/fix-config'),
            'cases/devops/deploy/fix-config'
        )
        # Non-path IDs should remain unchanged
        self.assertEqual(
            normalize_cbr_case_id('cbr_cyber1_abc123_1234567890'),
            'cbr_cyber1_abc123_1234567890'
        )


if __name__ == '__main__':
    import asyncio
    
    # Create async test runner
    def run_async_test(test_func):
        """Helper to run async test functions."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(test_func())
        finally:
            loop.close()
    
    # Patch unittest to handle async tests
    original_run = unittest.TestCase.run
    
    def async_test_wrapper(self, result=None):
        """Wrapper to handle async test methods."""
        test_method = getattr(self, self._testMethodName)
        if asyncio.iscoroutinefunction(test_method):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(test_method())
            finally:
                loop.close()
        else:
            original_run(self, result)
    
    unittest.TestCase.run = async_test_wrapper
    
    # Run tests
    unittest.main()