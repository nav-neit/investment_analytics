/* AI Assistant — mounts either as a slide-out panel (default, with a floating
   action button) or full-page when a #chat-root element exists (assistant.html).
   Session id persists in localStorage; conversation exports as .md. */

const CHAT_SESSION_KEY = "quantartha_chat_session";

function chatSessionId() {
  let id = localStorage.getItem(CHAT_SESSION_KEY);
  if (!id) {
    id = "s_" + Math.random().toString(36).slice(2, 12);
    localStorage.setItem(CHAT_SESSION_KEY, id);
  }
  return id;
}

document.addEventListener("DOMContentLoaded", () => {
  const fullRoot = document.getElementById("chat-root");
  const panel = el(`
    <div class="chat-panel ${fullRoot ? "fullpage" : ""}" id="chat-panel">
      <div class="chat-head">
        <h2>✦ QuantArtha Assistant</h2>
        <span class="backend-tag" id="chat-backend"></span>
        <button class="btn-ghost btn" id="chat-export" title="Download conversation as Markdown">⬇ Save</button>
        <button class="btn-ghost btn" id="chat-clear" title="Clear conversation">Clear</button>
        ${fullRoot ? "" : '<button class="btn-ghost btn" id="chat-close" title="Close">✕</button>'}
      </div>
      <div class="chat-body" id="chat-body"></div>
      <div class="chat-input">
        <textarea id="chat-text" placeholder="Ask about indices, allocations, news…"></textarea>
        <button class="btn btn-accent" id="chat-send">Send</button>
      </div>
      <div class="chat-hint">Answers use live platform context (indices + news). Not investment advice.</div>
    </div>`);

  if (fullRoot) {
    fullRoot.appendChild(panel);
  } else {
    document.body.appendChild(panel);
    const fab = el('<button class="chat-fab" title="Open assistant">✦</button>');
    document.body.appendChild(fab);
    fab.addEventListener("click", () => panel.classList.add("open"));
    panel.querySelector("#chat-close").addEventListener("click", () => panel.classList.remove("open"));
  }

  const body = panel.querySelector("#chat-body");
  const text = panel.querySelector("#chat-text");
  const send = panel.querySelector("#chat-send");

  function addMsg(role, content, thinking = false) {
    const div = el(`<div class="msg ${role} ${thinking ? "thinking" : ""}"></div>`);
    if (role === "assistant" && !thinking) div.innerHTML = mdToHtml(content);
    else div.textContent = content;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }

  API.get("/api/chat/status").then((s) => {
    panel.querySelector("#chat-backend").textContent = s.available ? `LLM: ${s.backend}` : "no LLM configured";
  }).catch(() => {});

  API.get(`/api/chat/history/${chatSessionId()}`).then(({ messages }) => {
    if (!messages.length) {
      addMsg("assistant", "Hello! I'm the QuantArtha assistant. Ask me about the five tracked indices, model allocations, or today's market news.");
    } else {
      messages.forEach((m) => addMsg(m.role, m.content));
    }
  }).catch(() => addMsg("assistant", "Chat service unavailable — is the backend running?"));

  async function submit() {
    const msg = text.value.trim();
    if (!msg) return;
    text.value = "";
    addMsg("user", msg);
    const pending = addMsg("assistant", "thinking…", true);
    send.disabled = true;
    try {
      const r = await API.post("/api/chat", { session_id: chatSessionId(), message: msg });
      pending.classList.remove("thinking");
      pending.innerHTML = mdToHtml(r.reply);
    } catch (err) {
      pending.classList.remove("thinking");
      pending.textContent = "Error: " + err.message;
    } finally {
      send.disabled = false;
      body.scrollTop = body.scrollHeight;
    }
  }
  send.addEventListener("click", submit);
  text.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  });

  panel.querySelector("#chat-clear").addEventListener("click", async () => {
    await API.del(`/api/chat/history/${chatSessionId()}`).catch(() => {});
    body.innerHTML = "";
    addMsg("assistant", "Conversation cleared. What would you like to explore?");
  });

  panel.querySelector("#chat-export").addEventListener("click", async () => {
    const { messages } = await API.get(`/api/chat/history/${chatSessionId()}`).catch(() => ({ messages: [] }));
    if (!messages.length) return;
    const md = [
      `# QuantArtha Assistant — conversation export`,
      `_${new Date().toLocaleString("en-IN")}_`, "",
      ...messages.map((m) => `**${m.role === "user" ? "You" : "Assistant"}:**\n\n${m.content}\n`),
    ].join("\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `quantartha_chat_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
});
