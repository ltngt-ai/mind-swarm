"""Tests for knowledge sync configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from mind_swarm.utils.knowledge_sync_config import (
    KnowledgeSyncConfig,
    SyncRoot,
    load_knowledge_sync_config,
)


class TestKnowledgeSyncConfig:
    """Test knowledge sync configuration loading and validation."""

    def test_load_default_config(self):
        """Test loading the default configuration file."""
        # Load the actual config file from the project
        config = load_knowledge_sync_config()
        
        assert config.version == "1.0"
        assert len(config.sync_roots) > 0
        assert len(config.include_patterns) > 0
        assert len(config.exclude_patterns) > 0
        assert len(config.security_denylist) > 0
    
    def test_sync_roots_configuration(self):
        """Test sync roots are properly configured."""
        config = load_knowledge_sync_config()
        
        # Find expected roots
        templates_root = config.get_root_by_name("templates")
        assert templates_root is not None
        assert templates_root.id_prefix == "templates/"
        assert templates_root.source_path == "subspace_template/initial_knowledge"
        assert templates_root.enabled is True
        
        library_sections = config.get_root_by_name("library_sections")
        assert library_sections is not None
        assert library_sections.id_prefix == "library/sections/"
        
        library_schemas = config.get_root_by_name("library_schemas") 
        assert library_schemas is not None
        assert library_schemas.id_prefix == "library/schemas/"
        
        community = config.get_root_by_name("community")
        assert community is not None
        assert community.id_prefix == "community/"
        assert community.runtime is True  # Community uses runtime path
    
    def test_enabled_roots_priority_order(self):
        """Test that enabled roots are returned in priority order."""
        config = load_knowledge_sync_config()
        
        enabled_roots = config.get_enabled_roots()
        assert len(enabled_roots) > 0
        
        # Check priority ordering (highest first)
        for i in range(len(enabled_roots) - 1):
            assert enabled_roots[i].priority >= enabled_roots[i + 1].priority
    
    def test_file_inclusion_patterns(self):
        """Test file inclusion pattern matching."""
        config = load_knowledge_sync_config()
        
        # Test common knowledge file types
        assert config.should_include_file(Path("test.md"))
        assert config.should_include_file(Path("test.yaml"))
        assert config.should_include_file(Path("test.yml"))
        assert config.should_include_file(Path("test.txt"))
        assert config.should_include_file(Path("test.json"))
        assert config.should_include_file(Path("test.knowledge"))
        assert config.should_include_file(Path("test.prompt"))
        assert config.should_include_file(Path("test.template"))
        
        # Test that other file types are not included
        assert not config.should_include_file(Path("test.py"))
        assert not config.should_include_file(Path("test.exe"))
        assert not config.should_include_file(Path("test.bin"))
    
    def test_file_exclusion_patterns(self):
        """Test file exclusion pattern matching."""
        config = load_knowledge_sync_config()
        
        # Test excluded patterns
        assert config.should_exclude_file(Path(".git/config"))
        assert config.should_exclude_file(Path("__pycache__/test.pyc"))
        assert config.should_exclude_file(Path("test.pyc"))
        assert config.should_exclude_file(Path(".DS_Store"))
        assert config.should_exclude_file(Path("test.log"))
        assert config.should_exclude_file(Path("test.tmp"))
        assert config.should_exclude_file(Path("test.bak"))
        assert config.should_exclude_file(Path(".tmp_test"))
    
    def test_security_denylist(self):
        """Test security denylist patterns."""
        config = load_knowledge_sync_config()
        
        # Test credentials and secrets
        assert config.is_security_risk(Path(".env"))
        assert config.is_security_risk(Path("config/.env.production"))
        assert config.is_security_risk(Path("secrets/api_key.txt"))
        assert config.is_security_risk(Path("credentials/database.yml"))
        
        # Test private keys and certificates
        assert config.is_security_risk(Path("server.pem"))
        assert config.is_security_risk(Path("private.key"))
        assert config.is_security_risk(Path("cert.crt"))
        assert config.is_security_risk(Path("id_rsa"))
        assert config.is_security_risk(Path("id_ed25519"))
        
        # Test cloud provider files
        assert config.is_security_risk(Path(".aws/credentials"))
        assert config.is_security_risk(Path("service-account.json"))
        
        # Test sensitive paths
        assert config.is_security_risk(Path("private/data.txt"))
        assert config.is_security_risk(Path("confidential/report.md"))
    
    def test_content_filter_patterns(self):
        """Test content filtering for sensitive data."""
        config = load_knowledge_sync_config()
        
        # Test password patterns
        assert config.has_sensitive_content("password: secret123")
        assert config.has_sensitive_content("pwd=mypassword")
        assert config.has_sensitive_content("PASSWD: 'test123'")
        
        # Test API key patterns
        assert config.has_sensitive_content("api_key: sk-1234567890")
        assert config.has_sensitive_content("apikey=abcd1234")
        assert config.has_sensitive_content("API-KEY: test123")
        
        # Test AWS credentials
        assert config.has_sensitive_content('aws_access_key_id="AKIA1234567890')
        assert config.has_sensitive_content('aws_secret_access_key="secret123')
        
        # Test private keys
        assert config.has_sensitive_content("-----BEGIN RSA PRIVATE KEY-----")
        assert config.has_sensitive_content("-----BEGIN EC PRIVATE KEY-----")
        assert config.has_sensitive_content("-----BEGIN OPENSSH PRIVATE KEY-----")
        
        # Test safe content
        assert config.has_sensitive_content("This is safe content") is None
        assert config.has_sensitive_content("# Documentation\n\nSome text") is None
    
    def test_custom_config_loading(self):
        """Test loading a custom configuration file."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "version": "1.0",
                "sync_roots": [
                    {
                        "name": "test_root",
                        "source_path": "test/path",
                        "id_prefix": "test/",
                        "description": "Test root",
                        "enabled": True,
                        "priority": 100
                    }
                ],
                "include_patterns": ["*.md", "*.txt"],
                "exclude_patterns": ["*.tmp"],
                "security_denylist": ["*.key"],
                "content_filters": {
                    "max_file_size": 1000000,
                    "content_denylist": [
                        {
                            "pattern": "test_pattern",
                            "description": "Test pattern"
                        }
                    ]
                },
                "sync_behavior": {"on_conflict": "update"},
                "metadata_defaults": {"source": "test"},
                "logging": {"level": "DEBUG"}
            }
            yaml.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            # Load the custom config
            config = load_knowledge_sync_config(config_path)
            
            assert config.version == "1.0"
            assert len(config.sync_roots) == 1
            assert config.sync_roots[0].name == "test_root"
            assert config.sync_roots[0].id_prefix == "test/"
            assert config.content_filters["max_file_size"] == 1000000
            assert config.has_sensitive_content("test_pattern") == "Test pattern"
        finally:
            # Clean up
            config_path.unlink(missing_ok=True)
    
    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        # Test missing file
        with pytest.raises(FileNotFoundError):
            load_knowledge_sync_config(Path("/nonexistent/config.yaml"))
        
        # Test invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: ][")
            config_path = Path(f.name)
        
        try:
            with pytest.raises(Exception):  # Could be yaml.YAMLError or ValueError
                load_knowledge_sync_config(config_path)
        finally:
            config_path.unlink(missing_ok=True)
        
        # Test missing required fields
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({"version": "1.0"}, f)  # Missing other required fields
            config_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Missing required config fields"):
                load_knowledge_sync_config(config_path)
        finally:
            config_path.unlink(missing_ok=True)
