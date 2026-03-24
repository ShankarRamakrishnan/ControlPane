"""
title: ControlPane Manifest Manager
author: ControlPane
description: Create, edit, and delete ControlPane agent manifests from OpenWebUI
version: 0.1.0
license: MIT
"""

import json
import httpx
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        CONTROLPANE_URL: str = Field(
            default="http://localhost:8000",
            description="URL this server uses to reach ControlPane (e.g. http://gateway:8000 in Docker)",
        )
        CONTROLPANE_BROWSER_URL: str = Field(
            default="http://localhost:8000",
            description="URL your browser uses to reach ControlPane (must be reachable from the client machine)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.id = "manifest-manager"
        self.name = "Manifest Manager"

    async def pipe(self, body: dict, __user__: dict = {}, **kwargs) -> str:
        server_url = self.valves.CONTROLPANE_URL.rstrip("/")
        browser_url = self.valves.CONTROLPANE_BROWSER_URL.rstrip("/")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{server_url}/manifests", timeout=5.0)
                manifests = resp.json() if resp.status_code == 200 else []
        except Exception as e:
            manifests = []

        return _build_ui(browser_url, manifests)


# ── HTML/CSS/JS UI ────────────────────────────────────────────────────────────

def _build_ui(browser_url: str, manifests: list) -> str:
    initial_json = json.dumps(manifests)
    return f"""
<div id="cp-mm" style="font-family:system-ui,sans-serif;border:1px solid #d1d5db;border-radius:8px;overflow:hidden;max-width:860px">

<style>
#cp-mm * {{ box-sizing:border-box;margin:0;padding:0 }}
#cp-mm .hdr {{ background:#1e293b;color:#f8fafc;padding:12px 16px;display:flex;align-items:center;justify-content:space-between }}
#cp-mm .hdr h2 {{ font-size:15px;font-weight:600;letter-spacing:.3px }}
#cp-mm .body {{ display:flex;height:520px }}
#cp-mm .sidebar {{ width:200px;border-right:1px solid #e2e8f0;overflow-y:auto;background:#f8fafc;flex-shrink:0 }}
#cp-mm .agent-item {{ padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid #e2e8f0;color:#374151;display:flex;align-items:center;gap:6px }}
#cp-mm .agent-item:hover {{ background:#e0e7ff }}
#cp-mm .agent-item.active {{ background:#e0e7ff;font-weight:600;color:#1d4ed8 }}
#cp-mm .agent-item .dot {{ width:7px;height:7px;border-radius:50%;background:#6366f1;flex-shrink:0 }}
#cp-mm .editor {{ flex:1;padding:16px;overflow-y:auto;background:#fff }}
#cp-mm .empty {{ color:#9ca3af;font-size:13px;padding:24px;text-align:center }}
#cp-mm .form-grid {{ display:grid;grid-template-columns:1fr 1fr;gap:12px }}
#cp-mm .form-full {{ grid-column:1/-1 }}
#cp-mm label {{ font-size:12px;font-weight:600;color:#6b7280;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px }}
#cp-mm input,#cp-mm select,#cp-mm textarea {{ width:100%;border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;font-size:13px;color:#111827;background:#fff;outline:none }}
#cp-mm input:focus,#cp-mm select:focus,#cp-mm textarea:focus {{ border-color:#6366f1;box-shadow:0 0 0 2px #e0e7ff }}
#cp-mm input[disabled] {{ background:#f3f4f6;color:#9ca3af }}
#cp-mm textarea {{ resize:vertical;min-height:80px;font-family:monospace }}
#cp-mm .actions {{ display:flex;gap:8px;margin-top:16px }}
#cp-mm .btn {{ padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;border:none }}
#cp-mm .btn-save {{ background:#4f46e5;color:#fff }}
#cp-mm .btn-save:hover {{ background:#4338ca }}
#cp-mm .btn-del {{ background:#fee2e2;color:#dc2626 }}
#cp-mm .btn-del:hover {{ background:#fecaca }}
#cp-mm .btn-new {{ background:#dcfce7;color:#16a34a;font-size:13px;padding:6px 12px }}
#cp-mm .btn-new:hover {{ background:#bbf7d0 }}
#cp-mm .status {{ font-size:12px;padding:6px 10px;border-radius:4px;margin-top:10px;display:none }}
#cp-mm .status.ok {{ background:#dcfce7;color:#166534;display:block }}
#cp-mm .status.err {{ background:#fee2e2;color:#991b1b;display:block }}
#cp-mm .section-title {{ font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#9ca3af;margin:16px 0 8px;padding-bottom:4px;border-bottom:1px solid #f1f5f9;grid-column:1/-1 }}
#cp-mm .checkbox-row {{ display:flex;align-items:center;gap:8px }}
#cp-mm .checkbox-row input {{ width:auto }}
#cp-mm .checkbox-row label {{ margin:0;text-transform:none;font-size:13px;color:#374151;font-weight:400 }}
</style>

<div class="hdr">
  <h2>⚙ ControlPane — Manifest Manager</h2>
  <button class="btn btn-new" onclick="cpNewManifest()">+ New Agent</button>
</div>

<div class="body">
  <div class="sidebar" id="cp-sidebar">
    <div class="empty">Loading…</div>
  </div>
  <div class="editor" id="cp-editor">
    <div class="empty">Select an agent or create a new one.</div>
  </div>
</div>

</div>

<script>
(function() {{
  const API = {json.dumps(browser_url)};
  let manifests = {initial_json};
  let selected = null;
  let isNew = false;

  function renderSidebar() {{
    const el = document.getElementById('cp-sidebar');
    if (!manifests.length) {{
      el.innerHTML = '<div class="empty">No agents yet.</div>';
      return;
    }}
    el.innerHTML = manifests.map(m => `
      <div class="agent-item ${{selected === m.name ? 'active' : ''}}" onclick="cpSelect('${{m.name}}')">
        <span class="dot"></span>${{m.name}}
      </div>`).join('');
  }}

  function renderEditor() {{
    const el = document.getElementById('cp-editor');
    if (!selected && !isNew) {{
      el.innerHTML = '<div class="empty">Select an agent or create a new one.</div>';
      return;
    }}
    const m = isNew ? {{}} : manifests.find(x => x.name === selected) || {{}};
    const model = m.model || {{}};
    const prompts = m.prompts || {{}};
    const obs = m.observability || {{}};
    const toolLines = (m.tools || []).map(t => t.description ? `${{t.name}}: ${{t.description}}` : t.name).join('\\n');

    el.innerHTML = `
      <div class="form-grid">
        <div class="section-title">Identity</div>

        <div>
          <label>Name *</label>
          <input id="f-name" value="${{m.name || ''}}" ${{!isNew ? 'disabled' : ''}} placeholder="my-agent"/>
        </div>
        <div>
          <label>Version</label>
          <input id="f-version" value="${{m.version || '1.0.0'}}" placeholder="1.0.0"/>
        </div>
        <div class="form-full">
          <label>Description</label>
          <input id="f-desc" value="${{m.description || ''}}" placeholder="What this agent does"/>
        </div>

        <div class="section-title">Model</div>

        <div>
          <label>Provider</label>
          <select id="f-provider">
            <option value="openai" ${{model.provider === 'openai' ? 'selected' : ''}}>OpenAI</option>
            <option value="anthropic" ${{model.provider === 'anthropic' ? 'selected' : ''}}>Anthropic</option>
          </select>
        </div>
        <div>
          <label>Model Name</label>
          <input id="f-model-name" value="${{model.name || ''}}" placeholder="gpt-4o / claude-3-5-sonnet-latest"/>
        </div>
        <div>
          <label>Temperature</label>
          <input id="f-temp" type="number" min="0" max="1" step="0.1" value="${{model.temperature ?? 0.7}}"/>
        </div>
        <div>
          <label>Max Tokens (optional)</label>
          <input id="f-max-tokens" type="number" min="1" value="${{model.max_tokens || ''}}" placeholder="leave blank for default"/>
        </div>

        <div class="section-title">Prompts</div>

        <div class="form-full">
          <label>System Prompt</label>
          <textarea id="f-system" rows="5" placeholder="You are a helpful assistant.">${{(prompts.system || '').trim()}}</textarea>
        </div>

        <div class="section-title">Tools</div>

        <div class="form-full">
          <label>Tools — one per line as &nbsp;<code>name: description</code></label>
          <textarea id="f-tools" rows="4" placeholder="web_search: Search the web&#10;calculator: Evaluate math expressions">${{toolLines}}</textarea>
        </div>

        <div class="section-title">Observability</div>

        <div class="form-full">
          <div class="checkbox-row">
            <input type="checkbox" id="f-trace" ${{obs.trace !== false ? 'checked' : ''}}/>
            <label for="f-trace">Enable LangSmith tracing</label>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-save" onclick="cpSave()">${{isNew ? 'Create Agent' : 'Save Changes'}}</button>
        ${{!isNew ? `<button class="btn btn-del" onclick="cpDelete('${{m.name}}')">Delete</button>` : ''}}
      </div>
      <div class="status" id="cp-status"></div>
    `;
  }}

  function parseTools(raw) {{
    return raw.split('\\n')
      .map(l => l.trim()).filter(Boolean)
      .map(l => {{
        const idx = l.indexOf(':');
        if (idx === -1) return {{ name: l, description: '', input_schema: {{}} }};
        return {{ name: l.slice(0, idx).trim(), description: l.slice(idx + 1).trim(), input_schema: {{}} }};
      }});
  }}

  function showStatus(msg, isErr) {{
    const el = document.getElementById('cp-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'status ' + (isErr ? 'err' : 'ok');
    if (!isErr) setTimeout(() => {{ el.className = 'status'; }}, 3000);
  }}

  window.cpSelect = function(name) {{
    selected = name; isNew = false;
    renderSidebar(); renderEditor();
  }};

  window.cpNewManifest = function() {{
    selected = null; isNew = true;
    renderSidebar(); renderEditor();
    document.getElementById('f-name')?.focus();
  }};

  window.cpSave = async function() {{
    const name = (document.getElementById('f-name')?.value || '').trim();
    if (!name) {{ showStatus('Name is required.', true); return; }}

    const maxTok = document.getElementById('f-max-tokens')?.value;
    const body = {{
      name,
      version: document.getElementById('f-version')?.value || '1.0.0',
      description: document.getElementById('f-desc')?.value || '',
      model: {{
        provider: document.getElementById('f-provider')?.value || 'openai',
        name: document.getElementById('f-model-name')?.value || '',
        temperature: parseFloat(document.getElementById('f-temp')?.value ?? 0.7),
        ...(maxTok ? {{ max_tokens: parseInt(maxTok) }} : {{}}),
      }},
      prompts: {{ system: document.getElementById('f-system')?.value || '' }},
      tools: parseTools(document.getElementById('f-tools')?.value || ''),
      observability: {{ trace: document.getElementById('f-trace')?.checked ?? true }},
    }};

    try {{
      const method = isNew ? 'POST' : 'PUT';
      const url = isNew ? `${{API}}/manifests` : `${{API}}/manifests/${{name}}`;
      const resp = await fetch(url, {{
        method,
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
      }});
      if (!resp.ok) {{
        const err = await resp.json().catch(() => ({{}}));
        showStatus(err.detail || `Error ${{resp.status}}`, true);
        return;
      }}
      const saved = await resp.json();
      if (isNew) {{
        manifests.push(saved);
      }} else {{
        const idx = manifests.findIndex(m => m.name === name);
        if (idx !== -1) manifests[idx] = saved;
      }}
      selected = name; isNew = false;
      renderSidebar(); renderEditor();
      showStatus(isNew ? 'Agent created.' : 'Saved.', false);
    }} catch (e) {{
      showStatus(`Request failed: ${{e.message}}`, true);
    }}
  }};

  window.cpDelete = async function(name) {{
    if (!confirm(`Delete "${{name}}"? This cannot be undone.`)) return;
    try {{
      const resp = await fetch(`${{API}}/manifests/${{name}}`, {{ method: 'DELETE' }});
      if (!resp.ok && resp.status !== 204) {{
        const err = await resp.json().catch(() => ({{}}));
        showStatus(err.detail || `Error ${{resp.status}}`, true);
        return;
      }}
      manifests = manifests.filter(m => m.name !== name);
      selected = null; isNew = false;
      renderSidebar(); renderEditor();
    }} catch (e) {{
      showStatus(`Request failed: ${{e.message}}`, true);
    }}
  }};

  renderSidebar();
  renderEditor();
}})();
</script>
"""
