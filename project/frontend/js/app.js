/* app.js — Boeing 737-800 AMM Chatbot frontend */

const API = "http://localhost:5000/api";

let currentSessionId = null;

// ── DOM refs ────────────────────────────────────────────────
const chatArea   = document.getElementById("chatArea");
const messages   = document.getElementById("messages");
const inputBox   = document.getElementById("inputBox");
const sendBtn    = document.getElementById("sendBtn");
const welcome    = document.getElementById("welcome");
const sessionList= document.getElementById("sessionList");
const chapterNav = document.getElementById("chapterNav");
const sourceBar  = document.getElementById("sourceBar");
const sourceChips= document.getElementById("sourceChips");
const topTitle   = document.getElementById("topTitle");
const statusDot  = document.getElementById("statusDot");
const newChatBtn = document.getElementById("newChatBtn");
const toggleBtn  = document.getElementById("toggleBtn");
const sidebar    = document.getElementById("sidebar");

// ── Boot ────────────────────────────────────────────────────
(async function init() {
  await checkHealth();
  await loadChapters();
  await loadSessions();

  // Suggestion chip clicks
  document.querySelectorAll(".chip").forEach(c => {
    c.addEventListener("click", () => {
      inputBox.value = c.dataset.q;
      sendMessage();
    });
  });
})();

// ── Sidebar toggle ──────────────────────────────────────────
toggleBtn.addEventListener("click", () => sidebar.classList.toggle("hidden"));
newChatBtn.addEventListener("click", newChat);

// ── Health check ────────────────────────────────────────────
async function checkHealth() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();
    statusDot.textContent = `●  ${data.db}  ·  ${data.ai.toUpperCase()}`;
    statusDot.className   = "status-dot ok";
  } catch {
    statusDot.textContent = "●  Server offline";
    statusDot.className   = "status-dot err";
  }
}

// ── Chapters ────────────────────────────────────────────────
async function loadChapters() {
  try {
    const res  = await fetch(`${API}/chapters`);
    const list = await res.json();
    chapterNav.innerHTML = "";
    list.forEach(ch => {
      const btn = document.createElement("button");
      btn.className   = "ch-item";
      btn.textContent = ch;
      btn.title       = ch;
      btn.addEventListener("click", () => {
        inputBox.value = `Give me an overview of: ${ch}`;
        sendMessage();
      });
      chapterNav.appendChild(btn);
    });
  } catch {
    chapterNav.innerHTML =
      '<span style="font-size:11px;color:var(--text-3);padding:4px 8px">Run ingest.py first</span>';
  }
}

// ── Sessions ────────────────────────────────────────────────
async function loadSessions() {
  try {
    const res  = await fetch(`${API}/sessions`);
    const list = await res.json();
    renderSessions(list);
  } catch {
    sessionList.innerHTML =
      '<span style="font-size:11px;color:var(--text-3);padding:4px 8px">Unavailable</span>';
  }
}

function renderSessions(list) {
  sessionList.innerHTML = "";
  if (!list.length) {
    sessionList.innerHTML =
      '<span style="font-size:11px;color:var(--text-3);padding:4px 8px">No sessions yet</span>';
    return;
  }
  list.forEach(s => {
    const item = document.createElement("div");
    item.className = "sess-item" + (s.id === currentSessionId ? " active" : "");
    item.innerHTML = `
      <span class="sess-icon">💬</span>
      <span class="sess-title" title="${s.title || ''}">${s.title || "Untitled"}</span>
      <button class="sess-del" title="Delete">✕</button>
    `;
    item.querySelector(".sess-del").addEventListener("click", async e => {
      e.stopPropagation();
      await fetch(`${API}/sessions/${s.id}`, { method: "DELETE" });
      if (currentSessionId === s.id) newChat();
      else loadSessions();
    });
    item.addEventListener("click", () => openSession(s.id));
    sessionList.appendChild(item);
  });
}

async function openSession(id) {
  try {
    const res  = await fetch(`${API}/sessions/${id}`);
    const data = await res.json();
    currentSessionId = id;
    messages.innerHTML = "";
    welcome.classList.add("hidden");
    sourceBar.style.display = "none";
    topTitle.textContent = data.session.title || "Conversation";
    data.messages.forEach(m => addBubble(m.role, m.content));
    scrollDown();
    loadSessions();
  } catch (e) { console.error(e); }
}

function newChat() {
  currentSessionId = null;
  messages.innerHTML = "";
  welcome.classList.remove("hidden");
  sourceBar.style.display = "none";
  topTitle.textContent = "New Conversation";
  inputBox.value = "";
  inputBox.style.height = "auto";
  loadSessions();
}

// ── Send ─────────────────────────────────────────────────────
sendBtn.addEventListener("click", sendMessage);
inputBox.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
inputBox.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 110) + "px";
});

async function sendMessage() {
  const text = inputBox.value.trim();
  if (!text || sendBtn.disabled) return;

  welcome.classList.add("hidden");
  addBubble("user", text);
  inputBox.value = "";
  inputBox.style.height = "auto";
  sendBtn.disabled = true;

  const typingEl = addTyping();
  scrollDown();

  try {
    const res = await fetch(`${API}/chat`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ message: text, session_id: currentSessionId }),
    });
    const data = await res.json();
    typingEl.remove();

    if (res.ok) {
      currentSessionId = data.session_id;
      addBubble("assistant", data.reply);
      showSources(data.source_chapters || []);
      topTitle.textContent = text.slice(0, 55) + (text.length > 55 ? "…" : "");
      loadSessions();
    } else {
      addBubble("assistant", `❌ Error: ${data.error || "Unknown error"}`);
    }
  } catch {
    typingEl.remove();
    addBubble("assistant",
      "❌ Cannot reach the server. Make sure Flask is running:\n\n`python app.py`");
  }

  sendBtn.disabled = false;
  scrollDown();
}

// ── Render helpers ───────────────────────────────────────────
function addBubble(role, content) {
  const row = document.createElement("div");
  row.className = "msg-row " + role;
  row.innerHTML = `
    <div class="avatar ${role === "user" ? "user" : "ai"}">
      ${role === "user" ? "👤" : "🤖"}
    </div>
    <div class="bubble">${format(content)}</div>
  `;
  messages.appendChild(row);
  return row;
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.innerHTML = `
    <div class="avatar ai">🤖</div>
    <div class="bubble">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>
  `;
  messages.appendChild(row);
  return row;
}

function format(text) {
  return text
    .replace(/\bWARNING[:\s]+([^\n]+)/gi,
      '<div class="box-warn">⚠️ <strong>WARNING:</strong> $1</div>')
    .replace(/\bCAUTION[:\s]+([^\n]+)/gi,
      '<div class="box-caut">🔶 <strong>CAUTION:</strong> $1</div>')
    .replace(/\bNOTE[:\s]+([^\n]+)/gi,
      '<div class="box-note">📌 <strong>NOTE:</strong> $1</div>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g,   "<em>$1</em>")
    .replace(/`([^`]+)`/g,       "<code>$1</code>")
    .replace(/^(\d+)\.\s+(.+)$/gm, "<li><strong>$1.</strong> $2</li>")
    .replace(/^[-•]\s+(.+)$/gm,    "<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g,     "<br>")
    .replace(/^(.)/,    "<p>$1")
    .replace(/(.)$/,    "$1</p>");
}

function showSources(chapters) {
  if (!chapters.length) { sourceBar.style.display = "none"; return; }
  sourceChips.innerHTML = chapters.map(
    ch => `<span class="src-chip">${ch}</span>`
  ).join("");
  sourceBar.style.display = "flex";
}

function scrollDown() {
  setTimeout(() => { chatArea.scrollTop = chatArea.scrollHeight; }, 50);
}
