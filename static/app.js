let currentDecisions = [];
let decisionFilter = 'all';
let autoRefreshMs = 10000;
let refreshCountdownSec = 10;
let timerInterval = null;
let pollTimeout = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  fetchAllData();
  setupAutoRefresh();
});

function setupAutoRefresh() {
  if (timerInterval) clearInterval(timerInterval);
  if (pollTimeout) clearTimeout(pollTimeout);

  if (autoRefreshMs <= 0) {
    document.getElementById('refreshTimer').textContent = 'Paused';
    return;
  }

  refreshCountdownSec = Math.floor(autoRefreshMs / 1000);
  document.getElementById('refreshTimer').textContent = `${refreshCountdownSec}s`;

  timerInterval = setInterval(() => {
    refreshCountdownSec--;
    if (refreshCountdownSec <= 0) {
      refreshCountdownSec = Math.floor(autoRefreshMs / 1000);
      fetchAllData();
    }
    document.getElementById('refreshTimer').textContent = `${refreshCountdownSec}s`;
  }, 1000);
}

function changeAutoRefresh(val) {
  autoRefreshMs = parseInt(val, 10);
  setupAutoRefresh();
  showToast(`Auto-refresh interval set to ${autoRefreshMs > 0 ? autoRefreshMs/1000 + 's' : 'Paused'}.`);
}

async function fetchAllData() {
  await Promise.all([fetchStatus(), fetchFeed(), fetchDecisions(), fetchRuns()]);
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/agent/status');
    if (!res.ok) return;
    const data = await res.json();
    
    // Header & Pulse
    document.getElementById('personaName').textContent = data.persona_name || "Autonomous Agent";
    if (data.persona_name) {
      document.getElementById('avatarLetter').textContent = data.persona_name.charAt(0).toUpperCase();
    }
    
    // KPIs
    document.getElementById('kpiPublished').textContent = data.total_posts_published;
    document.getElementById('kpiPublishedSub').textContent = `Velocity: ${data.daily_posts_today} published today`;
    document.getElementById('kpiDecisions').textContent = data.total_decisions_made;
    document.getElementById('kpiIngested').textContent = data.total_news_items_ingested;
    document.getElementById('kpiCap').textContent = `${data.daily_posts_today} / ${data.daily_post_cap}`;
    
    const capPct = Math.min(100, Math.round((data.daily_posts_today / (data.daily_post_cap || 10)) * 100));
    document.getElementById('capFill').style.width = `${capPct}%`;
    
    // Sidebar Meta
    document.getElementById('intervalMinutes').textContent = `${data.posting_interval_minutes} min`;
    document.getElementById('lastRunStatus').textContent = data.last_cycle_status || "idle";
    
    const pulse = document.getElementById('pulseIndicator');
    const schedText = document.getElementById('schedulerStatus');
    const countdownEl = document.getElementById('nextRunCountdown');
    
    if (data.scheduler_running) {
      pulse.style.background = 'var(--accent-emerald)';
      const nextDate = data.next_scheduled_run ? new Date(data.next_scheduled_run) : null;
      schedText.textContent = 'Scheduler: Armed & Running';
      countdownEl.textContent = nextDate ? nextDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'Active';
    } else {
      pulse.style.background = 'var(--accent-amber)';
      schedText.textContent = 'Scheduler: Idle';
      countdownEl.textContent = 'Waiting for Init';
    }
  } catch (e) {
    console.error("Status fetch error", e);
  }
}

async function fetchFeed() {
  try {
    const res = await fetch('/api/agent/feed?limit=30&status=published');
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('feedCount').textContent = data.total;
    const feedContainer = document.getElementById('viewFeed');
    
    if (data.posts.length === 0) {
      feedContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📡</div>
          <p>No posts published yet. Click <strong>"Run Cycle Now"</strong> to trigger discovery and synthesis!</p>
        </div>
      `;
      return;
    }
    
    feedContainer.innerHTML = data.posts.map((p, idx) => {
      const pubDate = new Date(p.published_at).toLocaleString();
      const sourcesHtml = (p.sources || []).map(s => {
        let domain = 'Source';
        try { domain = new URL(s).hostname.replace('www.', ''); } catch (e) {}
        return `
          <a href="${s}" target="_blank" rel="noopener noreferrer" class="source-link">
            🔗 ${domain}
          </a>
        `;
      }).join('');
      
      const drawerId = `rationaleDrawer_${idx}`;
      
      return `
        <article class="post-card">
          <div class="post-meta">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 700; color: #f8fafc;">Published Take</span>
              <span style="font-size: 0.75rem; color: var(--accent-emerald); background: rgba(16,185,129,0.12); padding: 0.1rem 0.4rem; border-radius: 4px;">Live</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.6rem;">
              <span>${pubDate}</span>
              <button class="btn-copy" onclick="copyPostText('${escapeHtml(p.content)}')">📋 Copy</button>
            </div>
          </div>
          
          <div class="post-content">${escapeHtml(p.content)}</div>
          <div class="post-sources">${sourcesHtml}</div>
          
          <button class="rationale-toggle" onclick="toggleDrawer('${drawerId}')">
            <span>💡</span> Reason for Publishing ▾
          </button>
          
          <div id="${drawerId}" class="post-rationale-box" style="display: none;">
            <strong>Editorial Rationale:</strong> ${escapeHtml(p.rationale)}
          </div>
        </article>
      `;
    }).join('');
  } catch (e) {
    console.error("Feed fetch error", e);
  }
}

async function fetchDecisions() {
  try {
    const res = await fetch('/api/agent/decisions?limit=40');
    if (!res.ok) return;
    currentDecisions = await res.json();
    
    const rejectedOnly = currentDecisions.filter(d => !d.should_publish);
    document.getElementById('rejectedCount').textContent = rejectedOnly.length;
    document.getElementById('totalDecisionsTab').textContent = currentDecisions.length;
    
    renderDecisions();
    renderRejectedOnly();
  } catch (e) {
    console.error("Decisions fetch error", e);
  }
}

function renderDecisions() {
  const container = document.getElementById('decisionsStream');
  const filtered = currentDecisions.filter(d => {
    if (decisionFilter === 'approved') return d.should_publish;
    if (decisionFilter === 'rejected') return !d.should_publish;
    return true;
  });
  
  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>No decision logs recorded for this filter.</p></div>`;
    return;
  }
  
  container.innerHTML = filtered.map(d => formatDecisionCard(d)).join('');
}

function renderRejectedOnly() {
  const container = document.getElementById('rejectedStream');
  const rejected = currentDecisions.filter(d => !d.should_publish);
  
  if (rejected.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🛡️</div>
        <p>No stories rejected yet. All scored items met quality and topic criteria.</p>
      </div>
    `;
    return;
  }
  
  container.innerHTML = rejected.map(d => formatDecisionCard(d)).join('');
}

function formatDecisionCard(d) {
  const isApp = d.should_publish;
  const badgeClass = isApp ? 'approved' : 'rejected';
  const badgeText = isApp ? 'Approved for Synthesis' : 'Rejected';
  
  const relPct = Math.round(d.relevance_score * 100);
  const novPct = Math.round(d.novelty_score * 100);
  const recPct = Math.round(d.recency_score * 100);
  const compPct = Math.round(d.composite_score * 100);
  
  const reasonsHtml = (d.rationale || []).map(r => `<li>${escapeHtml(r)}</li>`).join('');
  
  let domain = 'Source Link';
  try { if (d.source_url) domain = new URL(d.source_url).hostname.replace('www.', ''); } catch (e) {}
  
  return `
    <div class="decision-card ${badgeClass}">
      <div class="decision-top">
        <div>
          <div class="decision-title">${escapeHtml(d.title || "Discovered Story")}</div>
          <a href="${d.source_url}" target="_blank" style="font-size: 0.775rem; color: var(--accent-cyan); text-decoration: none;">
            🔗 ${domain}
          </a>
        </div>
        <span class="badge-status ${badgeClass}">${badgeText}</span>
      </div>
      
      <div class="score-bars">
        <div class="score-item">
          Relevance: <strong>${relPct}%</strong>
          <div class="score-progress"><div class="score-fill ${relPct < 50 ? 'low' : ''}" style="width: ${relPct}%"></div></div>
        </div>
        <div class="score-item">
          Novelty: <strong>${novPct}%</strong>
          <div class="score-progress"><div class="score-fill ${novPct < 50 ? 'low' : ''}" style="width: ${novPct}%"></div></div>
        </div>
        <div class="score-item">
          Recency: <strong>${recPct}%</strong>
          <div class="score-progress"><div class="score-fill" style="width: ${recPct}%"></div></div>
        </div>
        <div class="score-item">
          Composite: <strong>${compPct}%</strong>
          <div class="score-progress"><div class="score-fill ${compPct < 60 ? 'low' : ''}" style="width: ${compPct}%"></div></div>
        </div>
      </div>
      
      <ul class="rationale-list">
        ${reasonsHtml}
      </ul>
    </div>
  `;
}

function filterDecisions(type) {
  decisionFilter = type;
  document.getElementById('filterAll').classList.toggle('active', type === 'all');
  document.getElementById('filterApproved').classList.toggle('active', type === 'approved');
  document.getElementById('filterRejected').classList.toggle('active', type === 'rejected');
  renderDecisions();
}

async function triggerCycle() {
  const btn = document.getElementById('btnManualTrigger');
  const icon = document.getElementById('triggerIcon');
  const text = document.getElementById('triggerText');
  
  btn.disabled = true;
  icon.textContent = '⏳';
  text.textContent = 'Executing Cycle...';
  
  try {
    const res = await fetch('/api/agent/trigger', { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Autonomous cycle executed!');
    await fetchAllData();
  } catch (e) {
    console.error("Trigger error", e);
    showToast('Failed to execute cycle. Check console.');
  } finally {
    btn.disabled = false;
    icon.textContent = '⚡';
    text.textContent = 'Run Cycle Now';
  }
}

function switchTab(tab) {
  document.getElementById('viewFeed').style.display = tab === 'feed' ? 'flex' : 'none';
  document.getElementById('viewRejected').style.display = tab === 'rejected' ? 'block' : 'none';
  document.getElementById('viewDecisions').style.display = tab === 'decisions' ? 'block' : 'none';
  document.getElementById('viewRuns').style.display = tab === 'runs' ? 'block' : 'none';
  
  document.getElementById('tabFeed').classList.toggle('active', tab === 'feed');
  document.getElementById('tabRejected').classList.toggle('active', tab === 'rejected');
  document.getElementById('tabDecisions').classList.toggle('active', tab === 'decisions');
  document.getElementById('tabRuns').classList.toggle('active', tab === 'runs');
  
  if (tab === 'runs') fetchRuns();
}

async function fetchRuns() {
  try {
    const res = await fetch('/api/agent/runs?limit=15');
    if (!res.ok) return;
    const runs = await res.json();
    const container = document.getElementById('runsStream');
    
    if (runs.length === 0) {
      container.innerHTML = '<div class="empty-state"><p>No cycle run telemetry recorded yet.</p></div>';
      return;
    }
    
    container.innerHTML = runs.map(r => `
      <div class="card" style="margin-bottom: 0.85rem; font-size: 0.85rem;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.4rem;">
          <strong style="color: #fff;">Cycle Run: ${r.id.substring(0, 8)}...</strong>
          <span style="color: ${r.status === 'success' ? 'var(--accent-emerald)' : 'var(--accent-amber)'}; font-weight: 700; text-transform: uppercase;">
            ${r.status}
          </span>
        </div>
        <div style="color: var(--text-muted); line-height: 1.6;">
          Started: <strong>${new Date(r.run_started_at).toLocaleTimeString()}</strong> | 
          Items Fetched: <strong>${r.items_fetched}</strong> | 
          Decisions: <strong>${r.decisions_made}</strong> | 
          Posts Published: <strong>${r.posts_published}</strong>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error("Fetch runs error", e);
  }
}

function toggleDrawer(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }
}

function openPersonaModal() {
  document.getElementById('personaModal').style.display = 'flex';
}

function closePersonaModal() {
  document.getElementById('personaModal').style.display = 'none';
}

function closeModalOnBackdrop(e) {
  if (e.target.id === 'personaModal') {
    closePersonaModal();
  }
}

async function handlePersonaSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btnSavePersona');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Saving...';
  
  const payload = {
    persona_name: document.getElementById('inputName').value.trim(),
    persona_bio: document.getElementById('inputBio').value.trim(),
    posting_interval_minutes: parseInt(document.getElementById('inputInterval').value, 10) || 15,
    daily_post_cap: parseInt(document.getElementById('inputCap').value, 10) || 10,
    topics_of_interest: document.getElementById('inputTopics').value.split(',').map(s => s.trim()).filter(Boolean),
    tone_traits: document.getElementById('inputTone').value.split(',').map(s => s.trim()).filter(Boolean),
    banned_topics: document.getElementById('inputBanned').value.split(',').map(s => s.trim()).filter(Boolean),
    force_restart: true
  };
  
  try {
    const res = await fetch('/api/agent/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      closePersonaModal();
      showToast('Persona successfully updated and agent scheduler re-armed!');
      await fetchAllData();
    } else {
      const err = await res.json();
      alert('Error updating persona: ' + (err.detail || 'Unknown error'));
    }
  } catch (err) {
    console.error(err);
    alert('Failed to connect to backend.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>💾</span> Save & Re-Arm Agent';
  }
}

function copyPostText(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Post copied to clipboard!');
  }).catch(() => {
    showToast('Failed to copy text.');
  });
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.display = 'none';
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
