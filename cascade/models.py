from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ImpactReport:
    source_urn: str
    changes: list[dict[str, Any]]
    downstream: list[dict[str, Any]]
    ml_impact: list[dict[str, Any]]
    severity: str
    remediations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
