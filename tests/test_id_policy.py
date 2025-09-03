import pytest

from mind_swarm.utils.id_policy import normalize_cbr_case_id, normalize_knowledge_id


def test_normalize_cbr_case_id_path_like():
    assert normalize_cbr_case_id("DevOps/Deploy/Rollout Strategy v1") == "cases/devops/deploy/rollout-strategy-v1"
    assert normalize_cbr_case_id("/cases/ML/Model V2") == "cases/ml/model-v2"


def test_normalize_cbr_case_id_non_path():
    # Non-path explicit IDs are preserved
    assert normalize_cbr_case_id("cbr_test_abc_123") == "cbr_test_abc_123"


def test_normalize_knowledge_id_templates():
    assert normalize_knowledge_id("templates", "Guides/Onboarding.md") == "templates/guides/onboarding.md"
    assert normalize_knowledge_id("library/sections", "Python/AsyncIO.md") == "library/sections/python/asyncio.md"
