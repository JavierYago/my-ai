from pathlib import Path

import pytest

from mi_ia.security import REDACTED, is_public_url, redact, safe_path


@pytest.mark.parametrize("secret", [
    "sk-proj-a8F3kL9mQ2xR7vT1nB5cW4zY6pD0sJ",
    "ghp_" + "a" * 36,
    "AKIA" + "ABCDEFGHIJKLMNOP",
    "tvly-" + "x1" * 12,
])
def test_redact_known_key_formats(secret):
    out = redact(f"mi clave es {secret} gracias")
    assert secret not in out and REDACTED in out


def test_redact_assignments():
    assert "hunter22" not in redact("DB_PASSWORD=hunter22")
    assert "s3cr3tvalue" not in redact('{"api_key": "s3cr3tvalue"}')


def test_redact_keeps_code_and_placeholders():
    code = 'API_KEY = os.getenv("API_KEY")\napi_key = settings.llm_api_key\nTOKEN=tu_token_aqui'
    assert redact(code) == code


def test_redact_env_values(monkeypatch):
    monkeypatch.setenv("MY_SERVICE_TOKEN", "valor-super-privado-123")
    assert "valor-super-privado-123" not in redact("token: valor-super-privado-123")


def test_safe_path_blocks_escape_and_secrets(tmp_path: Path):
    assert safe_path(tmp_path, "a/b.txt") == (tmp_path / "a" / "b.txt").resolve()
    with pytest.raises(PermissionError):
        safe_path(tmp_path, "../fuera.txt")
    with pytest.raises(PermissionError):
        safe_path(tmp_path, ".env")
    with pytest.raises(PermissionError):
        safe_path(tmp_path, "certs/server.key")
    assert safe_path(tmp_path, ".env.example").name == ".env.example"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080", "http://localhost", "http://192.168.1.1",
    "http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "ftp://8.8.8.8",
])
def test_private_urls_blocked(url):
    assert not is_public_url(url)


def test_public_ip_allowed():
    assert is_public_url("https://8.8.8.8")
