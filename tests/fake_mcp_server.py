"""Servidor MCP mínimo para los tests de conectores."""
import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("prueba")


@server.tool()
def sumar(a: int, b: int) -> str:
    """Suma dos números."""
    return str(a + b)


@server.tool()
def ver_secreto() -> str:
    """Devuelve la variable SECRETO_TEST si el servidor la recibió."""
    return os.environ.get("SECRETO_TEST", "no-recibido")


if __name__ == "__main__":
    server.run()
