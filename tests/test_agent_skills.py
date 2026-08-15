import tempfile
import unittest
from pathlib import Path

from jarvis_agent.config import SKILLS_DIR
from jarvis_agent.skills import (
    Skill,
    SkillNotFoundError,
    discover_skills,
    format_skills_catalog,
    load_skill,
)

_SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

{body}
"""


def _write_skill(skills_dir: Path, dirname: str, name: str, description: str, body: str) -> None:
    skill_dir = skills_dir / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        _SKILL_TEMPLATE.format(name=name, description=description, body=body)
    )


class DiscoverSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.skills_dir = Path(self._tmpdir.name)

    def test_discovers_multiple_valid_skills(self) -> None:
        _write_skill(self.skills_dir, "pdf", "pdf-generation", "Make PDFs.", "# PDF\nDo the pdf thing.")
        _write_skill(self.skills_dir, "csv", "csv-analysis", "Analyze CSVs.", "# CSV\nDo the csv thing.")

        skills = discover_skills(self.skills_dir)

        self.assertEqual(set(skills), {"pdf-generation", "csv-analysis"})
        self.assertEqual(skills["pdf-generation"].description, "Make PDFs.")
        self.assertIn("Do the pdf thing.", skills["pdf-generation"].instructions)
        self.assertEqual(skills["csv-analysis"].description, "Analyze CSVs.")
        self.assertIn("Do the csv thing.", skills["csv-analysis"].instructions)

    def test_subdirectory_without_skill_md_is_skipped(self) -> None:
        (self.skills_dir / "empty-dir").mkdir()
        _write_skill(self.skills_dir, "pdf", "pdf-generation", "Make PDFs.", "body")

        skills = discover_skills(self.skills_dir)

        self.assertEqual(set(skills), {"pdf-generation"})

    def test_missing_closing_delimiter_raises_value_error(self) -> None:
        skill_dir = self.skills_dir / "broken"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: broken\ndescription: oops\n\nbody without closing delimiter\n"
        )

        with self.assertRaises(ValueError):
            discover_skills(self.skills_dir)

    def test_missing_name_or_description_raises_value_error(self) -> None:
        skill_dir = self.skills_dir / "incomplete"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: incomplete\n---\n\nbody\n")

        with self.assertRaises(ValueError):
            discover_skills(self.skills_dir)

    def test_nonexistent_directory_returns_empty_dict(self) -> None:
        skills = discover_skills(self.skills_dir / "does-not-exist")
        self.assertEqual(skills, {})


class FormatSkillsCatalogTests(unittest.TestCase):
    def test_empty_dict_reports_no_skills_available(self) -> None:
        self.assertEqual(format_skills_catalog({}), "(no skills available)")

    def test_populated_dict_renders_one_sorted_line_per_skill(self) -> None:
        skills = {
            "zebra": Skill(name="zebra", description="Zebra things.", instructions="..."),
            "alpha": Skill(name="alpha", description="Alpha things.", instructions="..."),
        }

        catalog = format_skills_catalog(skills)

        self.assertEqual(
            catalog.splitlines(),
            ["- alpha: Alpha things.", "- zebra: Zebra things."],
        )


class LoadSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills = {
            "pdf-generation": Skill(
                name="pdf-generation",
                description="Make PDFs.",
                instructions="Full pdf instructions here.",
            ),
        }

    def test_returns_instructions_for_known_skill(self) -> None:
        self.assertEqual(load_skill(self.skills, "pdf-generation"), "Full pdf instructions here.")

    def test_raises_skill_not_found_error_listing_available_names(self) -> None:
        with self.assertRaises(SkillNotFoundError) as cm:
            load_skill(self.skills, "unknown-skill")

        self.assertIn("pdf-generation", str(cm.exception))


class RealSkillsDirectoryIntegrationTest(unittest.TestCase):
    """Light integration check that the shipped SKILL.md is well-formed."""

    def test_pdf_generation_skill_is_well_formed(self) -> None:
        skills = discover_skills(SKILLS_DIR)

        self.assertIn("pdf-generation", skills)
        skill = skills["pdf-generation"]
        self.assertTrue(skill.description.strip())
        self.assertTrue(skill.instructions.strip())


if __name__ == "__main__":
    unittest.main()
