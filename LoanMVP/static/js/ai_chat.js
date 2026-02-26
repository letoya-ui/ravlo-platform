async function sendMessage() {
  const input = document.getElementById("user-input");
  const message = input.value;
  const role = "loan_officer"; // dynamic later

  const response = await fetch("/api/ai_chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, message })
  });

  const data = await response.json();
  document.getElementById("messages").innerHTML += `<p>${data.reply}</p>`;
  input.value = "";
}
