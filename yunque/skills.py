"""Habilidades (skills): instrucciones detalladas que la IA carga solo cuando las necesita.

Cada habilidad es una carpeta dentro de skills/ con un archivo SKILL.md:

    ---
    name: crear-web
    description: Cuándo usarla, en una frase.
    ---
    Instrucciones detalladas...
"""
import re
from dataclasses import dataclass
from pathlib import Path

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    path: Path


def parse_skill(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        return None
    meta = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip().lower()] = value.strip().strip("\"'")
    if not meta.get("name") or not meta.get("description"):
        return None
    return Skill(meta["name"], meta["description"], match.group(2).strip(), path)


class SkillLibrary:
    def __init__(self, folder: Path):
        self.folder = folder

    def all(self) -> dict[str, Skill]:
        """Se lee cada vez: así una habilidad nueva funciona sin reiniciar."""
        skills = {}
        for path in sorted(self.folder.glob("*/SKILL.md")):
            skill = parse_skill(path)
            if skill:
                skills[skill.name] = skill
        return skills

    def summary(self) -> list[tuple[str, str]]:
        return [(s.name, s.description) for s in self.all().values()]

    def load(self, name: str) -> str:
        skills = self.all()
        skill = skills.get(name.strip())
        if skill is None:
            available = ", ".join(skills) or "ninguna"
            return f"No existe la habilidad '{name}'. Disponibles: {available}"
        return f"# Habilidad: {skill.name}\n\n{skill.instructions}"
