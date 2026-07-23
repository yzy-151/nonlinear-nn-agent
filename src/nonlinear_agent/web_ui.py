from __future__ import annotations


def render_home_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nonlinear Agent Harness</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d2733;
      --muted: #667085;
      --line: #c7d0dc;
      --accent: #0f766e;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    header {
      padding: 28px 36px 18px;
      background: var(--panel);
      border-bottom: 2px solid var(--line);
    }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    h2 { margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }
    p { margin: 0; color: var(--muted); line-height: 1.55; }
    main { padding: 24px 36px 40px; display: grid; gap: 20px; }
    section {
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .grid { display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 20px; align-items: start; }
    label { display: block; margin: 12px 0 6px; font-weight: 650; }
    input, select, textarea {
      width: 100%;
      border: 2px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 96px; resize: vertical; }
    button, a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      padding: 8px 13px;
      margin-top: 14px;
      border: 2px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      font-weight: 700;
      cursor: pointer;
    }
    a.secondary {
      background: #fff;
      color: var(--accent);
      margin-left: 8px;
    }
    pre {
      min-height: 430px;
      max-height: 620px;
      overflow: auto;
      margin: 0;
      padding: 14px;
      border: 2px solid var(--line);
      border-radius: 8px;
      background: #101828;
      color: #e4e7ec;
      font: 13px/1.5 "Cascadia Mono", Consolas, monospace;
      white-space: pre-wrap;
    }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
    .card { border: 2px solid var(--line); border-radius: 8px; padding: 13px; background: #fbfcfe; }
    .card strong { display: block; margin-bottom: 6px; }
    .error { color: var(--danger); }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      header, main { padding-left: 18px; padding-right: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Nonlinear Agent Harness</h1>
    <p>Local demo UI for the Agent Harness runtime, streaming tool events, diagnostics, and onboarding links.</p>
  </header>
  <main>
    <section>
      <h2>Quick Links</h2>
      <div class="cards">
        <div class="card"><strong>Dashboard</strong><a class="button secondary" href="/diagnostics/agent-runtime-dashboard.html">Open HTML</a></div>
        <div class="card"><strong>Markdown Diagnostics</strong><a class="button secondary" href="/diagnostics/agent-runtime-dashboard.md">Open MD</a></div>
        <div class="card"><strong>Health</strong><a class="button secondary" href="/health">Check API</a></div>
      </div>
    </section>
    <div class="grid">
      <section>
        <h2>Run Harness Demo</h2>
        <form id="runForm">
          <label for="sessionId">Session ID</label>
          <input id="sessionId" value="ui-demo-001">
          <label for="goal">Goal</label>
          <textarea id="goal">Run nonlinear NN experiment through the Agent Harness streaming runtime.</textarea>
          <label for="epochs">Epochs</label>
          <input id="epochs" type="number" min="0" value="0">
          <label for="threshold">NMSE Threshold dB</label>
          <input id="threshold" type="number" step="0.1" value="-35">
          <label for="timeout">Timeout Seconds</label>
          <input id="timeout" type="number" min="1" value="120">
          <button type="submit">Start Streaming Run</button>
        </form>
      </section>
      <section>
        <h2>Runtime Events</h2>
        <pre id="events">Ready.</pre>
      </section>
    </div>
  </main>
  <script>
    const form = document.getElementById('runForm');
    const eventsBox = document.getElementById('events');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      eventsBox.textContent = '';
      const sessionId = document.getElementById('sessionId').value.trim() || 'ui-demo-001';
      const body = {
        goal: document.getElementById('goal').value,
        epochs: Number(document.getElementById('epochs').value),
        nmse_threshold_db: Number(document.getElementById('threshold').value),
        timeout_seconds: Number(document.getElementById('timeout').value)
      };
      try {
        const response = await fetch(`/runs/${encodeURIComponent(sessionId)}/events`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body)
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          eventsBox.textContent += decoder.decode(value, {stream: true});
          eventsBox.scrollTop = eventsBox.scrollHeight;
        }
      } catch (error) {
        eventsBox.innerHTML += `\\n<span class="error">${String(error)}</span>`;
      }
    });
  </script>
</body>
</html>
"""
