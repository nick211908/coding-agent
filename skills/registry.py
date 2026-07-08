from __future__ import annotations

import logging

from config.config import Config
from skills.models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self, config: Config):
        self.config = config
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        key = skill.name.casefold()
        if key in self._skills:
            logger.warning(f"Overwriting existing skill: {skill.name}")

        self._skills[key] = skill

    def get_skills(self) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if self.config.allowed_skills:
            allowed = {name.casefold() for name in self.config.allowed_skills}
            skills = [skill for skill in skills if skill.name.casefold() in allowed]

        return skills

    def get_active_skills(self, message: str | None = None) -> list[SkillDefinition]:
        if not self.config.skills_enabled:
            return []

        normalized_message = " ".join((message or "").casefold().split())
        always_loaded = {
            name.casefold() for name in self.config.always_loaded_skills
        }

        active_skills: list[SkillDefinition] = []
        for skill in self.get_skills():
            skill_name = skill.name.casefold()
            trigger_match = any(
                trigger.casefold() in normalized_message for trigger in skill.triggers
            )
            name_match = skill_name in normalized_message if normalized_message else False

            if (
                skill.always_include
                or skill_name in always_loaded
                or trigger_match
                or name_match
            ):
                active_skills.append(skill)

        return active_skills
