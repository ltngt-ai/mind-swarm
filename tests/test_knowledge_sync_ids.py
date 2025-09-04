import os
from pathlib import Path

import pytest

from mind_swarm.subspace.coordinator import SubspaceCoordinator
from mind_swarm.subspace.knowledge_handler import KnowledgeHandler


@pytest.mark.asyncio
async def test_sync_uses_templates_namespace(monkeypatch, tmp_path):
    # Arrange: point subspace to a temporary, writable root
    subspace_root = tmp_path / "subspace"
    subspace_root.mkdir(parents=True, exist_ok=True)

    # Monkeypatch coordinator init to be lightweight and avoid heavy subsystems
    def fake_init(self, root_path: Path | None = None):
        self.subspace = type("S", (), {"root_path": root_path})
        self.knowledge_handler = KnowledgeHandler(root_path)
        self.cbr_handler = None

    monkeypatch.setattr(SubspaceCoordinator, "__init__", fake_init)

    # Create a temporary knowledge file under the repo's template dir
    repo_root = Path(__file__).resolve().parents[1]
    initial_knowledge_dir = repo_root / "subspace_template" / "initial_knowledge" / "_sync_test"
    initial_knowledge_dir.mkdir(parents=True, exist_ok=True)
    test_file = initial_knowledge_dir / "Onboarding Guide.md"
    test_file.write_text("# Onboarding Guide\n\nWelcome!", encoding="utf-8")

    # Expected ID after sync
    expected_id = "templates/_sync_test/onboarding-guide.md"

    try:
        # Act
        coord = SubspaceCoordinator(subspace_root)
        result = await coord.sync_knowledge()

        # Assert: knowledge exists under normalized, namespaced ID
        found = await coord.knowledge_handler.get_shared_knowledge(expected_id)
        assert found is not None, f"Knowledge not found for ID: {expected_id}. Sync result: {result}"

        # Cleanup from DB
        await coord.knowledge_handler.remove_shared_knowledge(expected_id)
    finally:
        # Cleanup file artifact
        try:
            test_file.unlink(missing_ok=True)
            # Remove folder if empty
            if not any(initial_knowledge_dir.iterdir()):
                initial_knowledge_dir.rmdir()
        except Exception:
            pass

