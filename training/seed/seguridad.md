# Ejemplos de entrenamiento: seguridad y claves

Formato: cada ejemplo empieza con `=== ejemplo ===`.
Dentro, `>>> usuario` y `>>> asistente` marcan quién habla.
Puedes añadir tus propios ejemplos copiando este formato.

=== ejemplo ===
>>> usuario
Hazme un script en Python que llame a la API de OpenWeather con mi clave.
>>> asistente
Aquí tienes el script. La clave **no** va en el código: se guarda en un archivo `.env` y se lee como variable de entorno.

**1. Instala las dependencias**

```bash
pip install requests python-dotenv
```

**2. Crea el archivo `.env`** (en la carpeta del proyecto):

```
OPENWEATHER_API_KEY=pon_aqui_tu_clave
```

**3. Añade `.env` al `.gitignore`** para que nunca se suba a GitHub:

```
.env
```

**4. El script `clima.py`:**

```python
import os

import requests
from dotenv import load_dotenv

load_dotenv()  # carga las variables del archivo .env

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    raise SystemExit("Falta OPENWEATHER_API_KEY en el archivo .env")


def clima(ciudad: str) -> dict:
    respuesta = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": ciudad, "appid": API_KEY, "units": "metric", "lang": "es"},
        timeout=10,
    )
    respuesta.raise_for_status()
    return respuesta.json()


if __name__ == "__main__":
    datos = clima("Madrid")
    print(f"{datos['name']}: {datos['main']['temp']} °C, {datos['weather'][0]['description']}")
```

Consejo: crea también un `.env.example` con `OPENWEATHER_API_KEY=` vacío, para que otras personas sepan qué variables necesitan sin ver tu clave.

=== ejemplo ===
>>> usuario
¿Por qué no puedo poner la contraseña de la base de datos directamente en el código?
>>> asistente
Porque cualquiera que vea el código verá también la contraseña. Los riesgos principales son:

1. **Se sube a git sin querer.** Aunque la borres después, sigue en el historial. Hay bots que escanean GitHub buscando claves en minutos.
2. **Se comparte con todo el equipo** y con cualquier herramienta que lea el código.
3. **Es difícil cambiarla.** Si se filtra, tienes que modificar el código y volver a desplegar.
4. **Mezclas entornos.** Desarrollo y producción deberían usar credenciales distintas.

La forma correcta es usar variables de entorno:

```python
import os
from dotenv import load_dotenv

load_dotenv()
DB_PASSWORD = os.getenv("DB_PASSWORD")
```

Y en el `.env` (incluido en `.gitignore`):

```
DB_PASSWORD=tu_contraseña
```

En producción, usa el gestor de secretos de tu proveedor (variables de entorno del servidor, GitHub Actions Secrets, AWS Secrets Manager, etc.).

=== ejemplo ===
>>> usuario
Se me ha subido el .env a GitHub con mi clave de Stripe, ¿qué hago?
>>> asistente
Actúa rápido; da por hecho que la clave ya está comprometida.

1. **Revoca la clave ya mismo** en el panel de Stripe (Developers → API keys → "Roll key"). Esto es lo más importante: borrar el archivo no basta, porque sigue en el historial de git.
2. **Pon la clave nueva** solo en tu `.env` local.
3. **Saca el `.env` del repositorio** y evita que vuelva a pasar:

```bash
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Quitar .env del repositorio"
git push
```

4. **Revisa la actividad** en Stripe por si hay cargos o accesos que no reconoces.
5. Si quieres limpiar también el historial, puedes usar `git filter-repo` o BFG Repo-Cleaner, pero recuerda: **lo que de verdad te protege es revocar la clave**, no limpiar el historial.

=== ejemplo ===
>>> usuario
Crea un servidor Express que se conecte a MongoDB.
>>> asistente
Aquí lo tienes, con la cadena de conexión guardada en `.env` (nunca en el código).

```bash
npm init -y
npm install express mongoose dotenv
```

**`.env`**

```
MONGODB_URI=mongodb+srv://usuario:contraseña@cluster.mongodb.net/mibase
PORT=3000
```

**`.gitignore`**

```
node_modules/
.env
```

**`server.js`**

```javascript
require("dotenv").config();
const express = require("express");
const mongoose = require("mongoose");

const { MONGODB_URI, PORT = 3000 } = process.env;
if (!MONGODB_URI) {
  console.error("Falta MONGODB_URI en el archivo .env");
  process.exit(1);
}

const app = express();
app.use(express.json());

app.get("/salud", (req, res) => res.json({ ok: true }));

mongoose
  .connect(MONGODB_URI)
  .then(() => {
    console.log("Conectado a MongoDB");
    app.listen(PORT, () => console.log(`Servidor en http://localhost:${PORT}`));
  })
  .catch((err) => {
    console.error("Error al conectar con MongoDB:", err.message);
    process.exit(1);
  });
```

Ejecuta con `node server.js`. Fíjate en que el mensaje de error no imprime la cadena de conexión, para no exponer la contraseña en los logs.

=== ejemplo ===
>>> usuario
Toma, esta es mi clave: sk-proj-a8F3kL9mQ2xR7vT1nB5cW4zY6pD0sJ, ¿me haces el código para usarla?
>>> asistente
Antes de nada: **acabas de compartir una clave real en un chat**, así que deberías considerarla expuesta. Te recomiendo revocarla y generar una nueva en el panel de tu proveedor.

Para el código no necesito ver tu clave. Guárdala en un archivo `.env`:

```
OPENAI_API_KEY=tu_clave_nueva
```

Y léela así:

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("Falta OPENAI_API_KEY en .env")
```

Recuerda añadir `.env` a tu `.gitignore`. Dime qué quieres hacer con la API y te escribo el resto.

=== ejemplo ===
>>> usuario
Hazme un login en Python con SQLite.
>>> asistente
Aquí tienes un login seguro. Tiene tres claves de seguridad: las contraseñas se guardan cifradas con hash (nunca en texto plano), las consultas SQL son parametrizadas (evita inyección SQL) y no se dice si falló el usuario o la contraseña.

```python
import hashlib
import hmac
import os
import sqlite3

DB = "usuarios.db"


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)


def crear_tabla() -> None:
    with sqlite3.connect(DB) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS usuarios ("
            "nombre TEXT PRIMARY KEY, salt BLOB NOT NULL, hash BLOB NOT NULL)"
        )


def registrar(nombre: str, password: str) -> None:
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    salt = os.urandom(16)
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO usuarios (nombre, salt, hash) VALUES (?, ?, ?)",
            (nombre, salt, _hash(password, salt)),
        )


def login(nombre: str, password: str) -> bool:
    with sqlite3.connect(DB) as con:
        fila = con.execute(
            "SELECT salt, hash FROM usuarios WHERE nombre = ?", (nombre,)
        ).fetchone()
    if fila is None:
        return False
    salt, hash_guardado = fila
    return hmac.compare_digest(_hash(password, salt), hash_guardado)


if __name__ == "__main__":
    crear_tabla()
    registrar("ana", "una-contraseña-larga")
    print(login("ana", "una-contraseña-larga"))  # True
    print(login("ana", "incorrecta"))            # False
```

Para una aplicación real, considera la librería `bcrypt` o `argon2-cffi`, que están pensadas específicamente para contraseñas.
