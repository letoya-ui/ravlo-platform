console.log("✅ CM Assistant Widget JS Loaded");

// ====================================
// CM Assistant Floating Widget (Animated)
// ====================================

document.addEventListener("DOMContentLoaded", () => {
  // Prevent duplicates if script runs twice
  if (document.getElementById("ai-widget")) return;

  const aiWidget = document.createElement("div");
  aiWidget.id = "ai-widget";
  aiWidget.innerHTML = `
    <button id="ai-toggle">🤖 CM Assistant</button>
    <div id="ai-window" class="hidden">
      <div id="ai-header">
        <span>CM Assistant</span>
        <button id="ai-close" title="Close">×</button>
      </div>
      <div id="ai-chat-box"></div>
      <form id="ai-form">
        <input type="text" id="ai-input" placeholder="Ask me anything..." autocomplete="off" />
        <button type="submit">Send</button>
      </form>
    </div>
  `;
  document.body.appendChild(aiWidget);

  const toggleBtn = document.getElementById("ai-toggle");
  const chatWindow = document.getElementById("ai-window");
  const closeBtn = document.getElementById("ai-close");
  const chatBox = document.getElementById("ai-chat-box");
  const aiForm = document.getElementById("ai-form");
  const aiInput = document.getElementById("ai-input");

  // --- OPEN CHAT ---
toggleBtn.addEventListener("click", () => {
  chatWindow.classList.remove("hidden");
  chatWindow.classList.add("slide-in");
  toggleBtn.classList.add("hidden"); // hide button using CSS, not inline
});

// --- CLOSE CHAT ---
closeBtn.addEventListener("click", () => {
  chatWindow.classList.add("slide-out");
  chatWindow.classList.remove("slide-in");
  setTimeout(() => {
    chatWindow.classList.add("hidden");
    chatWindow.classList.remove("slide-out");
    toggleBtn.classList.remove("hidden"); // show button again
  }, 300);
});


  // --- SEND MESSAGE ---
  aiForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = aiInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    aiInput.value = "";
    appendMessage("bot", "⏳ Thinking...");

    try {
      const res = await fetch("/api/ai_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          role: document.body.dataset.role || "general",
        }),
      });

      const data = await res.json();
      chatBox.removeChild(chatBox.lastElementChild); // remove "Thinking..."
      appendMessage("bot", data.reply || "⚠️ No reply received.");
    } catch (err) {
      console.error("AI fetch error:", err);
      chatBox.removeChild(chatBox.lastElementChild);
      appendMessage("bot", "⚠️ Connection error. Please try again.");
    }
  });

  function appendMessage(sender, text) {
    const msg = document.createElement("div");
    msg.classList.add(sender === "user" ? "user-msg" : "bot-msg");
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
  }
});
