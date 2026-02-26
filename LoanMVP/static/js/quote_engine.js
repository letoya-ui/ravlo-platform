document.getElementById('quoteForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/quote/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  const q = await res.json();
  document.getElementById('quoteResult').innerHTML = `
    <div class='alert alert-info'>
      <strong>${q.lender}</strong><br>
      Type: ${q.loan_type}<br>
      Term: ${q.term}<br>
      Rate: ${q.rate}%<br>
      Payment: $${q.monthly_payment}
    </div>`;
});