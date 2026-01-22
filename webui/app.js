const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// Simple event bus for sessionSelected routing
const bus = {
  handlers: {},
  on(evt, fn) { (this.handlers[evt] ||= []).push(fn); },
  emit(evt, payload) { (this.handlers[evt]||[]).forEach(fn => fn(payload)); }
};

// Tabs
$$('.tab').forEach(btn => btn.addEventListener('click', () => {
  $$('.tab').forEach(b => b.classList.remove('active'));
  $$('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const tabId = btn.getAttribute('data-tab');
  document.getElementById(tabId).classList.add('active');
}));

// State
let SESSIONS = [];
let CURRENT = null;

// Render Flow Overview list
function renderOverview(sessions) {
  const ul = $('#session-list');
  ul.innerHTML = '';
  sessions.forEach((s, i) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <div><strong>${s.title}</strong></div>
      <span class="meta">${s.type} • ${s.summary.version} • ${s.summary.sni || 'no SNI'}</span>
    `;
    if (CURRENT && CURRENT.id === s.id) li.classList.add('active');
    li.addEventListener('click', () => {
      bus.emit('sessionSelected', { id: s.id });
    });
    li.addEventListener('dblclick', () => {
      // Simulate Flow Overview double-click -> jump to TLS Flow tab
      bus.emit('sessionSelected', { id: s.id });
      // focus the first tab for clarity
      const firstTab = document.querySelector('.tab[data-tab="tab-overview"]');
      firstTab.click();
    });
    ul.appendChild(li);
  });
}

// Overview tab
function renderOverviewTab(s) {
  const el = $('#tab-overview');
  const badges = [];
  if (s.summary.chosenCipher?.includes('GCM')) badges.push('<span class="badge good">AEAD</span>');
  if (s.summary.chosenCipher?.includes('ECDHE')) badges.push('<span class="badge good">Forward Secrecy</span>');
  if (s.issues?.length) badges.push(`<span class="badge warn">${s.issues.length} issue(s)</span>`);

  el.innerHTML = `
    <div class="summary-grid">
      <div class="summary-card">
        <div><strong>SNI</strong></div>
        <div>${s.summary.sni || '<span class="muted">—</span>'}</div>
      </div>
      <div class="summary-card">
        <div><strong>Version</strong></div>
        <div>${s.summary.version || '<span class="muted">—</span>'}</div>
      </div>
      <div class="summary-card">
        <div><strong>Chosen Cipher</strong></div>
        <div>${s.summary.chosenCipher || '<span class="muted">—</span>'}</div>
      </div>
      <div class="summary-card">
        <div><strong>Session ID</strong></div>
        <div>${s.summary.sessionId ? s.summary.sessionId.slice(0, 16) + '…' : '<span class="muted">empty</span>'}</div>
      </div>
    </div>
    <div style="margin-top:10px;">${badges.join(' ')}</div>
  `;
}

// Timeline tab
function renderTimelineTab(s) {
  const el = $('#tab-timeline');
  const rows = s.events.map((ev, idx) => {
    const cls = ev.recordType === 'Alert' ? 'row-alert' : (ev.dir === 'SIM->ME' ? 'row-sim' : 'row-me');
    return `<tr class="${cls}" data-idx="${idx}">
      <td>${idx}</td>
      <td>${ev.ts || ''}</td>
      <td>${ev.dir}</td>
      <td>${ev.recordType}</td>
      <td>${ev.handshakeType || ''}</td>
      <td>${ev.len ?? ''}</td>
      <td>${ev.apduIndex ?? ''}</td>
    </tr>`;
  }).join('');
  el.innerHTML = `
    <table class="table">
      <thead>
        <tr><th>#</th><th>Time</th><th>Dir</th><th>Record</th><th>Handshake</th><th>Len</th><th>APDU</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// Ladder tab via Mermaid sequence diagram
function toMermaid(s) {
  const header = 'sequenceDiagram\n    participant SIM\n    participant ME\n';
  const body = s.events.map(ev => {
    const arrow = ev.dir === 'SIM->ME' ? 'SIM->>ME' : 'ME->>SIM';
    const label = ev.handshakeType ? `${ev.recordType}(${ev.handshakeType})` : ev.recordType;
    return `    ${arrow}: ${label}`;
  }).join('\n');
  return header + body;
}
async function renderLadderTab(s) {
  const m = toMermaid(s);
  const ladder = $('#ladder');
  ladder.textContent = m;
  await mermaid.run({ nodes: [ladder] });
}

// Handshake tab
function renderHandshakeTab(s) {
  const el = $('#tab-handshake');
  const cl = s.handshake?.clientHello || {};
  const sh = s.handshake?.serverHello || {};
  el.innerHTML = `
    <div class="tree">
      <dt>ClientHello</dt>
      <dd>version: <code class="inline">${cl.version || ''}</code></dd>
      <dd>random: <code class="inline">${cl.random || ''}</code></dd>
      <dd>session_id: <code class="inline">${cl.sessionId || ''}</code></dd>
      <dd>ciphers: ${cl.ciphers?.join(', ') || ''}</dd>
      <dd>extensions: ${cl.extensions?.join(', ') || ''}</dd>
      <dd>supported_groups: ${cl.supportedGroups?.join(', ') || ''}</dd>
      <dd>signature_algorithms: ${cl.signatureAlgorithms?.join(', ') || ''}</dd>
      <dd>ec_point_formats: ${cl.ecPointFormats?.join(', ') || ''}</dd>

      <dt style="margin-top:12px;">ServerHello</dt>
      <dd>version: <code class="inline">${sh.version || ''}</code></dd>
      <dd>random: <code class="inline">${sh.random || ''}</code></dd>
      <dd>session_id: <code class="inline">${sh.sessionId || ''}</code></dd>
      <dd>cipher: <code class="inline">${sh.cipher || ''}</code></dd>
      <dd>extensions: ${sh.extensions?.join(', ') || ''}</dd>
    </div>
  `;
}

// Certificates tab
function renderCertsTab(s) {
  const el = $('#tab-certs');
  const certs = s.certificates || [];
  if (!certs.length) { el.innerHTML = '<div class="muted">No certificates</div>'; return; }
  el.innerHTML = certs.map((c, i) => `
    <div class="summary-card">
      <div><strong>Certificate[${i+1}]</strong></div>
      <div>Subject: ${c.subject}</div>
      <div>Issuer: ${c.issuer}</div>
      <div>Valid: ${c.validFrom} → ${c.validTo}</div>
      <div>Key: ${c.publicKey}</div>
      <div>EKU: ${c.eku?.join(', ') || '—'}</div>
      <div>SAN: ${c.san?.join(', ') || '—'}</div>
    </div>
  `).join('');
}

// Raw tab
function renderRawTab(s) {
  $('#apdus').textContent = s.raw?.apdus || '';
  const recs = s.events.map((e, i) => `[${i}] ${e.dir} | ${e.recordType}${e.handshakeType ? ' ('+e.handshakeType+')' : ''}`).join('\n');
  $('#records').textContent = recs;
}

// Alerts tab
function renderAlertsTab(s) {
  const el = $('#tab-alerts');
  if (!s.issues || !s.issues.length) { el.innerHTML = '<div class="muted">No issues detected</div>'; return; }
  el.innerHTML = s.issues.map(x => `<div class="summary-card">${x}</div>`).join('');
}

function setCurrentById(id) {
  const s = SESSIONS.find(x => x.id === id);
  if (!s) return;
  CURRENT = s;
  renderOverview(SESSIONS);
  renderOverviewTab(s);
  renderTimelineTab(s);
  renderLadderTab(s);
  renderHandshakeTab(s);
  renderCertsTab(s);
  renderRawTab(s);
  renderAlertsTab(s);
}

bus.on('sessionSelected', ({ id }) => setCurrentById(id));

// JSON loader
$('#load-json').addEventListener('click', () => $('#file-input').click());
$('#file-input').addEventListener('change', async (ev) => {
  const file = ev.target.files?.[0];
  if (!file) return;
  const txt = await file.text();
  const data = JSON.parse(txt);
  SESSIONS = data.sessions || [];
  renderOverview(SESSIONS);
  if (SESSIONS.length) setCurrentById(SESSIONS[0].id);
});

// Initial load from sample
async function boot() {
  try {
    const res = await fetch('./sessions.sample.json');
    const data = await res.json();
    SESSIONS = data.sessions || [];
    renderOverview(SESSIONS);
    if (SESSIONS.length) setCurrentById(SESSIONS[0].id);
  } catch (e) {
    console.warn('No sample sessions found', e);
  }
}
boot();
