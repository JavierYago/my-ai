"""Búsqueda web y lectura de páginas."""
import re
import time
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..security import is_public_url

MAX_DOWNLOAD = 2_000_000  # 2 MB
MAX_TEXT = 8_000
# Nos identificamos con honestidad. Algunas webs (p. ej. Wikipedia) no permiten
# la descarga automática; en ese caso la IA usa los fragmentos de la búsqueda.
HEADERS = {
    "User-Agent": "Yunque/0.1 (asistente personal de IA) python-httpx",
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
FAILED_HINT = " Usa la información de los resultados de búsqueda que ya tienes para responder."


def web_search(query: str, tavily_api_key: str = "", max_results: int = 5) -> str:
    results = None
    for attempt in range(2):
        try:
            if tavily_api_key:
                results = _search_tavily(query, tavily_api_key, max_results)
            else:
                results = _search_ddg(query, max_results)
            break
        except Exception:
            if attempt == 0:
                time.sleep(2)
    if results is None:
        return ("La búsqueda web ha fallado (el buscador no responde o ha limitado las búsquedas). "
                "No vuelvas a buscar: responde con lo que sepas y avisa de que no lo has podido "
                "comprobar en internet.")
    if not results:
        return "Sin resultados. Prueba con otras palabras o responde con lo que sepas."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n{r['url']}\n{r['snippet']}")
    return "\n\n".join(lines)


def _search_ddg(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    raw = DDGS().text(query, max_results=max_results) or []
    return [
        {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
        for r in raw
    ]


def _search_tavily(query: str, api_key: str, max_results: int) -> list[dict]:
    r = httpx.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": query, "max_results": max_results},
        timeout=30,
    )
    r.raise_for_status()
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
        for x in r.json().get("results", [])
    ]


def fetch_url(url: str, max_redirects: int = 3) -> str:
    with httpx.Client(timeout=20, follow_redirects=False, headers=HEADERS) as client:
        for _ in range(max_redirects + 1):
            # Se comprueba cada salto: así una redirección no puede llevar a tu red local
            if not is_public_url(url):
                return f"URL bloqueada (no es pública o no es http/https): {url}"
            with client.stream("GET", url) as r:
                if r.is_redirect and "location" in r.headers:
                    url = urljoin(url, r.headers["location"])
                    continue
                if r.status_code >= 400:
                    return f"No se pudo abrir {url} (error HTTP {r.status_code})." + FAILED_HINT
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_DOWNLOAD:
                        break
                ctype = r.headers.get("content-type", "")
                text = body.decode(r.encoding or "utf-8", errors="replace")
                return html_to_text(text) if "html" in ctype else text[:MAX_TEXT]
    return "Demasiadas redirecciones." + FAILED_HINT


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "svg", "form"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    text = soup.get_text("\n")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    out = f"{title}\n\n{text}" if title else text
    return out[:MAX_TEXT] + ("\n[...texto recortado]" if len(out) > MAX_TEXT else "")
