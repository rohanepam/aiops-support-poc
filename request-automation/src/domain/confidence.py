from __future__ import annotations

from domain.models import Intent, REQUIRED_ENTITIES, ResolvedEntities


def _amb_field(item: object) -> str | None:
    if isinstance(item, dict):
        value = item.get("field")
        return str(value) if value is not None else None
    return getattr(item, "field", None)


def score_confidence(
    intent: Intent | None,
    entities: ResolvedEntities,
    ambiguities: list,
    *,
    threshold: int = 80,
) -> tuple[int, list[str]]:
    """Pure confidence scoring (0-100). Returns (score, missing_fields)."""
    if intent is None or intent == Intent.UNKNOWN:
        return 10, []

    required = REQUIRED_ENTITIES.get(intent, [])
    missing: list[str] = []
    for field in required:
        value = getattr(entities, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)

    has_db_ambiguity = any(_amb_field(a) == "database" for a in ambiguities)

    # Hostname resolution expected when database was provided
    if entities.database and not entities.hostname and not has_db_ambiguity:
        if "hostname" not in missing:
            missing.append("hostname")

    if not required:
        return 20, missing

    present = len(required) - len([f for f in missing if f in required])
    base = int(100 * (present / len(required)))

    if ambiguities:
        # Each ambiguous field cuts score proportionally
        penalty = min(40, 25 * len(ambiguities))
        base = max(0, base - penalty)

    if missing:
        # Cap below typical auto-proceed threshold when incomplete
        base = min(base, threshold - 1)
        if len(missing) >= 1 and base >= 70:
            base = 65

    if not missing and not ambiguities:
        base = max(base, 90)

    return max(0, min(100, base)), missing
