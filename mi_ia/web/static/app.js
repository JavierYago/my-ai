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
};

const TOOL_LABELS = {
  web_search: ["search", "Buscando en la web"],
  fetch_url: ["globe", "Leyendo página"],
  run_python: ["code", "Ejecutando código"],
  read_file: ["file", "Leyendo archivo"],
  write_file: ["file", "Guardando archivo"],
  list_files: ["file", "Mirando archivos"],
};

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
        const used = [...new Set(m.tools)].map((t) => (TOOL_LABELS[t] || [null, t])[1]);
        view.steps.before(Object.assign(el("div", "tools-used"), { textContent: "Usó: " + used.join(" · ") }));
      }
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
  const body = el("div", "md");
  const thinking = el("div", "thinking", "<span></span><span></span><span></span>");
  content.append(steps, thinking, body);
  root.append(content);
  $("#thread").append(root);
  return { root, content, steps, body, thinking };
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
        const [icon, label] = TOOL_LABELS[ev.name] || ["code", ev.name];
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
  code.textContent = ev.code;
  code.removeAttribute("data-highlighted");
  code.className = "language-python";
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
