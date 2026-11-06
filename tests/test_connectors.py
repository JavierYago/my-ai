import json
import sys
from pathlib import Path

import pytest

from yunque.connectors import ConnectorManager, expand_vars

SERVER = str(Path(__file__).parent / "fake_mcp_server.py")


def manager(tmp_path, servers: dict) -> ConnectorManager:
    config = tmp_path / "connectors.json"
    config.write_text(json.dumps({"servers": servers}), encoding="utf-8")
    return ConnectorManager(config, tmp_path / "log.txt", call_timeout=30)


def test_expand_vars(monkeypatch):
    monkeypatch.setenv("MI_TOKEN", "abc")
    assert expand_vars("Bearer ${MI_TOKEN}") == "Bearer abc"
    with pytest.raises(KeyError):
        expand_vars("${NO_EXISTE_ESTA_VARIABLE}")


def test_connector_tools_work_and_only_get_declared_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETO_TEST", "valor-del-env")
    monkeypatch.setenv("OTRO_SECRETO", "no-debe-llegar")
    m = manager(tmp_path, {
        "prueba": {"command": sys.executable, "args": [SERVER], "enabled": True, "confirm": False,
                   "env": {"SECRETO_TEST": "${SECRETO_TEST}"}},
        "apagado": {"command": "no-existe", "enabled": False},
    })
    try:
        m.start()
        assert m.status["prueba"].connected, m.status["prueba"].error
        assert not m.status["apagado"].enabled
        tools = m.tools()
        assert set(tools) == {"prueba__sumar", "prueba__ver_secreto"}
        assert tools["prueba__sumar"].func(a=2, b=3) == "5"
        assert tools["prueba__ver_secreto"].func() == "valor-del-env"
        assert not tools["prueba__sumar"].needs_confirmation
    finally:
        m.stop()


def test_connector_error_is_reported(tmp_path):
    m = manager(tmp_path, {"roto": {"command": "programa-que-no-existe-xyz", "enabled": True}})
    try:
        m.start()
        assert not m.status["roto"].connected
        assert m.status["roto"].error
    finally:
        m.stop()


def test_set_enabled(tmp_path):
    m = manager(tmp_path, {"a": {"command": "x", "enabled": False}})
    m.set_enabled("a", True)
    assert m.read_config()["servers"]["a"]["enabled"] is True
    with pytest.raises(KeyError):
        m.set_enabled("b", True)
