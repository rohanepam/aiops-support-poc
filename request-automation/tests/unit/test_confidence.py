from domain.confidence import score_confidence
from domain.models import Ambiguity, Intent, ResolvedEntities


def test_full_create_user_scores_high():
    entities = ResolvedEntities(
        username="APP_READONLY",
        database="DEVDB",
        role="Read Only",
        hostname="dev-oracle-01",
        environment="non-production",
    )
    score, missing = score_confidence(Intent.CREATE_USER, entities, [])
    assert missing == []
    assert score >= 90


def test_missing_role_scores_low():
    entities = ResolvedEntities(username="APP01", database="DEVDB", role=None, hostname="dev-oracle-01")
    score, missing = score_confidence(Intent.CREATE_USER, entities, [])
    assert "role" in missing
    assert score < 70


def test_ambiguity_reduces_score():
    entities = ResolvedEntities(username="admin", database="PROD", role=None, hostname=None)
    amb = [Ambiguity(field="database", raw_value="PROD", candidates=[{"hostname": "a"}, {"hostname": "b"}])]
    score, _ = score_confidence(Intent.RESET_PASSWORD, entities, amb)
    assert score < 80
