const state = {
  sessionId: null,
  isListening: false,
  isSpeaking: false,
  recognition: null,
  activeLang: 'en',
  availableSlots: [],
};

const SCENARIOS = {
  enterprise:
    "Hi, I'm Priya Nair, VP of Sales at VelocityTech. We have 35 sales reps and our biggest problem is slow lead response and manual CRM entry. We need to fix this this month.",
  objection:
    'Sounds interesting, but we are worried about SOC 2 security and whether the Growth plan is too expensive compared to basic dialers.',
  bant_book:
    'Okay, $899 per month fits our budget and my email is priya@velocitytech.io. Yes, please book tomorrow at 10:00 AM for a live demo.',
  hindi:
    'Namaste, kya aap Hindi mein baat kar sakte hain? Humari team ke liye pricing aur setup kitna samay leta hai?',
};

const els = {
  providerBadge: document.getElementById('providerBadge'),
  languageSelect: document.getElementById('languageSelect'),
  btnNewCall: document.getElementById('btnNewCall'),
  btnEndCall: document.getElementById('btnEndCall'),
  btnMic: document.getElementById('btnMic'),
  micLabel: document.getElementById('micLabel'),
  chkTts: document.getElementById('chkTts'),
  chkContinuous: document.getElementById('chkContinuous'),
  callStatusChip: document.getElementById('callStatusChip'),
  voiceStateText: document.getElementById('voiceStateText'),
  interimBox: document.getElementById('interimBox'),
  turnInput: document.getElementById('turnInput'),
  btnSendTurn: document.getElementById('btnSendTurn'),
  textTurnForm: document.getElementById('textTurnForm'),
  transcriptList: document.getElementById('transcriptList'),
  sessionIdBadge: document.getElementById('sessionIdBadge'),
  bantTierBadge: document.getElementById('bantTierBadge'),
  bantBarFill: document.getElementById('bantBarFill'),
  bantBudget: document.getElementById('bantBudget'),
  bantAuthority: document.getElementById('bantAuthority'),
  bantNeed: document.getElementById('bantNeed'),
  bantTimeline: document.getElementById('bantTimeline'),
  memoryList: document.getElementById('memoryList'),
  sentimentTrack: document.getElementById('sentimentTrack'),
  ragHitsList: document.getElementById('ragHitsList'),
  bookingStatusBox: document.getElementById('bookingStatusBox'),
  waveformCanvas: document.getElementById('waveformCanvas'),
  configModal: document.getElementById('configModal'),
};

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// --- Animated Luxury Mirrored Voice Waveform ---
function drawWaveform() {
  const ctx = els.waveformCanvas.getContext('2d');
  const { width, height } = els.waveformCanvas;
  ctx.clearRect(0, 0, width, height);

  const active = state.isListening || state.isSpeaking;
  const bars = 42;
  const barWidth = width / bars;
  const now = Date.now() / 110;

  const grad = ctx.createLinearGradient(0, 0, width, 0);
  if (state.isListening) {
    grad.addColorStop(0, '#10b981');
    grad.addColorStop(0.5, '#34d399');
    grad.addColorStop(1, '#f5d076');
  } else if (state.isSpeaking) {
    grad.addColorStop(0, '#6366f1');
    grad.addColorStop(0.5, '#f5d076');
    grad.addColorStop(1, '#8b5cf6');
  } else {
    grad.addColorStop(0, 'rgba(148, 163, 184, 0.28)');
    grad.addColorStop(0.5, 'rgba(245, 208, 118, 0.35)');
    grad.addColorStop(1, 'rgba(148, 163, 184, 0.28)');
  }

  ctx.fillStyle = grad;
  for (let i = 0; i < bars; i++) {
    const centerWeight = 1 - Math.abs(i - bars / 2) / (bars / 2) * 0.45;
    const amp = active
      ? ((Math.sin(now + i * 0.42) * 0.5 + 0.5) * (height * 0.68) + 8) * centerWeight
      : 4 + Math.sin(now * 0.35 + i * 0.3) * 2;
    const x = i * barWidth + 2;
    const y = (height - amp) / 2;
    const w = Math.max(2.5, barWidth - 4);
    ctx.beginPath();
    ctx.roundRect(x, y, w, amp, 99);
    ctx.fill();
  }
  requestAnimationFrame(drawWaveform);
}
requestAnimationFrame(drawWaveform);

// --- Web Speech TTS with Barge-in Support ---
function stopSpeaking() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  state.isSpeaking = false;
}

function speakText(text, bcp47 = 'en-US') {
  if (!els.chkTts.checked || !('speechSynthesis' in window)) return;
  stopSpeaking();

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = bcp47;
  utter.rate = 1.03;

  const voices = window.speechSynthesis.getVoices();
  const matched =
    voices.find((v) => v.lang.toLowerCase() === bcp47.toLowerCase()) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(bcp47.slice(0, 2).toLowerCase()));
  if (matched) utter.voice = matched;

  utter.onstart = () => {
    state.isSpeaking = true;
    els.voiceStateText.textContent = `Aria speaking (${bcp47})...`;
  };
  utter.onend = () => {
    state.isSpeaking = false;
    els.voiceStateText.textContent = state.isListening ? 'Listening for prospect...' : 'Ready for next turn';
    if (els.chkContinuous.checked && state.sessionId && !state.isListening) {
      startListening();
    }
  };
  window.speechSynthesis.speak(utter);
}

// --- Web Speech STT ---
function initRecognition() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) return null;

  const rec = new SpeechRec();
  rec.interimResults = true;
  rec.continuous = false;
  rec.lang = mapLangToBcp47(state.activeLang);

  rec.onstart = () => {
    stopSpeaking(); // Barge-in: user speaking cancels agent audio
    state.isListening = true;
    els.micLabel.textContent = 'Listening... Click to Stop';
    els.voiceStateText.textContent = `Listening (${rec.lang})...`;
  };

  rec.onresult = (event) => {
    let interim = '';
    let finalText = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const t = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += t;
      else interim += t;
    }
    if (interim) {
      els.interimBox.textContent = `Interim STT: ${interim}`;
      els.interimBox.classList.remove('hidden');
    }
    if (finalText.trim()) {
      els.interimBox.classList.add('hidden');
      sendTurn(finalText.trim());
    }
  };

  rec.onerror = (e) => {
    state.isListening = false;
    els.micLabel.textContent = 'Hold / Toggle Mic (STT)';
    els.interimBox.classList.add('hidden');
    els.voiceStateText.textContent = `Mic note: ${e.error} (text & simulator always ready)`;
  };

  rec.onend = () => {
    state.isListening = false;
    els.micLabel.textContent = 'Hold / Toggle Mic (STT)';
  };

  return rec;
}

function mapLangToBcp47(code) {
  return { en: 'en-US', hi: 'hi-IN', es: 'es-ES', fr: 'fr-FR', de: 'de-DE' }[code] || 'en-US';
}

function startListening() {
  if (!state.sessionId) return;
  if (!state.recognition) state.recognition = initRecognition();
  if (!state.recognition) {
    els.voiceStateText.textContent = 'Web Speech STT unavailable in this browser — use text or 1-Click Simulator.';
    return;
  }
  state.recognition.lang = mapLangToBcp47(state.activeLang);
  try {
    state.recognition.start();
  } catch {
    // Ignore already-started race
  }
}

function toggleMic() {
  if (state.isListening && state.recognition) {
    state.recognition.stop();
  } else {
    startListening();
  }
}

// --- Call Lifecycle ---
async function startNewCall() {
  stopSpeaking();
  const lang = els.languageSelect.value;
  const data = await api('/api/calls/start', {
    method: 'POST',
    body: JSON.stringify({ language: lang }),
  });

  state.sessionId = data.session.id;
  state.activeLang = lang;
  els.providerBadge.textContent = data.provider;
  els.sessionIdBadge.textContent = data.session.id;
  els.callStatusChip.textContent = 'Live Call';
  els.callStatusChip.className = 'badge badge-accent';

  els.btnEndCall.disabled = false;
  els.btnMic.disabled = false;
  els.turnInput.disabled = false;
  els.btnSendTurn.disabled = false;

  renderSession(data.session);
  await loadCRM();
  speakText(data.reply, data.languageMeta.bcp47);
}

async function sendTurn(text) {
  if (!state.sessionId || !text.trim()) return;
  els.turnInput.value = '';
  els.voiceStateText.textContent = 'Thinking (RAG + BANT + LLM)...';

  const data = await api(`/api/calls/${state.sessionId}/turn`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });

  state.activeLang = data.session.language;
  els.languageSelect.value = state.activeLang;
  state.availableSlots = data.availableSlots || [];

  renderSession(data.session, data.ragHits, data.availableSlots);
  await loadCRM();
  speakText(data.reply, data.languageMeta.bcp47);
}

async function endCall() {
  if (!state.sessionId) return;
  stopSpeaking();
  if (state.isListening && state.recognition) state.recognition.stop();

  const data = await api(`/api/calls/${state.sessionId}/end`, { method: 'POST', body: '{}' });
  els.callStatusChip.textContent = 'Completed';
  els.callStatusChip.className = 'badge badge-primary';
  els.btnEndCall.disabled = true;
  els.btnMic.disabled = true;
  els.turnInput.disabled = true;
  els.btnSendTurn.disabled = true;
  els.voiceStateText.textContent = 'Call summarized & synced to CRM';

  renderSession(data.session);
  await loadCRM();
  // Switch smoothly or highlight summary availability
  appendSystemBanner(`Call Summary Saved (${data.summary.tier} · BANT ${data.summary.bantScore}/100): ${data.summary.executiveSummary}`);
}

function appendSystemBanner(text) {
  const div = document.createElement('div');
  div.className = 'info-card';
  div.innerHTML = `<strong>Post-Call Intelligence</strong><p style="margin:4px 0 0">${escapeHtml(text)}</p>`;
  els.transcriptList.appendChild(div);
  els.transcriptList.scrollTop = els.transcriptList.scrollHeight;
}

function renderSession(session, lastRagHits = [], availableSlots = []) {
  // Transcript
  els.transcriptList.innerHTML = '';
  for (const turn of session.turns) {
    const div = document.createElement('div');
    div.className = `msg ${turn.role === 'user' ? 'msg-user' : 'msg-assistant'}`;

    const sentBadge = turn.sentiment
      ? `<span class="badge ${turn.sentiment.label === 'Positive' ? 'badge-accent' : turn.sentiment.label === 'Frustrated' ? 'badge-danger' : 'badge-warn'}">${turn.sentiment.label} (${turn.sentiment.score})</span>`
      : '';
    const latencyBadge = turn.latencyMs ? `<span>${turn.latencyMs}ms</span>` : '';
    const langBadge = `<span class="badge badge-neutral">${turn.language.toUpperCase()}</span>`;

    const ragPills = (turn.role === 'assistant' ? turn.ragHits || [] : [])
      .map((r) => `<span class="rag-pill">${escapeHtml(r.title)} (${Math.round(r.score * 100)}%)</span>`)
      .join('');

    div.innerHTML = `
      <div class="msg-meta">
        <strong>${turn.role === 'user' ? 'Prospect' : 'Aria (AI)'}</strong>
        ${langBadge}
        ${sentBadge}
        ${latencyBadge}
      </div>
      <div class="msg-text">${escapeHtml(turn.text)}</div>
      ${ragPills ? `<div>${ragPills}</div>` : ''}
    `;
    els.transcriptList.appendChild(div);
  }
  els.transcriptList.scrollTop = els.transcriptList.scrollHeight;

  // BANT Gauge
  const { score, tier, breakdown } = session.bant;
  els.bantBarFill.style.width = `${score}%`;
  els.bantTierBadge.textContent = `${tier} · ${score}/100`;
  els.bantTierBadge.className = `badge ${tier === 'Hot' ? 'badge-accent' : tier === 'Warm' ? 'badge-warn' : 'badge-neutral'}`;

  setBantBox(els.bantBudget, 'Budget', session.profile.budget, breakdown.budget > 0);
  setBantBox(els.bantAuthority, 'Authority', session.profile.authority, breakdown.authority > 0);
  setBantBox(els.bantNeed, 'Need', session.profile.need, breakdown.need > 0);
  setBantBox(els.bantTimeline, 'Timeline', session.profile.timeline, breakdown.timeline > 0);

  // Memory
  const p = session.profile;
  els.memoryList.innerHTML = `
    <div><dt>Prospect</dt><dd>${escapeHtml(p.name || '—')}${p.email ? ` (${escapeHtml(p.email)})` : ''}</dd></div>
    <div><dt>Company / Role</dt><dd>${escapeHtml(p.company || '—')}${p.role ? ` · ${escapeHtml(p.role)}` : ''}</dd></div>
    <div><dt>Team Size</dt><dd>${p.teamSize ? `${p.teamSize} reps` : '—'}</dd></div>
    <div><dt>Language</dt><dd>${escapeHtml(session.language.toUpperCase())}</dd></div>
    <div><dt>Objections</dt><dd>${p.objections?.length ? escapeHtml(p.objections.join(', ')) : 'None'}</dd></div>
  `;

  // Sentiment Trajectory
  if (session.sentimentHistory.length) {
    els.sentimentTrack.innerHTML = session.sentimentHistory
      .map(
        (s) =>
          `<span class="badge ${s.label === 'Positive' ? 'badge-accent' : s.label === 'Frustrated' ? 'badge-danger' : 'badge-warn'}">T${s.turn}: ${s.label}</span>`
      )
      .join('');
  } else {
    els.sentimentTrack.innerHTML = '<span class="muted">Waiting for first user turn...</span>';
  }

  // RAG Hits
  const ragToShow = lastRagHits.length ? lastRagHits : session.ragCitations.slice(-3);
  if (ragToShow.length) {
    els.ragHitsList.innerHTML = ragToShow
      .map(
        (r) =>
          `<div class="rag-card"><strong>${escapeHtml(r.title)}</strong> <span class="badge badge-primary">${Math.round(r.score * 100)}%</span><div class="muted" style="margin-top:4px">${escapeHtml(r.content)}</div></div>`
      )
      .join('');
  } else {
    els.ragHitsList.innerHTML = '<span class="muted">No specific KB chunk triggered yet.</span>';
  }

  // Booking / Slots
  if (p.appointmentBooked) {
    const apt = p.appointmentBooked;
    els.bookingStatusBox.innerHTML = `
      <div class="slot-card" style="border-color: rgba(16,185,129,0.6)">
        <div>
          <strong>Confirmed: ${escapeHtml(apt.dayLabel)} · ${escapeHtml(apt.time)}</strong>
          <div class="muted">${escapeHtml(apt.meetingLink)}</div>
        </div>
        <span class="badge badge-accent">Booked</span>
      </div>`;
  } else if (availableSlots.length) {
    els.bookingStatusBox.innerHTML = availableSlots
      .map(
        (s) => `
        <div class="slot-card">
          <div><strong>${escapeHtml(s.dayLabel)}</strong> · ${escapeHtml(s.time)}</div>
          <button class="btn btn-sm btn-primary" onclick="window.bookSlotManual('${s.slotId}')">Book</button>
        </div>`
      )
      .join('');
  }
}

function setBantBox(el, title, val, ok) {
  el.className = `bant-item ${ok ? 'ok' : ''}`;
  el.innerHTML = `<span>${title}</span><strong>${escapeHtml(val || 'Missing')}</strong>`;
}

window.bookSlotManual = async (slotId) => {
  if (!state.sessionId) return;
  const sessionRes = await api(`/api/calls/${state.sessionId}`);
  const p = sessionRes.session.profile;
  await api('/api/crm/book', {
    method: 'POST',
    body: JSON.stringify({
      sessionId: state.sessionId,
      prospectName: p.name,
      email: p.email,
      company: p.company,
      slotId,
    }),
  });
  await sendTurn(`Please confirm the slot ${slotId.split('_')[1] || 'tomorrow'} for our demo.`);
};

// --- CRM & Business Insights ---
async function loadCRM() {
  const crm = await api('/api/crm');
  const ins = crm.insights;

  document.getElementById('kpiRow').innerHTML = [
    { label: 'Total Leads', value: ins.totalLeads },
    { label: 'Qualification Rate', value: `${ins.qualificationRate}%` },
    { label: 'Demo Conversion', value: `${ins.bookingConversionRate}%` },
    { label: 'Avg BANT Score', value: `${ins.avgBantScore}/100` },
    { label: 'Avg Sentiment', value: ins.avgSentiment },
  ]
    .map((k) => `<div class="kpi-card"><div class="label">${k.label}</div><div class="value">${k.value}</div></div>`)
    .join('');

  document.querySelector('#leadsTable tbody').innerHTML = crm.leads
    .map(
      (l) => `
      <tr>
        <td><strong>${escapeHtml(l.name)}</strong><div class="muted">${escapeHtml(l.email || l.role || '')}</div></td>
        <td>${escapeHtml(l.company)}</td>
        <td><span class="badge badge-neutral">${escapeHtml((l.language || 'en').toUpperCase())}</span></td>
        <td><span class="badge ${l.tier === 'Hot' ? 'badge-accent' : l.tier === 'Warm' ? 'badge-warn' : 'badge-neutral'}">${l.tier} (${l.bantScore})</span></td>
        <td>${escapeHtml(l.status)}</td>
        <td class="muted">${escapeHtml(l.need || l.budget || '—')}</td>
      </tr>`
    )
    .join('');

  document.getElementById('appointmentsList').innerHTML = crm.appointments.length
    ? crm.appointments
        .map(
          (a) => `
        <div class="info-card">
          <strong>${escapeHtml(a.prospectName)} (${escapeHtml(a.company)})</strong>
          <span class="badge badge-accent" style="float:right">${escapeHtml(a.dayLabel)} · ${escapeHtml(a.time)}</span>
          <div class="muted">${escapeHtml(a.email)} · ${escapeHtml(a.meetingLink)}</div>
        </div>`
        )
        .join('')
    : '<p class="muted">No appointments booked yet in this workspace.</p>';

  document.getElementById('summariesList').innerHTML = crm.callSummaries
    .map(
      (s) => `
      <div class="info-card">
        <strong>${escapeHtml(s.prospectName)} · ${escapeHtml(s.company)}</strong>
        <span class="badge ${s.tier === 'Hot' ? 'badge-accent' : 'badge-warn'}" style="float:right">${s.tier} (${s.bantScore})</span>
        <p style="margin:6px 0">${escapeHtml(s.executiveSummary)}</p>
        <div class="muted"><strong>Next Action:</strong> ${escapeHtml(s.nextBestAction)}</div>
        <pre>${escapeHtml(s.followUpEmail)}</pre>
      </div>`
    )
    .join('');

  document.getElementById('insightsDetails').innerHTML = `
    <div class="info-card">
      <strong>Top Objections:</strong> ${ins.topObjections.length ? ins.topObjections.map((o) => `${escapeHtml(o.name)} (${o.count})`).join(', ') : 'None recorded'}<br/>
      <strong>Languages:</strong> ${Object.entries(ins.languageDistribution).map(([k, v]) => `${k.toUpperCase()}: ${v}`).join(' · ')}
    </div>`;

  document.getElementById('webhookList').innerHTML = crm.webhookOutbox
    .slice(0, 6)
    .map(
      (w) => `
      <div class="info-card">
        <span class="badge badge-primary">${escapeHtml(w.eventType)}</span>
        <span class="muted">${escapeHtml(w.provider)} · ${escapeHtml(w.timestamp)}</span>
        <pre>${escapeHtml(JSON.stringify(w.payload, null, 2))}</pre>
      </div>`
    )
    .join('');
}

// --- Knowledge Base ---
async function loadKB() {
  const kb = await api('/api/kb');
  document.getElementById('kbList').innerHTML = kb.chunks
    .map(
      (c) => `
      <div class="info-card">
        <strong>${escapeHtml(c.title)}</strong>
        <span class="badge badge-primary" style="float:right">${escapeHtml(c.category)}</span>
        <p style="margin:6px 0">${escapeHtml(c.content)}</p>
        <div class="muted">Tags: ${(c.tags || []).map((t) => `#${escapeHtml(t)}`).join(' ')}</div>
      </div>`
    )
    .join('');
}

// --- Event Listeners ---
document.querySelectorAll('.tab').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
  });
});

els.btnNewCall.addEventListener('click', startNewCall);
els.btnEndCall.addEventListener('click', endCall);
els.btnMic.addEventListener('click', toggleMic);

els.textTurnForm.addEventListener('submit', (e) => {
  e.preventDefault();
  sendTurn(els.turnInput.value);
});

els.turnInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendTurn(els.turnInput.value);
  }
});

document.querySelectorAll('.scenario-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    if (!state.sessionId) await startNewCall();
    await sendTurn(SCENARIOS[btn.dataset.scenario]);
  });
});

document.getElementById('kbAddForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const title = document.getElementById('kbTitle').value.trim();
  const category = document.getElementById('kbCategory').value;
  const tags = document.getElementById('kbTags').value.split(',').map((s) => s.trim()).filter(Boolean);
  const content = document.getElementById('kbContent').value.trim();
  await api('/api/kb', { method: 'POST', body: JSON.stringify({ title, category, tags, content }) });
  e.target.reset();
  await loadKB();
});

document.getElementById('btnConfig').addEventListener('click', () => els.configModal.classList.remove('hidden'));
document.getElementById('btnCloseConfig').addEventListener('click', () => els.configModal.classList.add('hidden'));
document.getElementById('configForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const res = await api('/api/config', {
    method: 'POST',
    body: JSON.stringify({
      provider: document.getElementById('cfgProvider').value,
      geminiApiKey: document.getElementById('cfgGeminiKey').value.trim(),
      openaiApiKey: document.getElementById('cfgOpenaiKey').value.trim(),
    }),
  });
  els.providerBadge.textContent = res.provider;
  els.configModal.classList.add('hidden');
});

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Initial bootstrap + SSE live updates
(async function init() {
  const health = await api('/api/health');
  els.providerBadge.textContent = health.provider;
  await Promise.all([loadCRM(), loadKB()]);

  const sse = new EventSource('/api/events');
  sse.addEventListener('crm_updated', () => loadCRM());
  sse.addEventListener('kb_updated', () => loadKB());
  sse.addEventListener('config_updated', (e) => {
    const payload = JSON.parse(e.data);
    els.providerBadge.textContent = payload.provider;
  });
})();
