from yunque.tools import files
from yunque.tools.code import run_python
from yunque.tools.web import html_to_text


def test_run_python_output(tmp_path):
    assert run_python("print(2 + 3)", tmp_path).strip() == "5"


def test_run_python_cannot_see_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "clave-que-no-debe-verse")
    out = run_python("import os; print(os.getenv('LLM_API_KEY'))", tmp_path)
    assert out.strip() == "None"


def test_run_python_timeout(tmp_path):
    assert "Tiempo agotado" in run_python("while True: pass", tmp_path, timeout=2)


def test_run_python_errors_are_reported(tmp_path):
    out = run_python("1/0", tmp_path)
    assert "ZeroDivisionError" in out and "código de salida" in out


def test_files_roundtrip_and_hides_env(tmp_path):
    files.write_file(tmp_path, "src/hola.py", "print('hola')")
    (tmp_path / ".env").write_text("SECRET=1")
    assert files.read_file(tmp_path, "src/hola.py") == "print('hola')"
    listing = files.list_files(tmp_path)
    assert "src/hola.py" in listing and ".env" not in listing


def test_pollinations_errors_are_explained():
    import httpx

    from yunque.tools.media import _http_error

    quest = httpx.Response(402, json={"error": {"code": "QUEST_POLLEN_ONLY", "message": "x"}})
    assert "Quest pollen only" in _http_error(quest)
    assert "saldo" in _http_error(httpx.Response(402, json={"error": {"code": "OTHER"}}))
    assert "no es válida" in _http_error(httpx.Response(401, text="no json"))


def test_html_to_text():
    html = "<html><head><title>T</title><script>x()</script></head><body><p>Hola</p></body></html>"
    text = html_to_text(html)
    assert "Hola" in text and "x()" not in text
