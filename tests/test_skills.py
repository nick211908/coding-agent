from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.config import Config
from context.manager import ContextManager
from prompts.system import get_system_prompt
from skills.discovery import SkillDiscoveryManager
from skills.models import SkillDefinition
from skills.registry import SkillRegistry


class SkillDiscoveryTests(unittest.TestCase):
    def test_discover_skill_reads_metadata_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".ai-agent" / "skills" / "debugging"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "# Debugging\nFollow the debugging workflow.",
                encoding="utf-8",
            )
            (skill_dir / "skill.toml").write_text(
                'name = "debug-workflow"\n'
                'description = "Structured debugging instructions."\n'
                'triggers = ["debug", "trace"]\n',
                encoding="utf-8",
            )

            config = Config(cwd=root)
            registry = SkillRegistry(config)
            manager = SkillDiscoveryManager(config, registry)

            manager.discover_from_directory(root)

            skills = registry.get_skills()
            self.assertEqual(len(skills), 1)
            self.assertEqual(skills[0].name, "debug-workflow")
            self.assertEqual(skills[0].triggers, ["debug", "trace"])
            self.assertIn("Follow the debugging workflow.", skills[0].content)


class SkillRegistryTests(unittest.TestCase):
    def test_active_skills_match_triggers_and_always_loaded(self) -> None:
        config = Config(
            cwd=Path.cwd(),
            always_loaded_skills=["code-review"],
        )
        registry = SkillRegistry(config)
        registry.register(
            SkillDefinition(
                name="code-review",
                path=Path("SKILL.md"),
                content="Review code carefully.",
            )
        )
        registry.register(
            SkillDefinition(
                name="debugging",
                path=Path("SKILL.md"),
                content="Debug systematically.",
                triggers=["debug", "error"],
            )
        )

        active = registry.get_active_skills("Please debug this failing request")

        self.assertEqual([skill.name for skill in active], ["code-review", "debugging"])


class PromptSkillTests(unittest.TestCase):
    def test_prompt_lists_available_skills_and_loads_matching_content(self) -> None:
        config = Config(cwd=Path.cwd())
        available_skill = SkillDefinition(
            name="debugging",
            path=Path("SKILL.md"),
            content="# Debugging\nUse the debugger first.",
            description="Guidance for debugging tasks.",
            triggers=["debug"],
        )

        manager = ContextManager(
            config=config,
            user_memory=None,
            tools=[],
            skills=[available_skill],
        )
        manager.add_user_message("debug the failing code path")

        system_prompt = manager.get_messages()[0]["content"]

        self.assertIn("## Available Skills", system_prompt)
        self.assertIn("**debugging**: Guidance for debugging tasks.", system_prompt)
        self.assertIn("## Loaded Skill Instructions", system_prompt)
        self.assertIn("Use the debugger first.", system_prompt)

    def test_prompt_excludes_unmatched_skill_content(self) -> None:
        config = Config(cwd=Path.cwd())
        skill = SkillDefinition(
            name="release",
            path=Path("SKILL.md"),
            content="# Release\nPrepare the release checklist.",
            description="Release process steps.",
            triggers=["release"],
        )

        prompt = get_system_prompt(
            config,
            user_memory=None,
            tools=[],
            available_skills=[skill],
            active_skills=[],
        )

        self.assertIn("## Available Skills", prompt)
        self.assertNotIn("## Loaded Skill Instructions", prompt)
        self.assertNotIn("Prepare the release checklist.", prompt)


if __name__ == "__main__":
    unittest.main()
