# Mi IA

Tu propia inteligencia artificial: **programa**, **responde preguntas** y **busca en internet** cuando lo necesita. Funciona en tu PC con un modelo abierto (gratis y privado) y puedes **entrenarla** con tus propios ejemplos.

## Cómo funciona

```
Tú ──► main.py (chat) ──► Agente ──► Modelo de lenguaje (Ollama, en tu PC)
                             │
                             ├── web_search / fetch_url   → busca y lee en internet
                             ├── run_python               → ejecuta y prueba código
                             └── read/write/list_files    → archivos en workspace/
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
2. **Descarga el modelo** (unos 2 GB):
   ```bash
   ollama pull qwen2.5-coder:3b
   ```
   El modelo necesita RAM libre: el 3B unos 2,5 GB y el 7B unos 5,5 GB. Si ves un error de memoria, cierra programas (el navegador suele ser el que más gasta) o usa `qwen2.5-coder:1.5b`. Con más RAM libre, `qwen2.5-coder:7b` responde bastante mejor. Cambia el modelo en `LLM_MODEL` dentro de `.env`.
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
- Botones 👍 👎 y **Corregir** en cada respuesta para entrenarla
- **Memoria**: cosas que le enseñas y recordará siempre

La web solo es accesible desde tu PC: no se abre a tu red ni a internet, y rechaza peticiones de otras webs.

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
   !python llama.cpp/convert_hf_to_gguf.py output/merged --outfile mi-ia.gguf --outtype q8_0
   ```
5. Descarga `mi-ia.gguf` y guárdalo en `training/`.

Por defecto entrena **Qwen2.5-Coder 1.5B** (cabe en la GPU gratis). Para el 7B usa `--base-model Qwen/Qwen2.5-Coder-7B-Instruct --qlora`.

### 3. Usar tu modelo entrenado

```bash
.venv\Scripts\python training\make_modelfile.py training\mi-ia.gguf --base qwen2.5-coder:1.5b
ollama create mi-ia -f training\Modelfile
```

Y en `.env`: `LLM_MODEL=mi-ia`.

## Seguridad

- **Claves solo en `.env`**, que está en `.gitignore`. `.env.example` lleva la lista de variables sin valores reales.
- **La configuración nunca muestra claves** al imprimirse.
- **El código que ejecuta la IA** corre en un proceso aparte, sin acceso a las variables del `.env`, con límite de tiempo y pidiéndote permiso antes (`CONFIRM_CODE=true`). Ojo: no es un aislamiento total; revisa el código antes de aceptarlo.
- **Los archivos** solo se leen o escriben dentro de `workspace/`, y los `.env`, `.pem` y `.key` están bloqueados.
- **Navegar por internet**: no puede abrir direcciones de tu red local (`localhost`, `192.168.x.x`…). Se identifica con honestidad y respeta las webs que no permiten bots (como Wikipedia); en ese caso usa los resultados del buscador.
- **La interfaz web** escucha solo en `127.0.0.1`, comprueba el origen de cada petición y limpia el HTML de las respuestas para que no pueda ejecutar código en tu navegador.
- **Conversaciones y datasets** pasan por un filtro que sustituye claves por `[REDACTADO]` antes de guardarse.
- **La IA aprende estas reglas**: están en sus instrucciones (`mi_ia/prompts.py`) y en los ejemplos de entrenamiento (`training/seed/seguridad.md`).

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
mi_ia/
  web/                   servidor y página del chat
  chats.py               guarda las conversaciones de la web
  config.py              lee el .env
  llm.py                 conexión con el modelo
  agent.py               bucle de razonamiento y herramientas
  prompts.py             instrucciones y reglas de la IA
  memory.py              notas, historial y valoraciones
  security.py            filtro de claves, rutas y URLs seguras
  tools/                 web, código y archivos
training/
  seed/                  ejemplos escritos a mano
  build_dataset.py       crea el dataset
  finetune_lora.py       entrena con LoRA
  make_modelfile.py      prepara el modelo para Ollama
data/                    tu historial (no se sube a git)
workspace/               carpeta de trabajo de la IA
```
