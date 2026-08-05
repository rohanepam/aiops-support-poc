from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from domain.models import Ambiguity, EntityResult, ResolvedEntities


def load_database_lookup(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("database lookup YAML must be a mapping of alias → entry")
    return {str(k).upper(): v for k, v in data.items()}


def resolve_entities(
    extracted: EntityResult,
    lookup: dict[str, Any],
) -> tuple[ResolvedEntities, list[Ambiguity]]:
    """Map aliases to canonical hostnames. Never guess on multi-match."""
    ambiguities: list[Ambiguity] = []
    hostname: str | None = extracted.hostname
    environment: str | None = extracted.environment
    technology: str | None = None
    database = extracted.database.strip() if extracted.database and extracted.database.strip() else None

    if database:
        key = database.upper()
        entry = lookup.get(key)
        if entry is None:
            pass
        elif isinstance(entry, list):
            candidates = [dict(c) for c in entry if isinstance(c, dict)]
            if candidates:
                ambiguities.append(
                    Ambiguity(field="database", raw_value=database, candidates=candidates)
                )
            hostname = None
            environment = None
        elif isinstance(entry, dict):
            if "hostname" in entry:
                hostname = entry.get("hostname")
            environment = entry.get("environment") or environment
            technology = entry.get("technology")
        # else: malformed entry — leave unresolved

    resolved = ResolvedEntities(
        username=extracted.username,
        database=database,
        role=extracted.role,
        environment=environment,
        hostname=hostname,
        technology=technology,
        schema_name=extracted.schema_name,
        tablespace=extracted.tablespace,
        tenant=extracted.tenant,
    )
    return resolved, ambiguities
