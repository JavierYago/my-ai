from pathlib import Path

from yunque.prompts import build_system_prompt
from yunque.skills import SkillLibrary
from yunque.voice import SentenceSplitter, clean_for_speech

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def test_real_skills_load():
    lib = SkillLibrary(SKILLS_DIR)
    names = dict(lib.summary())
    assert {"crear-web", "depurar-errores", "investigar", "crear-imagenes", "explicar"} <= set(names)
    assert lib.load("crear-web").startswith("# Habilidad: crear-web")
    assert "No existe" in lib.load("inventada")


def test_skill_without_frontmatter_is_ignored(tmp_path):
    (tmp_path / "mala").mkdir()
    (tmp_path / "mala" / "SKILL.md").write_text("sin cabecera", encoding="utf-8")
    assert SkillLibrary(tmp_path).summary() == []


def test_prompt_includes_skills_and_voice_mode():
    prompt = build_system_prompt("Javi-IA", ["Uso Python"], [("crear-web", "Hacer webs")], voice=True)
    assert "Javi-IA" in prompt and "crear-web" in prompt and "Uso Python" in prompt
    assert "Modo llamada de voz" in prompt
    assert "Modo llamada" not in build_system_prompt("x", [])


def test_sentence_splitter_skips_code():
    s = SentenceSplitter()
    text = "Claro, te lo explico ahora mismo. Mira:\n```python\nprint(1)\n```\nY listo, así de fácil."
    out = []
    for ch in text:
        out += s.feed(ch)
    out += s.flush()
    assert out[0] == "Claro, te lo explico ahora mismo."
    assert "print(1)" not in " ".join(out)
    assert "Te he dejado el código en el chat." in out
    assert out[-1] == "Y listo, así de fácil."


def test_clean_for_speech():
    assert clean_for_speech("**Hola** [web](http://a.com) 😀 https://b.com") == "Hola web"
