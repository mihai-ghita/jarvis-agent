"""Skill discovery and loading from `skills/*/SKILL.md` bundles.

Skills are markdown files with a tiny frontmatter block, discovered by name
and description up front (cheap to keep in the system prompt) and loaded in
full only when the agent asks for them by name (progressive disclosure).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_FRONTMATTER_DELIMITER = "---"


@dataclass(frozen=True)
class Skill:
    """A single skill: its catalog entry plus full instructions."""

    name: str
    description: str
    instructions: str


class SkillNotFoundError(KeyError):
    """Raised when `load_skill` is asked for an unknown skill name."""


def discover_skills(skills_dir: Path) -> dict[str, Skill]:
    """Discover skills from immediate subdirectories of `skills_dir`.

    Each subdirectory containing a `SKILL.md` file is parsed as a skill,
    keyed by the `name` field from its frontmatter. Returns `{}` if
    `skills_dir` doesn't exist.
    """
    if not skills_dir.is_dir():
        return {}

    skills: dict[str, Skill] = {}
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue
        skill = _parse_skill_file(skill_file)
        skills[skill.name] = skill
    return skills


def _parse_skill_file(path: Path) -> Skill:
    """Parse a `SKILL.md` file's frontmatter + body into a `Skill`."""
    text = path.read_text()
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise ValueError(f"{path}: expected file to start with '---' frontmatter")

    frontmatter: dict[str, str] = {}
    body_start = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_DELIMITER:
            body_start = idx + 1
            break
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()

    if body_start is None:
        raise ValueError(f"{path}: frontmatter is missing its closing '---'")

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not name or not description:
        raise ValueError(
            f"{path}: frontmatter must include both 'name' and 'description'"
        )

    instructions = "\n".join(lines[body_start:]).strip()
    return Skill(name=name, description=description, instructions=instructions)


def format_skills_catalog(skills: dict[str, Skill]) -> str:
    """Render a one-line-per-skill catalog, sorted by name."""
    if not skills:
        return "(no skills available)"
    return "\n".join(
        f"- {skill.name}: {skill.description}"
        for skill in sorted(skills.values(), key=lambda s: s.name)
    )


def load_skill(skills: dict[str, Skill], name: str) -> str:
    """Return the full instructions for skill `name`.

    Raises `SkillNotFoundError` (listing available names) if unknown.
    """
    try:
        return skills[name].instructions
    except KeyError:
        available = ", ".join(sorted(skills)) or "(none)"
        raise SkillNotFoundError(
            f"Unknown skill '{name}'. Available skills: {available}"
        ) from None
