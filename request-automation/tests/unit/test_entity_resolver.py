from pathlib import Path

from domain.entity_resolver import load_database_lookup, resolve_entities
from domain.models import EntityResult

LOOKUP = load_database_lookup(Path(__file__).resolve().parents[2] / "entity_lookup" / "databases.yaml")


def test_resolve_devdb():
    extracted = EntityResult(username="APP_READONLY", database="DEVDB", role="Read Only")
    resolved, amb = resolve_entities(extracted, LOOKUP)
    assert amb == []
    assert resolved.hostname == "dev-oracle-01"
    assert resolved.environment == "non-production"
    assert resolved.technology == "oracle"


def test_ambiguous_prod_not_guessed():
    extracted = EntityResult(username="admin", database="PROD")
    resolved, amb = resolve_entities(extracted, LOOKUP)
    assert resolved.hostname is None
    assert len(amb) == 1
    assert amb[0].field == "database"
    assert len(amb[0].candidates) == 2
