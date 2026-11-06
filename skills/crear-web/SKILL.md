---
name: crear-web
description: Crear páginas o aplicaciones web (HTML, CSS, JavaScript) bonitas y que funcionen.
---
Sigue estos pasos para crear una web:

1. **Entiende el objetivo**: qué debe hacer la página y para quién. Si falta algo importante, pregunta una sola cosa.
2. **Estructura**: un único `index.html` con el CSS en `<style>` y el JS en `<script>`, salvo que el proyecto sea grande. Guárdalo con write_file en `workspace/<nombre-proyecto>/index.html`.
3. **Diseño**:
   - Usa variables CSS (`:root { --color-fondo: ...; }`) y una paleta de 3-4 colores como mucho.
   - Tipografía del sistema: `font-family: system-ui, sans-serif;`, tamaño base 16px, `line-height: 1.6`.
   - Espaciado generoso, bordes redondeados suaves y sombras discretas.
   - Que funcione en móvil: `<meta name="viewport" content="width=device-width, initial-scale=1">`, flexbox o grid y una media query para pantallas de menos de 700px.
   - Incluye modo oscuro con `@media (prefers-color-scheme: dark)`.
4. **Accesibilidad**: etiquetas `<label>` en los formularios, `alt` en las imágenes, botones de verdad (`<button>`) y suficiente contraste.
5. **JavaScript**: sin librerías si no hacen falta. Usa `const`/`let`, `addEventListener` y nunca metas en `innerHTML` texto que venga del usuario (usa `textContent`).
6. **Seguridad**: si la web usa una API con clave, la clave NO puede ir en el JavaScript del navegador. Explica que hace falta un pequeño servidor (por ejemplo Express o FastAPI) que guarde la clave en `.env`.
7. **Entrega**: di dónde se guardó el archivo y cómo abrirlo (doble clic en el `index.html`).
