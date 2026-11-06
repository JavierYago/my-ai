"use strict";

const $ = (sel) => document.querySelector(sel);

const ICONS = {
  copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  up: '<svg viewBox="0 0 24 24"><path d="M7 10v11M15 5.9 14 10h5.8a2 2 0 0 1 2 2.3l-1.4 7a2 2 0 0 1-2 1.7H7V10l4-8a3 3 0 0 1 4 3.9z"/></svg>',
  down: '<svg viewBox="0 0 24 24"><path d="M17 14V3M9 18.1 10 14H4.2a2 2 0 0 1-2-2.3l1.4-7a2 2 0 0 1 2-1.7H17v11l-4 8a3 3 0 0 1-4-3.9z"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>',
  star: '<svg viewBox="0 0 24 24"><path d="M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4z"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
  globe: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/></svg>',
  code: '<svg viewBox="0 0 24 24"><path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
  image: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
  music: '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  speaker: '<svg viewBox="0 0 24 24"><path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg>',
  stop: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/></svg>',
  plug: '<svg viewBox="0 0 24 24"><path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4"/></svg>',
};

const TOOL_LABELS = {
  web_search: ["search", "Buscando en la web"],
  fetch_url: ["globe", "Leyendo página"],
  run_python: ["code", "Ejecutando código"],
  read_file: ["file", "Leyendo archivo"],
  write_file: ["file", "Guardando archivo"],
  list_files: ["file", "Mirando archivos"],
  generate_image: ["image", "Creando imagen"],
  generate_music: ["music", "Creando música"],
  generate_speech: ["speaker", "Grabando audio"],
  use_skill: ["book", "Usando habilidad"],
};

function toolLabel(name) {
  if (TOOL_LABELS[name]) return TOOL_LABELS[name];
  const [server, tool] = name.split("__");
  return tool ? ["plug", `Conector ${server}: ${tool}`] : ["code", name];
}

const state = { chatId: null, busy: false };

marked.setOptions({ gfm: true, breaks: false });

// ---------- Utilidades ----------

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

async function errorMessage(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
  } catch { /* sin cuerpo JSON */ }
  return `Error ${res.status}`;
}

function el(tag, className, html) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (html !== undefined) node.innerHTML = html;
  return node;
}

let toastTimer;
function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

async function copyText(text, button) {
  await navigator.clipboard.writeText(text);
  const old = button.innerHTML;
  button.innerHTML = ICONS.check + (button.dataset.label ? " Copiado" : "");
  setTimeout(() => (button.innerHTML = old), 1500);
}

// El HTML del modelo siempre pasa por DOMPurify: así no puede inyectar scripts
function renderMarkdown(target, text) {
  target.innerHTML = DOMPurify.sanitize(marked.parse(text || ""));
  target.querySelectorAll("a").forEach((a) => {
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  });
  target.querySelectorAll("pre > code").forEach((code) => {
    const pre = code.parentElement;
    const lang = (code.className.match(/language-([\w+#-]+)/) || [])[1] || "código";
    try { hljs.highlightElement(code); } catch { /* lenguaje desconocido */ }
    const block = el("div", "code-block");
    const head = el("div", "code-head");
    head.append(el("span", "", ""));
    head.firstChild.textContent = lang;
    const copy = el("button", "copy-btn", ICONS.copy + " Copiar");
    copy.dataset.label = "1";
    copy.type = "button";
    copy.addEventListener("click", () => copyText(code.textContent, copy));
    head.append(copy);
    pre.replaceWith(block);
    block.append(head, pre);
  });
}

const messagesEl = $("#messages");
function nearBottom() {
  return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 120;
}
function scrollToBottom(force = false) {
  if (force || nearBottom()) messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---------- Barra lateral ----------

async function loadChats() {
  const list = $("#chat-list");
  const chats = await api("/api/chats");
  list.innerHTML = "";
  if (!chats.length) {
    list.append(el("div", "chat-list-empty", "Aún no hay conversaciones"));
    return;
  }
  for (const chat of chats) {
    const item = el("a", "chat-item" + (chat.id === state.chatId ? " active" : ""));
    item.href = "#" + chat.id;
    const title = el("span", "title");
    title.textContent = chat.title;
    const del = el("button", "delete", ICONS.trash);
    del.type = "button";
    del.setAttribute("aria-label", "Borrar conversación");
    del.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm(`¿Borrar "${chat.title}"?`)) return;
      await api(`/api/chats/${chat.id}`, { method: "DELETE" });
      if (chat.id === state.chatId) newChat();
      loadChats();
    });
    item.append(title, del);
    item.addEventListener("click", (e) => {
      e.preventDefault();
      openChat(chat.id);
      closeSidebar();
    });
    list.append(item);
  }
}

function setActive(id) {
  document.querySelectorAll(".chat-item").forEach((a) =>
    a.classList.toggle("active", a.getAttribute("href") === "#" + id));
}

function showEmpty(show) {
  $("#empty").classList.toggle("hidden", !show);
}

function newChat() {
  if (state.busy) return;
  state.chatId = null;
  $("#thread").innerHTML = "";
  $("#chat-title").textContent = "";
  history.replaceState(null, "", "/");
  showEmpty(true);
  setActive(null);
  $("#input").focus();
}

async function openChat(id) {
  if (state.busy) return;
  let chat;
  try {
    chat = await api(`/api/chats/${id}`);
  } catch {
    newChat();
    return;
  }
  state.chatId = chat.id;
  history.replaceState(null, "", "#" + chat.id);
  $("#chat-title").textContent = chat.title;
  const thread = $("#thread");
  thread.innerHTML = "";
  showEmpty(chat.messages.length === 0);
  for (const m of chat.messages) {
    if (m.role === "user") addUserMessage(m.content);
    else {
      const view = addAssistantMessage();
      view.thinking.remove();
      if (m.tools && m.tools.length) {
        const used = [...new Set(m.tools)].map((t) => toolLabel(t)[1]);
        view.steps.before(Object.assign(el("div", "tools-used"), { textContent: "Usó: " + used.join(" · ") }));
      }
      (m.media || []).forEach((item) => addMedia(view, item));
      renderMarkdown(view.body, m.content);
      addActions(view, m.content, m.turn_id);
    }
  }
  setActive(chat.id);
  scrollToBottom(true);
}

// ---------- Mensajes ----------

function addUserMessage(text) {
  const node = el("div", "msg-user");
  node.textContent = text;
  $("#thread").append(node);
}

function addAssistantMessage() {
  const root = el("div", "msg-ai");
  root.append(el("div", "avatar", ICONS.star));
  const content = el("div", "content");
  const steps = el("div", "steps");
  const media = el("div", "media");
  const body = el("div", "md");
  const thinking = el("div", "thinking", "<span></span><span></span><span></span>");
  content.append(steps, media, thinking, body);
  root.append(content);
  $("#thread").append(root);
  return { root, content, steps, media, body, thinking };
}

function addMedia(view, item) {
  const box = el("div");
  if (item.kind === "image") {
    const link = el("a");
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener";
    const img = el("img");
    img.src = item.url;
    img.alt = item.alt || "Imagen generada";
    img.loading = "lazy";
    img.addEventListener("load", () => scrollToBottom());
    link.append(img);
    box.append(link);
  } else {
    const audio = el("audio");
    audio.controls = true;
    audio.src = item.url;
    box.append(audio);
  }
  const caption = el("div", "media-caption");
  caption.textContent = item.alt || "";
  box.append(caption);
  view.media.append(box);
}

// Lee una respuesta en voz alta con la voz local de la IA
let currentAudio = null;
async function speak(text, button) {
  if (currentAudio) {
    currentAudio.pause();
    const wasThis = currentAudio.button === button;
    currentAudio.button.innerHTML = ICONS.speaker;
    currentAudio = null;
    if (wasThis) return;
  }
  button.innerHTML = '<span class="spin"></span>';
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 5000) }),
    });
    if (!res.ok) throw new Error(await errorMessage(res));
    const audio = new Audio(URL.createObjectURL(await res.blob()));
    audio.button = button;
    currentAudio = audio;
    button.innerHTML = ICONS.stop;
    audio.addEventListener("ended", () => {
      button.innerHTML = ICONS.speaker;
      if (currentAudio === audio) currentAudio = null;
    });
    audio.play();
  } catch (e) {
    button.innerHTML = ICONS.speaker;
    toast(e.message);
  }
}

function addActions(view, answer, turnId) {
  const bar = el("div", "actions");
  const button = (icon, title) => {
    const b = el("button", "", icon);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    bar.append(b);
    return b;
  };
  const copy = button(ICONS.copy, "Copiar");
  copy.addEventListener("click", () => copyText(answer, copy));
  const listen = button(ICONS.speaker, "Escuchar");
  listen.addEventListener("click", () => speak(answer, listen));
  if (turnId) {
    const good = button(ICONS.up, "Buena respuesta");
    const bad = button(ICONS.down, "Mala respuesta");
    const fix = button(ICONS.edit, "Corregir");
    const rate = async (rating, btn) => {
      await api("/api/feedback", { method: "POST", body: JSON.stringify({ turn_id: turnId, rating }) });
      good.classList.toggle("active", btn === good);
      bad.classList.toggle("active", btn === bad);
      toast(rating === "good" ? "¡Gracias! La usaré para entrenar" : "Anotado, no la usaré para entrenar");
    };
    good.addEventListener("click", () => rate("good", good));
    bad.addEventListener("click", () => rate("bad", bad));
    fix.addEventListener("click", () => openCorrection(turnId, answer, fix));
  }
  view.content.append(bar);
}

function finishSteps(view) {
  view.steps.querySelectorAll(".step").forEach((s) => s.classList.add("done"));
}

// ---------- Enviar ----------

async function send(text) {
  if (state.busy || !text.trim()) return;
  setBusy(true);
  showEmpty(false);

  try {
    if (!state.chatId) {
      const chat = await api("/api/chats", { method: "POST" });
      state.chatId = chat.id;
      history.replaceState(null, "", "#" + chat.id);
    }
  } catch (e) {
    toast(e.message);
    setBusy(false);
    return;
  }

  addUserMessage(text);
  const view = addAssistantMessage();
  scrollToBottom(true);

  let segment = "";       // texto del paso actual
  let renderQueued = false;
  const render = () => {
    renderQueued = false;
    renderMarkdown(view.body, segment);
    scrollToBottom();
  };
  const queueRender = () => {
    if (!renderQueued) { renderQueued = true; requestAnimationFrame(render); }
  };

  const handle = (ev) => {
    switch (ev.type) {
      case "token":
        view.thinking.remove();
        segment += ev.text;
        queueRender();
        break;
      case "discard":
        segment = "";
        queueRender();
        break;
      case "tool": {
        finishSteps(view);
        if (segment.trim()) {
          const note = el("div", "step-note");
          note.textContent = segment.trim();
          view.steps.append(note);
        }
        segment = "";
        view.body.innerHTML = "";
        const [icon, label] = toolLabel(ev.name);
        const step = el("div", "step", `<span class="spin"></span>${ICONS[icon]}<span></span><span class="detail"></span>`);
        step.children[2].textContent = label;
        step.children[3].textContent = ev.detail || "";
        view.steps.append(step);
        if (!view.content.contains(view.thinking)) view.content.insertBefore(view.thinking, view.body);
        scrollToBottom();
        break;
      }
      case "confirm":
        askConfirm(ev);
        break;
      case "media":
        addMedia(view, ev);
        scrollToBottom();
        break;
      case "done":
        finishSteps(view);
        view.thinking.remove();
        renderMarkdown(view.body, ev.answer);
        addActions(view, ev.answer, ev.turn_id);
        $("#chat-title").textContent = ev.title;
        loadChats();
        scrollToBottom();
        break;
      case "error":
        finishSteps(view);
        view.thinking.remove();
        view.body.innerHTML = "";
        view.body.append(Object.assign(el("div", "error-box"), { textContent: ev.message }));
        scrollToBottom();
        break;
    }
  };

  try {
    const res = await fetch(`/api/chats/${state.chatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(await errorMessage(res));
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) handle(JSON.parse(line));
      }
    }
  } catch (e) {
    handle({ type: "error", message: e.message || "Se perdió la conexión con el servidor." });
  } finally {
    setBusy(false);
    $("#input").focus();
  }
}

function setBusy(busy) {
  state.busy = busy;
  updateSend();
}

// ---------- Caja de texto ----------

const input = $("#input");
function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 220) + "px";
}
function updateSend() {
  $("#send").disabled = state.busy || !input.value.trim();
}
input.addEventListener("input", () => { autosize(); updateSend(); });
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  if (state.busy) return;
  const text = input.value;
  if (!text.trim()) return;
  input.value = "";
  autosize();
  send(text);
});
document.querySelectorAll(".suggestions button").forEach((b) =>
  b.addEventListener("click", () => send(b.dataset.prompt)));

// ---------- Diálogos ----------

function askConfirm(ev) {
  const dialog = $("#confirm-dialog");
  const code = $("#confirm-code");
  const isPython = ev.tool === "run_python";
  $("#confirm-title").textContent = isPython ? "¿Ejecutar este código?" : `¿Usar ${toolLabel(ev.tool)[1]}?`;
  $("#confirm-sub").textContent = isPython
    ? "La IA quiere ejecutar este código Python en tu PC (sin acceso a tus claves). Revísalo antes de aceptar."
    : "La IA quiere usar esta herramienta de un conector con estos datos. Revísalos antes de aceptar.";
  code.textContent = ev.code;
  code.removeAttribute("data-highlighted");
  code.className = isPython ? "language-python" : "language-json";
  try { hljs.highlightElement(code); } catch { /* nada */ }
  const answer = async (allow) => {
    dialog.close();
    await api(`/api/confirm/${ev.id}`, { method: "POST", body: JSON.stringify({ allow }) })
      .catch((e) => toast(e.message));
  };
  $("#confirm-allow").onclick = () => answer(true);
  $("#confirm-deny").onclick = () => answer(false);
  dialog.oncancel = (e) => { e.preventDefault(); answer(false); };
  dialog.showModal();
}

function openCorrection(turnId, answer, button) {
  const dialog = $("#correct-dialog");
  const text = $("#correct-text");
  text.value = answer;
  $("#correct-cancel").onclick = () => dialog.close();
  $("#correct-save").onclick = async () => {
    if (!text.value.trim()) return;
    try {
      await api("/api/feedback", {
        method: "POST",
        body: JSON.stringify({ turn_id: turnId, rating: "corrected", correction: text.value }),
      });
      button.classList.add("active");
      dialog.close();
      toast("Corrección guardada para entrenar");
    } catch (e) {
      toast(e.message);
    }
  };
  dialog.showModal();
  text.focus();
}

function renderNotes(notes) {
  const list = $("#notes-list");
  list.innerHTML = "";
  if (!notes.length) {
    list.append(el("li", "empty-note", "Todavía no le has enseñado nada."));
    return;
  }
  for (const n of notes) {
    const li = el("li");
    li.textContent = n;
    list.append(li);
  }
}

$("#open-notes").addEventListener("click", async () => {
  renderNotes(await api("/api/notes"));
  $("#notes-dialog").showModal();
  $("#note-input").focus();
});
$("#notes-close").addEventListener("click", () => $("#notes-dialog").close());
$("#note-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const field = $("#note-input");
  if (!field.value.trim()) return;
  renderNotes(await api("/api/notes", { method: "POST", body: JSON.stringify({ text: field.value }) }));
  field.value = "";
  toast("Aprendido");
});

// ---------- Habilidades y conectores ----------

function itemRow(name, desc) {
  const li = el("li");
  const text = el("div", "item-text");
  const n = el("span", "item-name");
  n.textContent = name;
  const d = el("span", "item-desc");
  d.textContent = desc;
  text.append(n, d);
  li.append(text);
  return { li, text };
}

function renderConnectors(list) {
  const ul = $("#connectors-list");
  ul.innerHTML = "";
  if (!list.length) {
    ul.append(el("li", "", "No hay conectores. Copia connectors.example.json como connectors.json."));
    return;
  }
  for (const c of list) {
    const { li, text } = itemRow(c.name, c.description || "");
    if (c.error) {
      const err = el("span", "item-error");
      err.textContent = "Error: " + c.error;
      text.append(err);
    } else if (c.connected) {
      const ok = el("span", "item-ok");
      ok.textContent = `Conectado · ${c.tools.length} herramientas`;
      text.append(ok);
    }
    const sw = el("label", "switch");
    const input = el("input");
    input.type = "checkbox";
    input.checked = c.enabled;
    input.setAttribute("aria-label", `Activar ${c.name}`);
    input.addEventListener("change", async () => {
      document.querySelectorAll("#connectors-list input").forEach((i) => (i.disabled = true));
      toast(input.checked ? `Conectando ${c.name}…` : `Desconectando ${c.name}…`);
      try {
        renderConnectors(await api(`/api/connectors/${encodeURIComponent(c.name)}`, {
          method: "POST", body: JSON.stringify({ enabled: input.checked }),
        }));
      } catch (e) {
        toast(e.message);
        renderConnectors(await api("/api/connectors"));
      }
    });
    sw.append(input, el("span"));
    li.append(sw);
    ul.append(li);
  }
}

$("#open-tools").addEventListener("click", async () => {
  const [skills, conns] = await Promise.all([api("/api/skills"), api("/api/connectors")]);
  const ul = $("#skills-list");
  ul.innerHTML = "";
  if (!skills.length) ul.append(el("li", "", "No hay habilidades en la carpeta skills/."));
  skills.forEach((s) => ul.append(itemRow(s.name, s.description).li));
  renderConnectors(conns);
  $("#tools-dialog").showModal();
});
$("#tools-close").addEventListener("click", () => $("#tools-dialog").close());

// ---------- Llamada de voz ----------
// Escucha el micrófono, detecta cuándo hablas y cuándo te callas, envía lo que dijiste
// y reproduce la respuesta hablada frase a frase. Si hablas mientras responde, se calla.

const call = {
  active: false, muted: false, state: "idle",
  ctx: null, stream: null, node: null, analyser: null,
  inSpeech: false, speechMs: 0, silenceMs: 0, noise: 0.01,
  chunks: [], preroll: [], level: 0,
  queue: [], source: null, playing: false, turn: 0, waitingDone: false, abort: null,
};
const TARGET_RATE = 16000;
const END_SILENCE_MS = 900;   // silencio para dar por terminada tu frase
const MIN_SPEECH_MS = 350;    // ignora ruidos cortos

function setCallState(stateName, text) {
  call.state = stateName;
  $("#call").dataset.state = call.muted ? "muted" : stateName;
  const labels = { listening: "Te escucho…", thinking: "Pensando…", speaking: "Hablando…" };
  $("#call-status").textContent = text || labels[stateName] || "";
}

async function startCall() {
  if (state.busy) { toast("Espera a que termine la respuesta actual"); return; }
  if (!navigator.mediaDevices || !window.AudioWorkletNode) {
    toast("Tu navegador no permite usar el micrófono aquí");
    return;
  }
  $("#call").hidden = false;
  $("#call-name").textContent = $("#brand-name").textContent;
  $("#call-you").textContent = "";
  $("#call-ai").textContent = "";
  call.active = true;
  call.muted = false;
  $("#call-mute").classList.remove("active");
  try {
    setCallState("thinking", "Preparando la voz… (la primera vez descarga los modelos)");
    if (!state.chatId) {
      const chat = await api("/api/chats", { method: "POST" });
      state.chatId = chat.id;
      history.replaceState(null, "", "#" + chat.id);
    }
    await api("/api/voice/warmup", { method: "POST" });
    if (!call.active) return;
    call.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    call.ctx = new AudioContext();
    await call.ctx.audioWorklet.addModule("/static/recorder-worklet.js");
    const mic = call.ctx.createMediaStreamSource(call.stream);
    call.node = new AudioWorkletNode(call.ctx, "recorder");
    call.node.port.onmessage = (e) => onMicFrame(e.data);
    mic.connect(call.node);
    call.analyser = call.ctx.createAnalyser();
    call.analyser.fftSize = 512;
    call.analyser.connect(call.ctx.destination);
    animateOrb();
    setCallState("listening");
  } catch (e) {
    toast(e.name === "NotAllowedError" ? "Necesito permiso para usar el micrófono" : e.message);
    endCall();
  }
}

function endCall() {
  call.active = false;
  stopPlayback();
  if (call.abort) call.abort.abort();
  call.stream?.getTracks().forEach((t) => t.stop());
  call.ctx?.close();
  Object.assign(call, { stream: null, ctx: null, node: null, analyser: null, inSpeech: false,
    chunks: [], preroll: [], speechMs: 0, silenceMs: 0 });
  $("#call").hidden = true;
  if (state.chatId) { openChat(state.chatId); loadChats(); }
}

function onMicFrame(frame) {
  if (!call.active || !call.ctx) return;
  const frameMs = (frame.length / call.ctx.sampleRate) * 1000;
  let sum = 0;
  for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
  const rms = Math.sqrt(sum / frame.length);
  call.level = rms;
  if (call.muted || call.state === "thinking") return;

  // Mientras la IA habla, hace falta hablar más fuerte para interrumpirla (evita el eco)
  const threshold = Math.max(0.012, call.noise * 3) * (call.state === "speaking" ? 2.5 : 1);
  const loud = rms > threshold;

  if (!call.inSpeech) {
    call.preroll.push(frame);
    if (call.preroll.length > 8) call.preroll.shift();
    if (!loud) call.noise = call.noise * 0.95 + rms * 0.05;
    call.speechMs = loud ? call.speechMs + frameMs : 0;
    const needed = call.state === "speaking" ? 300 : 120;
    if (call.speechMs >= needed) {
      call.inSpeech = true;
      call.silenceMs = 0;
      call.chunks = [...call.preroll];
      call.preroll = [];
      if (call.state === "speaking") { stopPlayback(); call.turn++; setCallState("listening"); }
    }
    return;
  }
  call.chunks.push(frame);
  call.speechMs += loud ? frameMs : 0;
  call.silenceMs = loud ? 0 : call.silenceMs + frameMs;
  if (call.silenceMs >= END_SILENCE_MS) {
    const chunks = call.chunks;
    const spoken = call.speechMs;
    Object.assign(call, { inSpeech: false, chunks: [], speechMs: 0, silenceMs: 0 });
    if (spoken >= MIN_SPEECH_MS) sendUtterance(chunks);
  }
}

function encodeWav(chunks, inputRate) {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const ratio = inputRate / TARGET_RATE;
  const length = Math.floor(total / ratio);
  const merged = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) { merged.set(c, offset); offset += c.length; }
  const view = new DataView(new ArrayBuffer(44 + length * 2));
  const writeStr = (pos, s) => { for (let i = 0; i < s.length; i++) view.setUint8(pos + i, s.charCodeAt(i)); };
  writeStr(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); writeStr(8, "WAVE");
  writeStr(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, TARGET_RATE, true); view.setUint32(28, TARGET_RATE * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  writeStr(36, "data"); view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const s = Math.max(-1, Math.min(1, merged[Math.floor(i * ratio)]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

async function sendUtterance(chunks) {
  const turn = ++call.turn;
  setCallState("thinking");
  const form = new FormData();
  form.append("audio", encodeWav(chunks, call.ctx.sampleRate), "voz.wav");
  call.abort = new AbortController();
  let res;
  // Si la respuesta anterior aún se está generando, espera un poco y reintenta
  for (let tries = 0; tries < 60; tries++) {
    try {
      res = await fetch(`/api/chats/${state.chatId}/voice`, { method: "POST", body: form, signal: call.abort.signal });
    } catch { return; }
    if (res.status !== 409) break;
    await new Promise((r) => setTimeout(r, 1000));
    if (!call.active || turn !== call.turn) return;
  }
  if (!res.ok) { toast(await errorMessage(res)); setCallState("listening"); return; }

  let aiText = "";
  call.waitingDone = true;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line || turn !== call.turn) continue;
        const ev = JSON.parse(line);
        if (ev.type === "transcript") {
          $("#call-you").textContent = ev.text ? `Tú: ${ev.text}` : "(no te he entendido)";
          $("#call-ai").textContent = "";
        } else if (ev.type === "token") {
          aiText += ev.text;
          $("#call-ai").textContent = aiText;
        } else if (ev.type === "discard") {
          aiText = "";
        } else if (ev.type === "tool") {
          $("#call-status").textContent = toolLabel(ev.name)[1] + "…";
        } else if (ev.type === "audio") {
          enqueueAudio(ev.data, turn);
        } else if (ev.type === "error") {
          $("#call-ai").textContent = ev.message;
        }
      }
    }
  } catch { /* llamada colgada o interrumpida */ }
  if (turn === call.turn) {
    call.waitingDone = false;
    if (!call.playing && call.queue.length === 0 && call.active) setCallState("listening");
  }
}

async function enqueueAudio(b64, turn) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const buffer = await call.ctx.decodeAudioData(bytes.buffer);
  if (turn !== call.turn || !call.active) return;
  call.queue.push(buffer);
  if (!call.playing) playNext();
}

function playNext() {
  const buffer = call.queue.shift();
  if (!buffer || !call.active) {
    call.playing = false;
    if (call.active && !call.waitingDone) setCallState("listening");
    return;
  }
  call.playing = true;
  setCallState("speaking");
  const src = call.ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(call.analyser);
  src.onended = () => { if (call.source === src) { call.source = null; playNext(); } };
  call.source = src;
  src.start();
}

function stopPlayback() {
  call.queue = [];
  if (call.source) {
    const src = call.source;
    call.source = null;
    try { src.stop(); } catch { /* ya parado */ }
  }
  call.playing = false;
}

function animateOrb() {
  if (!call.active) return;
  let level = call.level * 6;
  if (call.state === "speaking" && call.analyser) {
    const data = new Uint8Array(call.analyser.fftSize);
    call.analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const v of data) sum += ((v - 128) / 128) ** 2;
    level = Math.sqrt(sum / data.length) * 5;
  }
  if (call.state !== "thinking") {
    $("#orb").style.transform = `scale(${1 + Math.min(level, 0.45)})`;
  } else {
    $("#orb").style.transform = "";
  }
  requestAnimationFrame(animateOrb);
}

$("#start-call").addEventListener("click", startCall);
$("#call-end").addEventListener("click", endCall);
$("#call-mute").addEventListener("click", () => {
  call.muted = !call.muted;
  $("#call-mute").classList.toggle("active", call.muted);
  if (call.muted) Object.assign(call, { inSpeech: false, chunks: [], speechMs: 0, silenceMs: 0 });
  setCallState(call.state, call.muted ? "Micrófono silenciado" : undefined);
});

// ---------- Móvil ----------

function closeSidebar() {
  $("#sidebar").classList.remove("open");
  $("#backdrop").classList.remove("show");
}
$("#toggle-sidebar").addEventListener("click", () => {
  $("#sidebar").classList.add("open");
  $("#backdrop").classList.add("show");
});
$("#backdrop").addEventListener("click", closeSidebar);
$("#new-chat").addEventListener("click", () => { newChat(); closeSidebar(); });

// ---------- Inicio ----------

(async function init() {
  try {
    const info = await api("/api/info");
    document.title = info.name;
    $("#brand-name").textContent = info.name;
    $("#model-name").textContent = info.model;
  } catch { /* el servidor responderá luego */ }
  await loadChats();
  const id = location.hash.slice(1);
  if (id) openChat(id);
  else input.focus();
})();
