"""Generación de imágenes, música y audio con voz.

Imágenes y música: API de Pollinations (https://enter.pollinations.ai), con la clave en .env.
Voz: Piper, en tu PC y gratis.
"""
import random
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx

POLLINATIONS = "https://gen.pollinations.ai"
GENERATED = "generated"
NO_KEY = ("No puedo generar {what}: falta `POLLINATIONS_API_KEY` en el archivo `.env`. "
          "Puedes conseguir una clave en https://enter.pollinations.ai.")
_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_AUDIO_TYPES = {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav",
                "audio/ogg": "ogg", "audio/opus": "opus", "audio/flac": "flac", "audio/aac": "aac"}


def _save(workspace: Path, prefix: str, ext: str, data: bytes) -> str:
    folder = workspace / GENERATED
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.{ext}"
    (folder / name).write_bytes(data)
    return f"{GENERATED}/{name}"


def _failure(reason: str) -> dict:
    """Error explicado: "notice" se muestra siempre al usuario, aunque el modelo no lo cuente."""
    return {"text": f"No se pudo generar. Motivo (explícaselo al usuario): {reason}",
            "notice": reason}


def _http_error(response: httpx.Response) -> str:
    """Traduce el error de Pollinations a una explicación clara para el usuario."""
    status = response.status_code
    try:
        error = response.json().get("error") or {}
    except ValueError:
        error = {}
    code = error.get("code", "") if isinstance(error, dict) else ""
    if code == "QUEST_POLLEN_ONLY":
        return ("Este modelo solo funciona con **Pollen de pago**, y tu clave de Pollinations "
                "está configurada para gastar solo Pollen gratis (*Quest pollen only*). "
                "Todos los modelos de música de Pollinations son de pago. Para usarlo, desmarca "
                "*Quest pollen only* en tu clave desde https://enter.pollinations.ai y añade saldo.")
    if status == 401:
        return "La clave `POLLINATIONS_API_KEY` no es válida (debe empezar por `sk_`)."
    if status == 402:
        return "Tu cuenta de Pollinations no tiene saldo (Pollen) suficiente."
    if status == 403:
        return "Tu clave de Pollinations no tiene permiso para generar esto."
    if status == 429:
        return "Demasiadas peticiones a Pollinations; espera un poco y vuelve a intentarlo."
    detail = error.get("message", "") if isinstance(error, dict) else ""
    return f"Pollinations respondió con un error {status}. {detail}"[:400]


def generate_image(prompt: str, workspace: Path, api_key: str, model: str,
                   width: int = 1024, height: int = 1024) -> dict | str:
    if not api_key:
        return _failure(NO_KEY.format(what="imágenes"))
    width = max(256, min(int(width), 2048))
    height = max(256, min(int(height), 2048))
    r = httpx.get(f"{POLLINATIONS}/image/{quote(prompt, safe='')}",
                  params={"model": model, "width": width, "height": height,
                          "seed": random.randint(0, 2_147_483_647)},
                  headers={"Authorization": f"Bearer {api_key}"},
                  timeout=180, follow_redirects=True)
    if r.status_code >= 400:
        return _failure(_http_error(r))
    ext = _IMAGE_TYPES.get(r.headers.get("content-type", "").split(";")[0])
    if ext is None:  # se descartan SVG y otros formatos que podrían llevar código
        return _failure("El servicio devolvió un formato de imagen no admitido.")
    path = _save(workspace, "imagen", ext, r.content)
    return {"text": f"Imagen generada y guardada en workspace/{path}. El usuario ya la está viendo; "
                    "descríbela en una frase y ofrece variaciones.",
            "media": {"kind": "image", "path": path, "alt": prompt}}


def generate_music(prompt: str, workspace: Path, api_key: str, model: str) -> dict | str:
    if not api_key:
        return _failure(NO_KEY.format(what="música"))
    r = httpx.get(f"{POLLINATIONS}/audio/{quote(prompt, safe='')}", params={"model": model},
                  headers={"Authorization": f"Bearer {api_key}"},
                  timeout=300, follow_redirects=True)
    if r.status_code >= 400:
        return _failure(_http_error(r))
    ext = _AUDIO_TYPES.get(r.headers.get("content-type", "").split(";")[0], "mp3")
    path = _save(workspace, "musica", ext, r.content)
    return {"text": f"Audio generado y guardado en workspace/{path}. El usuario ya puede escucharlo.",
            "media": {"kind": "audio", "path": path, "alt": prompt}}


def generate_speech(text: str, workspace: Path, voice) -> dict:
    path = _save(workspace, "voz", "wav", voice.synthesize(text))
    return {"text": f"Audio con voz guardado en workspace/{path}. El usuario ya puede escucharlo.",
            "media": {"kind": "audio", "path": path, "alt": text[:100]}}
