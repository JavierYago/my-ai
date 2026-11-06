---
name: depurar-errores
description: Encontrar y arreglar errores en código (excepciones, fallos, resultados incorrectos).
---
Método para depurar:

1. **Lee el error completo**: tipo de excepción, mensaje y la última línea del traceback que pertenece al código del usuario (no a librerías). Esa suele ser la pista principal.
2. **Explica la causa en una frase sencilla** antes de dar la solución. Ejemplo: "Estás sumando un texto y un número".
3. **Reproduce el problema** si puedes: crea un ejemplo mínimo y ejecútalo con run_python para confirmar la causa.
4. **Arregla la causa, no el síntoma**: evita soluciones como envolver todo en `try/except: pass`.
5. **Comprueba el arreglo** ejecutándolo con run_python cuando sea posible.
6. **Muestra solo lo que cambia**, con unas líneas de contexto, y explica por qué funciona.
7. Si no hay suficiente información, pide exactamente lo que falta: el traceback completo, la versión de Python o de la librería, o el fragmento de código donde falla.

Causas frecuentes que conviene revisar:
- Tipos mezclados (str + int), `None` donde se esperaba un valor.
- Índices fuera de rango o claves que no existen en un diccionario.
- Rutas de archivo relativas que dependen de la carpeta desde donde se ejecuta.
- Versiones de librerías que cambiaron su API.
- Variables de entorno que no se cargaron (falta `load_dotenv()` o el `.env` no está en la carpeta correcta).
