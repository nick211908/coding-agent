from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    import tomllib as tomli
except ModuleNotFoundError:  # pragma: no cover
    import tomli

from config.config import Config
from config.loader import get_config_dir
from skills.models import SkillDefinition
from skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

SKILL_FILE_NAME = "SKILL.md"
SKILL_METADATA_FILE_NAME = "skill.toml"


class SkillDiscoveryManager:
    def __init__(self, config: Config, registry: SkillRegistry):
        self.config = config
        self.registry = registry

    def _parse_metadata(self, skill_dir: Path) -> dict[str, Any]:
        metadata_path = skill_dir / SKILL_METADATA_FILE_NAME
        if not metadata_path.is_file():
            return {}

        try:
            with open(metadata_path, "rb") as file_obj:
                data = tomli.load(file_obj)
                return data if isinstance(data, dict) else {}
        except (OSError, IOError, tomli.TOMLDecodeError) as error:
            logger.warning(f"Skipping invalid skill metadata {metadata_path}: {error}")
            return {}

    def _infer_description(self, content: str) -> str | None:
        for raw_line in content.splitlines():
            line = raw_line.strip().lstrip("#").strip()
            if line:
                return line[:160]
        return None

    def _load_skill(self, skill_dir: Path) -> SkillDefinition | None:
        skill_path = skill_dir / SKILL_FILE_NAME
        if not skill_path.is_file():
            return None

        try:
            content = skill_path.read_text(encoding="utf-8")
        except (OSError, IOError) as error:
            logger.warning(f"Skipping unreadable skill file {skill_path}: {error}")
            return None

        metadata = self._parse_metadata(skill_dir)
        description = metadata.get("description") or self._infer_description(content)
        triggers = metadata.get("triggers") or []

        if not isinstance(triggers, list):
            logger.warning(f"Ignoring non-list triggers in {skill_dir / SKILL_METADATA_FILE_NAME}")
            triggers = []

        return SkillDefinition(
            name=str(metadata.get("name") or skill_dir.name),
            path=skill_path,
            content=content,
            description=description,
            triggers=[str(trigger) for trigger in triggers],
            always_include=bool(metadata.get("always_include", False)),
        )

    def discover_from_skill_directory(self, skill_directory: Path) -> None:
        if not skill_directory.exists() or not skill_directory.is_dir():
            return

        for skill_dir in skill_directory.iterdir():
            if not skill_dir.is_dir():
                continue

            skill = self._load_skill(skill_dir)
            if skill:
                self.registry.register(skill)

    def discover_from_directory(self, directory: Path) -> None:
        self.discover_from_skill_directory(directory / ".ai-agent" / "skills")

    def discover_all(self) -> None:
        self.discover_from_directory(get_config_dir())

        for skill_dir in self.config.extra_skill_dirs:
            self.discover_from_skill_directory(skill_dir)

        self.discover_from_directory(self.config.cwd)
