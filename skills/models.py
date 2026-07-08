from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SkillDefinition:
    name: str
    path: Path
    content: str
    description: str | None = None
    triggers: list[str] = field(default_factory=list)
    always_include: bool = False
