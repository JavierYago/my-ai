# Yunque

Tu propia inteligencia artificial: **programa**, **responde preguntas**, **busca en internet**, **crea imágenes y audio**, se conecta a otros servicios y puedes **hablar con ella por voz** como en una llamada. Funciona en tu PC con un modelo abierto (gratis y privado) y puedes **entrenarla** con tus propios ejemplos.

## Cómo funciona

```
Tú ──► web.py / main.py ──► Agente ──► Modelo de lenguaje (Ollama, en tu PC)
 🎙                            │
 └─ voz ─► Whisper (oír)       ├── web_search / fetch_url    → busca y lee en internet
     ◄──── Piper (hablar)      ├── run_python                → ejecuta y prueba código
                               ├── read/write/list_files     → archivos en workspace/
                               ├── generate_image / _music   → imágenes y música (Pollinations)
                               ├── generate_speech           → audios con voz (Piper)
                               ├── use_skill                 → habilidades de skills/
                               └── conectores MCP            → GitHub, archivos, Notion...
```

El "cerebro" es un modelo abierto (por defecto **Qwen2.5-Coder 3B**). Entrenar un modelo como ChatGPT o Claude desde cero cuesta millones en GPUs, así que lo que hacemos es lo que hacen casi todos los proyectos de IA: **partir de un modelo abierto y especializarlo** con tus datos (fine-tuning).

Tu IA aprende de tres formas:

| Forma | Qué hace | Necesita GPU |
|---|---|---|
| `/aprende <texto>` | Guarda un dato que la IA recordará en cada conversación | No |
| `/bien`, `/corrige` | Guarda respuestas buenas o corregidas para el entrenamiento | No |
| Fine-tuning (LoRA) | Cambia los pesos del modelo con tus ejemplos | Sí (Colab gratis) |

## Instalación

1. **Instala Ollama**: https://ollama.com/download (programa que ejecuta el modelo en tu PC).
2. **Descarga el modelo** (unos 2 GB) y crea la versión con más memoria de conversación:
   ```bash
   ollama pull qwen2.5-coder:3b
   ```
   ```bash
   ollama create yunque-3b -f ollama/Modelfile
   ```
   El modelo necesita RAM libre: el 3B unos 2,5 GB y el 7B unos 5,5 GB. Si ves un error de memoria, cierra programas (el navegador suele ser el que más gasta). Con más RAM libre, el 7B responde bastante mejor: cambia `qwen2.5-coder:3b` por `qwen2.5-coder:7b` en `ollama/Modelfile`, vuelve a crear el modelo y ajusta `LLM_MODEL` en `.env`.
3. **Instala las dependencias de Python** (ya está hecho en `.venv`; si no):
   ```bash
   py -3.12 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
4. **Configura `.env`**: ya existe, copiado de `.env.example`. Ahí van todas las claves; nunca en el código.
5. **Comprueba** que todo conecta:
   ```bash
   .venv\Scripts\python main.py --check
   ```

## Uso

### En el navegador (recomendado)

```bash
.venv\Scripts\python web.py
```

Se abre http://127.0.0.1:8000 con un chat parecido a ChatGPT o Claude:

- Conversaciones guardadas en la barra lateral
- Respuestas que aparecen palabra a palabra, con código resaltado y botón de copiar
- Avisos de lo que está haciendo (buscando en la web, leyendo una página, ejecutando código)
- Ventana para **permitir o denegar** cada ejecución de código
- Botones 👍 👎 y **Corregir** en cada respuesta para entrenarla, y 🔊 para escucharla
- **Memoria**: cosas que le enseñas y recordará siempre
- **Habilidades y conectores**: panel para verlas y activar conectores
- **Llamada de voz** (botón del micrófono)

La web solo es accesible desde tu PC: no se abre a tu red ni a internet, y rechaza peticiones de otras webs.

## Llamada de voz

Pulsa el **micrófono** junto a la caja de texto. Habla con normalidad: la IA detecta cuándo terminas, te contesta en voz alta frase a frase y, si hablas mientras responde, se calla para escucharte.

- **Todo en tu PC y gratis**: Whisper entiende lo que dices (licencia MIT) y Piper habla con la voz `es_ES-davefx`, de dominio público (CC0).
- La **primera llamada** descarga los modelos de voz (unos 200 MB, en `models/`) y tarda alrededor de un minuto en prepararse. Después, la primera frase de cada respuesta suele llegar en 3-7 segundos.
- **Usa auriculares**: sin ellos, el micrófono puede oír la voz de la IA y cortarla.
- Durante la llamada solo usa la búsqueda web, para responder rápido. Para código o imágenes, usa el chat.
- Puedes cambiar la voz con `VOICE_NAME` en `.env` (hay voces en muchos idiomas en https://huggingface.co/rhasspy/piper-voices; cada una tiene su licencia en el archivo MODEL_CARD).

## Imágenes, música y audio

- **Audio con voz** (narraciones, mensajes leídos): gratis y en tu PC con Piper. Pídele, por ejemplo, "léeme este texto en un audio".
- **Imágenes y música**: usan la API de [Pollinations](https://enter.pollinations.ai). Crea una cuenta, genera una **clave secreta** (empieza por `sk_`) y ponla en `.env`:
  ```
  POLLINATIONS_API_KEY=sk_...
  ```
  Pollinations funciona con créditos ("Pollen"): da algunos gratis y cobra el resto. El modelo de imagen por defecto (`flux.1-schnell`) es de los más baratos. Puedes cambiar los modelos con `IMAGE_MODEL` y `MUSIC_MODEL`.
- **La música solo funciona con Pollen de pago**: todos los modelos de música de Pollinations son de pago. Si tu clave tiene marcado "Quest pollen only" (solo Pollen gratis), las imágenes funcionan pero la música no. Para activarla, desmarca esa opción en la clave y añade saldo.
- Todo lo generado se guarda en `workspace/generated/` y se muestra en el chat.

## Habilidades (skills)

Son guías detalladas que la IA carga **solo cuando las necesita**, igual que las skills de Claude. Vienen cinco: `crear-web`, `depurar-errores`, `investigar`, `crear-imagenes` y `explicar`.

Para crear una nueva, haz una carpeta en `skills/` con un archivo `SKILL.md`:

```
---
name: mi-habilidad
description: Cuándo debe usarla, en una frase.
---
Instrucciones paso a paso...
```

La IA la ve al momento, sin reiniciar.

## Conectores (MCP)

Los conectores unen la IA a otros servicios usando **MCP** (Model Context Protocol), el estándar abierto que usan Claude y otras IAs. Hay cientos de servidores MCP: GitHub, Notion, Google Drive, Slack, bases de datos, archivos...

1. Edita `connectors.json` (si no existe, copia `connectors.example.json`). Ejemplo:
   ```json
   "github": {
     "description": "Repositorios de GitHub",
     "url": "https://api.githubcopilot.com/mcp/",
     "headers": { "Authorization": "Bearer ${GITHUB_TOKEN}" },
     "enabled": true,
     "confirm": true
   }
   ```
2. Las claves **nunca** van en `connectors.json`: escribe `${NOMBRE}` y pon el valor en `.env` (`GITHUB_TOKEN=...`).
3. Actívalos desde el panel **Habilidades y conectores** de la web.

Detalles:
- Conectores locales (`command`): se ejecutan en tu PC. Muchos usan `npx`, que necesita Node.js (ya lo tienes).
- Conectores remotos (`url`): se conectan por internet.
- `confirm: true` hace que la IA te pida permiso antes de usar cualquier herramienta de ese conector.
- Un conector local solo recibe las variables básicas del sistema más las que pongas en su `env`; nunca el resto de tu `.env`.
- Solo instala conectores de fuentes de confianza: pueden ejecutar programas en tu PC.
- Si un conector falla, el error aparece en el panel y en `data/connectors.log`.

## Personalidad y libertad

Sus instrucciones están en `yunque/prompts.py`. Habla con naturalidad de cualquier tema (adulto, polémico, tabú), no sermonea, da opiniones y escribe ficción oscura. El único límite es no ayudar a cometer delitos ni a hacer daño real. Puedes ajustar su carácter editando ese archivo.

Ten en cuenta que el modelo base (Qwen) tiene su propio entrenamiento y a veces será más prudente de lo que dicen las instrucciones. El fine-tuning con tus ejemplos (sección "Entrenar") es la forma de ajustar eso a fondo.

### En la terminal

```bash
.venv\Scripts\python main.py
```

Comandos dentro del chat de terminal: `/ayuda`, `/aprende`, `/notas`, `/bien`, `/mal`, `/corrige`, `/nuevo`, `/salir`.

Una sola pregunta:

```bash
.venv\Scripts\python main.py --pregunta "¿Qué novedades trae la última versión de Python?"
```

## Entrenar

### 1. Crear el dataset

```bash
.venv\Scripts\python training\build_dataset.py
```

Junta los ejemplos de `training/seed/*.md` (escritos a mano, incluyen cómo usar `.env` de forma segura), tus respuestas marcadas con `/bien` y tus correcciones de `/corrige`. Todo pasa por un filtro que oculta claves. Resultado: `training/dataset.jsonl`.

Para añadir ejemplos propios, crea un `.md` en `training/seed/` con este formato:

```
=== ejemplo ===
>>> usuario
La pregunta
>>> asistente
La respuesta perfecta que quieres que aprenda
```

Cuantos más ejemplos buenos, mejor: a partir de 100-200 se empieza a notar.

### 2. Entrenar en Google Colab (gratis)

Tu PC no tiene GPU NVIDIA, así que el entrenamiento se hace en Colab:

1. Entra en https://colab.research.google.com → Nuevo cuaderno → Entorno de ejecución → Cambiar tipo → **GPU T4**.
2. Sube `training/dataset.jsonl`, `training/finetune_lora.py` y `requirements-train.txt` (icono de carpeta a la izquierda).
3. Ejecuta en celdas:
   ```
   !pip install -q -r requirements-train.txt
   !python finetune_lora.py --data dataset.jsonl --output output
   ```
4. Convierte el modelo a formato GGUF (el que usa Ollama):
   ```
   !git clone --depth 1 https://github.com/ggml-org/llama.cpp
   !pip install -q -r llama.cpp/requirements.txt
   !python llama.cpp/convert_hf_to_gguf.py output/merged --outfile yunque.gguf --outtype q8_0
   ```
5. Descarga `yunque.gguf` y guárdalo en `training/`.

Por defecto entrena **Qwen2.5-Coder 1.5B** (cabe en la GPU gratis). Para el 7B usa `--base-model Qwen/Qwen2.5-Coder-7B-Instruct --qlora`.

### 3. Usar tu modelo entrenado

```bash
.venv\Scripts\python training\make_modelfile.py training\yunque.gguf --base qwen2.5-coder:1.5b
ollama create yunque -f training\Modelfile
```

Y en `.env`: `LLM_MODEL=yunque`.

## Seguridad

- **Claves solo en `.env`**, que está en `.gitignore`. `.env.example` lleva la lista de variables sin valores reales.
- **La configuración nunca muestra claves** al imprimirse.
- **El código que ejecuta la IA** corre en un proceso aparte, sin acceso a las variables del `.env`, con límite de tiempo y pidiéndote permiso antes (`CONFIRM_CODE=true`). Ojo: no es un aislamiento total; revisa el código antes de aceptarlo.
- **Los archivos** solo se leen o escriben dentro de `workspace/`, y los `.env`, `.pem` y `.key` están bloqueados.
- **Navegar por internet**: no puede abrir direcciones de tu red local (`localhost`, `192.168.x.x`…). Se identifica con honestidad y respeta las webs que no permiten bots (como Wikipedia); en ese caso usa los resultados del buscador.
- **La interfaz web** escucha solo en `127.0.0.1`, comprueba el origen de cada petición y limpia el HTML de las respuestas para que no pueda ejecutar código en tu navegador.
- **Conversaciones y datasets** pasan por un filtro que sustituye claves por `[REDACTADO]` antes de guardarse.
- **La IA aprende estas reglas**: están en sus instrucciones (`yunque/prompts.py`) y en los ejemplos de entrenamiento (`training/seed/seguridad.md`).

## Usar otro modelo

Cualquier servicio compatible con la API de OpenAI sirve (LM Studio, Groq, OpenRouter…). Cambia en `.env`:

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=tu_clave
LLM_MODEL=llama-3.3-70b-versatile
```

## Tests

```bash
.venv\Scripts\python -m pytest
```

## Estructura

```
web.py                   chat en el navegador
main.py                  chat por terminal
connectors.example.json  ejemplo de conectores MCP
skills/                  habilidades (una carpeta con SKILL.md cada una)
ollama/Modelfile         modelo base con más memoria de conversación
models/                  modelos de voz descargados (no se suben a git)
yunque/
  web/                   servidor y página del chat (incluida la llamada de voz)
  chats.py               guarda las conversaciones de la web
  voice.py               oír (Whisper) y hablar (Piper)
  skills.py              carga las habilidades
  connectors.py          conectores MCP
  config.py              lee el .env
  llm.py                 conexión con el modelo
  agent.py               bucle de razonamiento y herramientas
  prompts.py             instrucciones y reglas de la IA
  memory.py              notas, historial y valoraciones
  security.py            filtro de claves, rutas y URLs seguras
  tools/                 web, código, archivos, imágenes y audio
training/
  seed/                  ejemplos escritos a mano
  build_dataset.py       crea el dataset
  finetune_lora.py       entrena con LoRA
  make_modelfile.py      prepara el modelo para Ollama
data/                    tu historial (no se sube a git)
workspace/               carpeta de trabajo de la IA
```
