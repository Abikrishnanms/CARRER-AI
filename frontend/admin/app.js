/* ═══════════════════════════════════════════════════════
   TalentLens Admin Console — Application Logic
═══════════════════════════════════════════════════════ */

const API = 'http://localhost:8000/api/v1';
const REFRESH_MS = 30_000;

const state = {
  token: localStorage.getItem('admin_token'),
  refreshTimer: null,
  jobsPage: 1,
  usersPage: 1,
  scamThreshold: 0.4,
};

// ─── Bootstrap ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupSourceTagToggles();
  if (state.token) {
    hideLoginOverlay();
    initDashboard();
  }
  checkApiStatus();
});

function hideLoginOverlay() {
  document.getElementById('login-overlay').style.display = 'none';
}

async function initDashboard() {
  await Promise.allSettled([loadOverview(), checkApiStatus()]);
  state.refreshTimer = setInterval(() => {
    if (document.querySelector('.page.active')?.id === 'page-overview') loadOverview();
  }, REFRESH_MS);
}

// ─── Login ────────────────────────────────────────────────
async function doLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const err = document.getElementById('login-error');
  err.classList.add('hidden');
  btn.textContent = 'Signing in…'; btn.disabled = true;

  try {
    const data = await post('/auth/login', {
      email: document.getElementById('adm-email').value,
      password: document.getElementById('adm-pass').value,
    }, false);

    // Verify admin role
    const me = await get('/auth/me', data.access_token);
    if (me.role !== 'admin') {
      err.textContent = 'Access denied. Admin role required.';
      err.classList.remove('hidden');
      return;
    }

    localStorage.setItem('admin_token', data.access_token);
    state.token = data.access_token;
    document.getElementById('admin-avatar').textContent = (me.full_name || me.email || 'A')[0].toUpperCase();
    hideLoginOverlay();
    initDashboard();
  } catch (ex) {
    err.textContent = ex.message || 'Invalid credentials';
    err.classList.remove('hidden');
  } finally {
    btn.textContent = 'Sign In'; btn.disabled = false;
  }
}

// ─── API Status ───────────────────────────────────────────
async function checkApiStatus() {
  const dot = document.getElementById('status-dot');
  const val = document.getElementById('status-value');
  try {
    const t0 = performance.now();
    await fetch(`${API.replace('/api/v1', '')}/health`);
    const ms = Math.round(performance.now() - t0);
    dot.classList.remove('error');
    val.textContent = `Online · ${ms}ms`;
  } catch {
    dot.classList.add('error');
    val.textContent = 'Unreachable';
  }
}

// ─── Page Navigation ──────────────────────────────────────
function showPage(name, clickedLink) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));

  const page = document.getElementById(`page-${name}`);
  if (page) { page.classList.add('active'); page.style.display = 'block'; }
  if (clickedLink) clickedLink.classList.add('active');

  const titles = { overview:'Dashboard', pipeline:'Pipeline Monitor', jobs:'Job Management', scam:'Scam Reports', users:'User Management', companies:'Companies', settings:'Settings' };
  document.getElementById('page-title').textContent = titles[name] || name;
  document.getElementById('breadcrumb').textContent = `Admin / ${titles[name] || name}`;

  if (name === 'overview') loadOverview();
  else if (name === 'pipeline') loadPipelineLog(24);
  else if (name === 'jobs') loadJobsTable();
  else if (name === 'scam') loadScamReports();
  else if (name === 'users') loadUsersTable();
  else if (name === 'companies') loadCompaniesTable();
  return false;
}

// ─── Overview Dashboard ────────────────────────────────────
async function loadOverview() {
  try {
    const [stats, analytics] = await Promise.all([
      get('/admin/stats'),
      get('/analytics/overview').catch(() => ({})),
    ]);
    renderKPIs(stats, analytics);
    renderPipelineFlow(stats.jobs || {});
    renderSpeedChart(stats.pipeline?.avg_processing_time_ms || {});
    renderActivityFeed(stats);
    renderSourceChart(stats);
  } catch (e) {
    console.error('Overview load failed:', e);
  }
}

function renderKPIs(stats, analytics) {
  const jobs = stats.jobs || {};
  const users = stats.users || {};
  const trust = stats.trust || {};
  const pipeline = stats.pipeline || {};

  const kpis = [
    { label: 'Published Jobs',   value: fmt(jobs.published||0),       delta: `+${analytics.new_today||0} today`,   deltaType: 'up',   icon: '💼', accent: 'linear-gradient(90deg,#7C3AED,#2563EB)' },
    { label: 'Total Users',      value: fmt(users.total||0),          delta: `${users.active||0} active`,          deltaType: 'neutral', icon: '👥', accent: 'linear-gradient(90deg,#10B981,#059669)' },
    { label: 'Scam Rejected',    value: fmt(trust.scam_rejected||0),  delta: `${trust.high_risk_flagged||0} flagged`, deltaType: 'down', icon: '🛡️', accent: 'linear-gradient(90deg,#EF4444,#DC2626)' },
    { label: 'Pipeline Events',  value: fmt(pipeline.events_24h||0),  delta: `${pipeline.failed_24h||0} failed`,   deltaType: pipeline.failed_24h > 0 ? 'down' : 'up', icon: '⚙️', accent: 'linear-gradient(90deg,#F59E0B,#D97706)' },
    { label: 'Avg Quality Score',value: `${jobs.avg_quality_score||0}`, delta: '/ 100',                            deltaType: 'neutral', icon: '⭐', accent: 'linear-gradient(90deg,#22D3EE,#0891B2)' },
    { label: 'Admin Users',      value: users.admins||0,              delta: `${users.total - users.active||0} inactive`, deltaType: 'neutral', icon: '👑', accent: 'linear-gradient(90deg,#8B5CF6,#6D28D9)' },
  ];

  document.getElementById('kpi-grid').innerHTML = kpis.map(k => `
  <div class="kpi-card" style="--kpi-accent:${k.accent}">
    <div class="kpi-label">${k.label}</div>
    <div class="kpi-value">${k.value}</div>
    <div class="kpi-delta ${k.deltaType}">${k.deltaType==='up'?'↑':k.deltaType==='down'?'↓':''} ${k.delta}</div>
    <div class="kpi-icon">${k.icon}</div>
  </div>`).join('');
}

function renderPipelineFlow(jobs) {
  const stages = [
    { name: 'Collected', icon: '📥', key: 'raw' },
    { name: 'Cleaned',   icon: '🧹', key: 'cleaned' },
    { name: 'Deduped',   icon: '🔍', key: 'deduplicated' },
    { name: 'Enriched',  icon: '🧠', key: 'enriched' },
    { name: 'Verified',  icon: '✅', key: 'verified' },
    { name: 'Live',      icon: '🚀', key: 'published' },
  ];
  const html = stages.map((s, i) => `
    <div class="pipeline-stage">
      <div class="stage-bubble ${jobs[s.key] > 0 ? 'active' : ''}" data-count="${fmt(jobs[s.key]||0)}">${s.icon}</div>
      <div class="stage-label">${s.name}</div>
    </div>
    ${i < stages.length - 1 ? '<div class="stage-arrow">→</div>' : ''}`
  ).join('');
  document.getElementById('pipeline-flow').innerHTML = html;
  document.getElementById('pipeline-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function renderSpeedChart(durations) {
  const max = Math.max(...Object.values(durations).filter(Number.isFinite), 1);
  const html = Object.entries(durations).sort((a,b)=>b[1]-a[1]).map(([agent, ms]) => `
  <div class="speed-bar-row">
    <div class="speed-bar-name">${esc(agent)}</div>
    <div class="speed-bar-track"><div class="speed-bar-fill" style="width:${(ms/max)*100}%"></div></div>
    <div class="speed-bar-val">${ms.toFixed(0)}ms</div>
  </div>`).join('') || '<p style="color:var(--text-muted);font-size:0.85rem">No data yet</p>';
  document.getElementById('speed-chart').innerHTML = html;
}

function renderActivityFeed(stats) {
  const jobs = stats.jobs || {};
  const trust = stats.trust || {};
  const now = new Date().toLocaleTimeString();
  const items = [
    { type:'success', icon:'✅', msg:`${fmt(jobs.published||0)} jobs currently live`, time: now },
    { type:'info',    icon:'📥', msg:`Pipeline processed ${fmt(stats.pipeline?.events_24h||0)} events (24h)`, time: now },
    { type: trust.scam_rejected > 0 ? 'error' : 'success', icon:'🛡️', msg:`${fmt(trust.scam_rejected||0)} scam jobs rejected`, time: now },
    { type:'info',    icon:'👥', msg:`${fmt(stats.users?.active||0)} active users on platform`, time: now },
    { type: stats.pipeline?.failed_24h > 0 ? 'error' : 'success', icon:'⚙️', msg:`${fmt(stats.pipeline?.failed_24h||0)} pipeline failures (24h)`, time: now },
  ];
  document.getElementById('activity-feed').innerHTML = items.map(a => `
  <div class="activity-item">
    <div class="activity-icon ${a.type}">${a.icon}</div>
    <div class="activity-text">
      <div class="activity-msg">${a.msg}</div>
      <div class="activity-time">${a.time}</div>
    </div>
  </div>`).join('');
}

function renderSourceChart(stats) {
  // Placeholder — real data would come from analytics/trends
  const sources = [
    { name: 'Adzuna', count: Math.floor(Math.random() * 800 + 200), color: '#7C3AED' },
    { name: 'Greenhouse', count: Math.floor(Math.random() * 500 + 100), color: '#2563EB' },
    { name: 'Indeed', count: Math.floor(Math.random() * 400 + 80), color: '#22D3EE' },
    { name: 'RSS', count: Math.floor(Math.random() * 200 + 50), color: '#10B981' },
  ];
  const max = Math.max(...sources.map(s => s.count), 1);
  document.getElementById('source-chart').innerHTML = sources.map(s => `
  <div class="source-bar-row">
    <div class="source-name">${s.name}</div>
    <div class="source-bar-outer"><div class="source-bar-inner" style="width:${(s.count/max)*100}%;background:${s.color}"></div></div>
    <div class="source-count">${fmt(s.count)}</div>
  </div>`).join('');
}

// ─── Pipeline Log ──────────────────────────────────────────
async function loadPipelineLog(hours = 24) {
  const container = document.getElementById('pipeline-log');
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await get(`/admin/pipeline?since_hours=${hours}&limit=60`);
    const events = data.events || [];
    if (!events.length) { container.innerHTML = '<p style="color:var(--text-muted);padding:20px">No events found in this time window</p>'; return; }
    container.innerHTML = events.map(e => {
      const t = e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—';
      const dur = e.duration_ms ? `${e.duration_ms.toFixed(0)}ms` : '—';
      return `
      <div class="log-entry">
        <div class="log-status ${e.status === 'success' ? 'success' : e.status === 'failed' ? 'failed' : 'pending'}"></div>
        <div class="log-agent">${esc(e.agent || '?')}</div>
        <div class="log-msg">${esc(e.event_type || '')} <span style="color:var(--text-muted);font-size:0.75rem">${e.job_id ? '· ' + e.job_id.slice(0,8) + '…' : ''}</span></div>
        <div class="log-time">${t}</div>
        <div class="log-dur">${dur}</div>
      </div>`;
    }).join('');
  } catch { container.innerHTML = '<p style="color:var(--text-muted);padding:20px">Failed to load pipeline log</p>'; }
}

// ─── Jobs Table ────────────────────────────────────────────
async function loadJobsTable() {
  const tbody = document.getElementById('jobs-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="7" class="loading-row"><div class="loading-spinner"></div></td></tr>';
  const status = document.getElementById('job-status-filter')?.value || 'published';
  const params = new URLSearchParams({ page: state.jobsPage, page_size: 20 });
  if (status) params.set('status', status);
  try {
    const data = await get(`/jobs?${params}`);
    const rows = (data.results || []).map(j => {
      const riskColor = j.scam_risk === 'very_high' || j.scam_risk === 'high' ? '#F87171' : j.scam_risk === 'medium' ? '#FBBF24' : '#34D399';
      const riskPct = Math.round((j.scam_probability || 0) * 100);
      return `<tr>
        <td class="cell-truncate" title="${esc(j.title)}">${esc(j.title || '—')}</td>
        <td class="cell-truncate">${esc(j.company_name || '—')}</td>
        <td><span style="font-family:JetBrains Mono,monospace;font-size:0.78rem">${esc(j.source || '—')}</span></td>
        <td><span class="status-chip chip-${j.status}">${j.status}</span></td>
        <td><span class="quality-score">${j.quality_score ? j.quality_score.toFixed(0) : '—'}</span></td>
        <td><div class="risk-bar"><div class="risk-fill" style="width:${riskPct}px;max-width:60px;background:${riskColor}"></div><span class="risk-pct" style="color:${riskColor}">${riskPct}%</span></div></td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-sm btn-ghost" onclick="openJobUrl('${esc(j.apply_url||'')}')">View</button>
            <button class="btn btn-sm btn-danger" onclick="rejectJob('${esc(j.id)}')">Reject</button>
          </div>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">No jobs found</td></tr>';
    tbody.innerHTML = rows;
    renderTablePagination('jobs-pagination', data.total_pages || 1, state.jobsPage, p => { state.jobsPage = p; loadJobsTable(); });
  } catch { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">Failed to load jobs</td></tr>'; }
}

function filterJobsTable(query) {
  document.querySelectorAll('#jobs-tbody tr').forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(query.toLowerCase()) ? '' : 'none';
  });
}

async function rejectJob(id) {
  if (!confirm('Reject this job?')) return;
  try {
    await patch(`/admin/jobs/${id}/status`, { status: 'rejected', reason: 'Admin override' });
    showToast('Job rejected', 'success');
    loadJobsTable();
  } catch { showToast('Failed to reject job', 'error'); }
}

function openJobUrl(url) { if (url) window.open(url, '_blank'); else showToast('No apply URL for this job', 'info'); }

// ─── Scam Reports ──────────────────────────────────────────
async function loadScamReports() {
  const tbody = document.getElementById('scam-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="7" class="loading-row"><div class="loading-spinner"></div></td></tr>';
  try {
    const data = await get(`/admin/jobs/scam-reports?min_probability=${state.scamThreshold}&page_size=30`);
    const badge = document.getElementById('scam-badge');
    if (badge) badge.textContent = data.total || 0;

    const rows = (data.scam_flagged || []).map(j => {
      const pct = Math.round((j.scam_probability || 0) * 100);
      const color = pct >= 70 ? '#F87171' : pct >= 50 ? '#FBBF24' : '#22D3EE';
      const rules = (j.triggered_rules || []).join(', ') || '—';
      return `<tr>
        <td class="cell-truncate" title="${esc(j.title)}">${esc(j.title || '—')}</td>
        <td class="cell-truncate">${esc(j.company_name || '—')}</td>
        <td style="font-size:0.78rem;font-family:JetBrains Mono,monospace">${esc(j.source || '—')}</td>
        <td><span style="font-weight:700;color:${color};font-family:JetBrains Mono,monospace">${pct}%</span></td>
        <td style="font-size:0.78rem;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(rules)}">${esc(rules)}</td>
        <td><span class="status-chip chip-${j.status}">${j.status}</span></td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-sm btn-danger" onclick="rejectJob('${esc(j.id)}')">Reject</button>
            <button class="btn btn-sm btn-ghost" onclick="publishJob('${esc(j.id)}')">Restore</button>
          </div>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">No scam reports found</td></tr>';
    tbody.innerHTML = rows;
  } catch { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">Failed to load scam reports</td></tr>'; }
}

function onScamThreshold(val) {
  state.scamThreshold = parseFloat(val);
  document.getElementById('scam-threshold-val').textContent = val;
  clearTimeout(state.scamTimer);
  state.scamTimer = setTimeout(loadScamReports, 600);
}

async function publishJob(id) {
  try {
    await patch(`/admin/jobs/${id}/status`, { status: 'published', reason: 'Admin reviewed - legitimate' });
    showToast('Job restored to published', 'success');
    loadScamReports();
  } catch { showToast('Failed to restore job', 'error'); }
}

// ─── Users Table ───────────────────────────────────────────
async function loadUsersTable(search = '') {
  const tbody = document.getElementById('users-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" class="loading-row"><div class="loading-spinner"></div></td></tr>';
  const params = new URLSearchParams({ page: state.usersPage, page_size: 20 });
  if (search) params.set('search', search);
  try {
    const data = await get(`/admin/users?${params}`);
    const rows = (data.users || []).map(u => `<tr>
      <td>${esc(u.full_name || '—')}</td>
      <td style="color:var(--text-secondary)">${esc(u.email)}</td>
      <td><span class="status-chip chip-${u.role}">${u.role}</span></td>
      <td><span style="color:${u.is_active ? 'var(--emerald-400)' : 'var(--rose-400)'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
      <td style="color:var(--text-muted);font-size:0.8rem">${formatDate(u.created_at)}</td>
      <td>
        <div style="display:flex;gap:6px">
          ${u.role !== 'admin' ? `<button class="btn btn-sm btn-ghost" onclick="promoteUser('${u.id}')">Promote</button>` : ''}
          ${u.is_active ? `<button class="btn btn-sm btn-danger" onclick="deactivateUser('${u.id}')">Deactivate</button>` : ''}
        </div>
      </td>
    </tr>`).join('') || '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">No users found</td></tr>';
    tbody.innerHTML = rows;
    renderTablePagination('users-pagination', data.total_pages || 1, state.usersPage, p => { state.usersPage = p; loadUsersTable(search); });
  } catch { tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">Failed to load users</td></tr>'; }
}

let userSearchTimer;
function searchUsers(q) {
  clearTimeout(userSearchTimer);
  userSearchTimer = setTimeout(() => { state.usersPage = 1; loadUsersTable(q); }, 400);
}

async function promoteUser(id) {
  if (!confirm('Promote this user to admin?')) return;
  try {
    await patch(`/admin/users/${id}/role`, { role: 'admin' });
    showToast('User promoted to admin', 'success');
    loadUsersTable();
  } catch { showToast('Failed to promote user', 'error'); }
}

async function deactivateUser(id) {
  if (!confirm('Deactivate this user?')) return;
  try {
    await del(`/admin/users/${id}`);
    showToast('User deactivated', 'success');
    loadUsersTable();
  } catch { showToast('Failed to deactivate user', 'error'); }
}

// ─── Companies Table ───────────────────────────────────────
async function loadCompaniesTable() {
  const tbody = document.getElementById('companies-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" class="loading-row"><div class="loading-spinner"></div></td></tr>';
  try {
    const data = await get('/analytics/top-companies?limit=40');
    const rows = (data.top_companies || []).map(c => {
      const trustColor = c.trust_score >= 70 ? '#34D399' : c.trust_score >= 40 ? '#FBBF24' : '#F87171';
      return `<tr>
        <td><b>${esc(c.company_name || '—')}</b></td>
        <td><span style="color:${trustColor};font-weight:700;font-family:JetBrains Mono,monospace">${c.trust_score ? c.trust_score.toFixed(0) : '—'}%</span></td>
        <td>${c.job_count || 0}</td>
        <td>${c.scam_reports || 0}</td>
        <td>${c.is_verified ? '<span style="color:var(--emerald-400)">✅ Verified</span>' : '<span style="color:var(--text-muted)">—</span>'}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No data</td></tr>';
    tbody.innerHTML = rows;
  } catch { tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">Failed to load companies</td></tr>'; }
}

// ─── Collection Trigger ────────────────────────────────────
async function triggerCollection() {
  const activeSources = [...document.querySelectorAll('.tag-toggle.active')].map(t => t.dataset.source);
  if (!activeSources.length) { showToast('Select at least one source', 'error'); return; }

  const btn = document.getElementById('collect-btn');
  btn.disabled = true; btn.innerHTML = '<span class="btn-icon">⏳</span> Triggering…';

  try {
    const data = await post('/admin/collect', {
      sources: activeSources,
      search_terms: ['software engineer', 'data scientist', 'python developer', 'machine learning', 'full stack'],
      limit: 500,
    });
    document.getElementById('collect-result').textContent = `Collection task ${data.task?.task_id?.slice(0,8)}… started for: ${activeSources.join(', ')}`;
    document.getElementById('collect-modal').classList.remove('hidden');
    showToast(`Collection started on ${activeSources.length} sources`, 'success');
  } catch (e) {
    showToast(`Failed to trigger: ${e.message}`, 'error');
  } finally {
    btn.disabled = false; btn.innerHTML = '<span class="btn-icon">⚡</span> Collect Now';
  }
}

function setupSourceTagToggles() {
  document.querySelectorAll('.tag-toggle').forEach(tag => {
    tag.addEventListener('click', () => tag.classList.toggle('active'));
  });
}

// ─── Pagination Helper ─────────────────────────────────────
function renderTablePagination(containerId, totalPages, currentPage, onPageChange) {
  const container = document.getElementById(containerId);
  if (!container || totalPages <= 1) { if (container) container.innerHTML = ''; return; }
  let html = '';
  if (currentPage > 1) html += `<button class="btn btn-sm btn-ghost" onclick="(${onPageChange})(${currentPage-1})">‹</button>`;
  for (let p = Math.max(1, currentPage-2); p <= Math.min(totalPages, currentPage+2); p++) {
    html += `<button class="btn btn-sm ${p === currentPage ? 'btn-primary' : 'btn-ghost'}" onclick="(${onPageChange})(${p})">${p}</button>`;
  }
  if (currentPage < totalPages) html += `<button class="btn btn-sm btn-ghost" onclick="(${onPageChange})(${currentPage+1})">›</button>`;
  container.innerHTML = html;
}

// ─── API Helpers ───────────────────────────────────────────
async function get(path, token) {
  const res = await fetch(API + path, { headers: authHeaders(token) });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function post(path, body, auth = true) {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(auth ? authHeaders() : {}) },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function patch(path, body) {
  const res = await fetch(API + path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function del(path) {
  const res = await fetch(API + path, { method: 'DELETE', headers: authHeaders() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json().catch(() => ({}));
}
function authHeaders(token) {
  const t = token || state.token;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// ─── UI Helpers ────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  t.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(12px)'; setTimeout(()=>t.remove(),300); }, 3500);
}

function fmt(n) {
  if (typeof n !== 'number') n = parseInt(n) || 0;
  return n >= 1_000_000 ? (n/1_000_000).toFixed(1)+'M' : n >= 1000 ? (n/1000).toFixed(1)+'K' : String(n);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' });
  } catch { return dateStr; }
}

function esc(s) {
  if (typeof s !== 'string') s = String(s || '');
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
