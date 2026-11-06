import json
import sys
from pathlib import Path

from mi_ia.memory import Memory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
from build_dataset import build, parse_markdown  # noqa: E402

SEED = """
=== ejemplo ===
>>> usuario
Hola
>>> asistente
Soy Mi IA.
```python
x = 1
```
"""


def test_parse_markdown():
    [conv] = parse_markdown(SEED)
    assert [m["role"] for m in conv] == ["user", "assistant"]
    assert "x = 1" in conv[1]["content"]


def test_real_seed_files_parse():
    seed_dir = Path(__file__).resolve().parent.parent / "training" / "seed"
    for path in seed_dir.glob("*.md"):
        assert parse_markdown(path.read_text(encoding="utf-8")), path.name


def test_build_uses_good_and_corrected_feedback(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "a.md").write_text(SEED, encoding="utf-8")
    memory = Memory(tmp_path)
    good = memory.log_turn("s", "pregunta buena", "respuesta buena", [])
    bad = memory.log_turn("s", "pregunta mala", "respuesta mala", [])
    fixed = memory.log_turn("s", "pregunta corregida", "respuesta vieja", [])
    memory.rate(good, "good")
    memory.rate(bad, "bad")
    memory.rate(fixed, "corrected", "respuesta nueva con clave ghp_" + "a" * 36)

    out = tmp_path / "dataset.jsonl"
    assert build(seed, memory, out, "Javi-IA") == 3
    text = out.read_text(encoding="utf-8")
    assert "Soy Javi-IA" in text
    assert "respuesta buena" in text and "respuesta nueva" in text
    assert "respuesta mala" not in text and "respuesta vieja" not in text
    assert "ghp_" not in text
    first = json.loads(text.splitlines()[0])
    assert first["messages"][0]["role"] == "system"
