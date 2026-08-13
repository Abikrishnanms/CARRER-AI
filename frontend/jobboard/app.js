/* ═══════════════════════════════════════════════════════
   TalentLens Job Board — SPA Application Logic
═══════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api/v1';

// ─── App State ────────────────────────────────────────────
const state = {
  token: localStorage.getItem('token'),
  user: null,
  currentPage: 1,
  pageSize: 15,
  totalJobs: 0,
  filters: { remote_type: '', experience: '', job_type: '', scam_risk: 'medium', days: '' },
  searchQuery: '',
  searchLocation: '',
  sortBy: 'posted_at',
  salaryMin: null,
  currentSection: 'hero',
  notifCount: 0,
  autocompleteTimer: null,
};

// ─── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initScrollEffect();
  loadPlatformStats();
  setupAutocomplete();
  if (state.token) restoreSession();
});

function initScrollEffect() {
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  });
}

// ─── Session & Auth ────────────────────────────────────────
async function restoreSession() {
  try {
    const res = await apiGet('/auth/me');
    state.user = res;
    updateUserUI();
    loadNotifCount();
  } catch {
    logout(true);
  }
}

function updateUserUI() {
  const { user } = state;
  if (!user) return;
  document.getElementById('btn-login').classList.add('hidden');
  document.getElementById('btn-register').classList.add('hidden');
  document.getElementById('user-menu').classList.remove('hidden');
  const initials = (user.full_name || user.email || 'U')[0].toUpperCase();
  document.getElementById('user-avatar').textContent = initials;
  document.getElementById('dropdown-email').textContent = user.email;
}

function toggleUserDropdown() {
  document.getElementById('user-dropdown').classList.toggle('hidden');
}
document.addEventListener('click', e => {
  if (!e.target.closest('#user-menu')) {
    document.getElementById('user-dropdown')?.classList.add('hidden');
  }
  if (!e.target.closest('#hero-search') && !e.target.closest('#autocomplete')) {
    document.getElementById('autocomplete')?.classList.add('hidden');
  }
});

function logout(silent = false) {
  localStorage.removeItem('token');
  state.token = null;
  state.user = null;
  document.getElementById('btn-login').classList.remove('hidden');
  document.getElementById('btn-register').classList.remove('hidden');
  document.getElementById('user-menu').classList.add('hidden');
  if (!silent) { showToast('Signed out successfully', 'info'); showSection('hero'); }
}

// ─── Stats ─────────────────────────────────────────────────
async function loadPlatformStats() {
  try {
    const data = await apiGet('/analytics/overview');
    animateCounter('stat-jobs', data.total_jobs || 0);
    animateCounter('stat-companies', data.total_companies || 0);
    animateCounter('stat-verified', data.verified_jobs || 0);
    animateCounter('stat-remote', data.remote_jobs || 0);
  } catch {
    ['stat-jobs','stat-companies','stat-verified','stat-remote'].forEach(id => {
      document.getElementById(id).textContent = '—';
    });
  }
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const duration = 1500;
  const start = performance.now();
  const format = n => n >= 1000 ? (n / 1000).toFixed(1) + 'K' : n.toString();
  const step = now => {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = format(Math.floor(eased * target));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ─── Section Nav ───────────────────────────────────────────
function showSection(name) {
  document.getElementById('hero')?.classList.add('hidden');
  ['jobs','analytics','saved','notifications'].forEach(s => {
    document.getElementById(`section-${s}`)?.classList.add('hidden');
  });
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

  if (name === 'hero') {
    document.getElementById('hero').classList.remove('hidden');
  } else {
    const sec = document.getElementById(`section-${name}`);
    if (sec) {
      sec.classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      document.getElementById(`nav-${name}`)?.classList.add('active');
    }
  }

  state.currentSection = name;

  if (name === 'jobs') loadJobs();
  if (name === 'analytics') loadAnalytics();
  if (name === 'saved') { requireAuth(); loadSavedSearches(); }
  if (name === 'notifications') { requireAuth(); loadNotifications(); }

  document.getElementById('user-dropdown')?.classList.add('hidden');
}

function requireAuth() {
  if (!state.token) { openLoginModal(); return false; }
  return true;
}

// ─── Search ────────────────────────────────────────────────
function performSearch() {
  state.searchQuery = document.getElementById('hero-search').value.trim();
  state.searchLocation = document.getElementById('hero-location').value.trim();
  state.currentPage = 1;
  showSection('jobs');
}

function quickSearch(term) {
  document.getElementById('hero-search').value = term;
  performSearch();
}

function setupAutocomplete() {
  const input = document.getElementById('hero-search');
  if (!input) return;
  input.addEventListener('input', () => {
    clearTimeout(state.autocompleteTimer);
    const q = input.value.trim();
    if (q.length < 2) { document.getElementById('autocomplete').classList.add('hidden'); return; }
    state.autocompleteTimer = setTimeout(() => fetchAutocomplete(q), 280);
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter') performSearch(); });
}

async function fetchAutocomplete(q) {
  try {
    const data = await apiGet(`/search/autocomplete?q=${encodeURIComponent(q)}`);
    const dropdown = document.getElementById('autocomplete');
    const items = data.suggestions || [];
    if (!items.length) { dropdown.classList.add('hidden'); return; }
    dropdown.innerHTML = items.map(s => `
      <div class="autocomplete-item" onclick="selectAutocomplete('${s.value.replace(/'/g,"\\'")}')">
        <span>${escHtml(s.value)}</span>
        <span class="autocomplete-type">${s.type}</span>
      </div>
    `).join('');
    dropdown.classList.remove('hidden');
  } catch { /* ignore */ }
}

function selectAutocomplete(value) {
  document.getElementById('hero-search').value = value;
  document.getElementById('autocomplete').classList.add('hidden');
  performSearch();
}

// ─── Jobs ──────────────────────────────────────────────────
async function loadJobs() {
  showSkeletons();
  const params = new URLSearchParams({
    page: state.currentPage,
    page_size: state.pageSize,
    sort_by: state.sortBy,
    sort_order: 'desc',
  });
  if (state.searchQuery) params.set('q', state.searchQuery);
  if (state.searchLocation) params.set('location', state.searchLocation);
  if (state.filters.remote_type) params.set('remote', state.filters.remote_type);
  if (state.filters.experience) params.set('experience', state.filters.experience);
  if (state.filters.job_type) params.set('job_type', state.filters.job_type);
  if (state.salaryMin) params.set('salary_min', state.salaryMin * 100000);
  if (state.filters.days) params.set('posted_within_days', state.filters.days);
  if (state.filters.scam_risk) params.set('max_scam_risk', state.filters.scam_risk);

  try {
    const data = await apiGet(`/jobs?${params}`);
    state.totalJobs = data.total || 0;
    renderJobs(data.results || []);
    renderPagination(data.total_pages || 1);
    updateResultsInfo(data.total || 0);
  } catch (e) {
    showError('Failed to load jobs. Is the API running?');
  }
}

function showSkeletons() {
  document.getElementById('jobs-grid').innerHTML = Array(6).fill('<div class="job-skeleton"></div>').join('');
  document.getElementById('empty-state').classList.add('hidden');
}

function renderJobs(jobs) {
  const grid = document.getElementById('jobs-grid');
  if (!jobs.length) {
    grid.innerHTML = '';
    document.getElementById('empty-state').classList.remove('hidden');
    return;
  }
  document.getElementById('empty-state').classList.add('hidden');
  grid.innerHTML = jobs.map((job, i) => buildJobCard(job, i)).join('');
}

function buildJobCard(job, i) {
  const trust = getTrustBadge(job);
  const skills = (job.required_skills || []).slice(0, 5);
  const extra = (job.required_skills || []).length - 5;
  const metaPills = buildMetaPills(job);
  const posted = formatDate(job.posted_at);

  return `
  <div class="job-card" style="animation-delay:${i * 0.05}s" onclick="openJobDrawer('${escAttr(job.id)}')">
    <div class="job-card-top">
      <div class="company-logo">${escHtml(job.company_name?.[0] || '?')}</div>
      <div class="job-card-info">
        <div class="job-title">${escHtml(job.title)}</div>
        <div class="job-company">${escHtml(job.company_name)} · ${escHtml(job.location)}</div>
      </div>
      <div class="job-trust-badge ${trust.cls}">${trust.icon} ${trust.label}</div>
    </div>
    <div class="job-meta">${metaPills}</div>
    <div class="job-skills">
      ${skills.map(s => `<span class="skill-tag">${escHtml(s)}</span>`).join('')}
      ${extra > 0 ? `<span class="skill-tag more">+${extra}</span>` : ''}
    </div>
    <div class="job-card-footer">
      <span class="job-posted">${posted}</span>
      <span class="job-source">${escHtml(job.source_url ? getDomain(job.source_url) : '')}</span>
    </div>
  </div>`;
}

function buildMetaPills(job) {
  const pills = [];
  if (job.remote_type && job.remote_type !== 'unknown') {
    const icons = { remote: '🌍', hybrid: '🏠', on_site: '🏢' };
    const labels = { remote: 'Remote', hybrid: 'Hybrid', on_site: 'On-site' };
    pills.push(`<span class="meta-pill remote">${icons[job.remote_type] || ''} ${labels[job.remote_type] || job.remote_type}</span>`);
  }
  if (job.job_type && job.job_type !== 'unknown') {
    pills.push(`<span class="meta-pill">${escHtml(job.job_type.replace('_', ' '))}</span>`);
  }
  if (job.experience_level && job.experience_level !== 'unknown') {
    pills.push(`<span class="meta-pill">${escHtml(job.experience_level)}</span>`);
  }
  if (job.salary_display) {
    pills.push(`<span class="meta-pill salary">💰 ${escHtml(job.salary_display)}</span>`);
  }
  return pills.join('');
}

function getTrustBadge(job) {
  if (job.is_verified && job.scam_risk === 'very_low') return { cls: 'trust-verified', icon: '✅', label: 'Verified' };
  if (job.scam_risk === 'high' || job.scam_risk === 'very_high') return { cls: 'trust-risky', icon: '⚠️', label: 'Review' };
  return { cls: 'trust-low', icon: '🔎', label: 'Checking' };
}

// ─── Filters ───────────────────────────────────────────────
function setFilter(btn, filterKey, value) {
  state.filters[filterKey] = value;
  btn.closest('.filter-options').querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.currentPage = 1;
  loadJobs();
}

function onSalarySlider(val) {
  const v = parseInt(val);
  state.salaryMin = v > 0 ? v : null;
  document.getElementById('salary-display').textContent = v > 0 ? `₹${v}L+` : 'Any';
  clearTimeout(state.sliderTimer);
  state.sliderTimer = setTimeout(() => { state.currentPage = 1; loadJobs(); }, 500);
}

function clearFilters() {
  state.filters = { remote_type: '', experience: '', job_type: '', scam_risk: 'medium', days: '' };
  state.salaryMin = null;
  document.getElementById('salary-slider').value = 0;
  document.getElementById('salary-display').textContent = 'Any';
  document.querySelectorAll('.filter-btn').forEach(b => {
    const isDefault = b.dataset.value === '' || (b.dataset.filter === 'scam_risk' && b.dataset.value === 'medium');
    b.classList.toggle('active', isDefault);
  });
  state.currentPage = 1;
  loadJobs();
}

function onSortChange() {
  state.sortBy = document.getElementById('sort-select').value;
  state.currentPage = 1;
  loadJobs();
}

function updateResultsInfo(total) {
  const start = (state.currentPage - 1) * state.pageSize + 1;
  const end = Math.min(state.currentPage * state.pageSize, total);
  const query = state.searchQuery ? ` for "<b>${escHtml(state.searchQuery)}</b>"` : '';
  document.getElementById('results-count').innerHTML =
    total > 0 ? `Showing <b>${start}–${end}</b> of <b>${total}</b> jobs${query}` : `0 jobs found${query}`;
}

function renderPagination(totalPages) {
  const pg = document.getElementById('pagination');
  if (totalPages <= 1) { pg.innerHTML = ''; return; }
  const { currentPage: cp } = state;
  let html = '';

  if (cp > 1) html += `<button class="page-btn" onclick="goToPage(${cp-1})">‹</button>`;

  const range = getPageRange(cp, totalPages);
  let prev = null;
  range.forEach(p => {
    if (prev !== null && p - prev > 1) html += `<button class="page-btn" disabled>…</button>`;
    html += `<button class="page-btn ${p === cp ? 'active' : ''}" onclick="goToPage(${p})">${p}</button>`;
    prev = p;
  });

  if (cp < totalPages) html += `<button class="page-btn" onclick="goToPage(${cp+1})">›</button>`;
  pg.innerHTML = html;
}

function getPageRange(current, total) {
  const delta = 2;
  const pages = new Set([1, total]);
  for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) pages.add(i);
  return [...pages].sort((a, b) => a - b);
}

function goToPage(page) {
  state.currentPage = page;
  loadJobs();
  document.getElementById('section-jobs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Job Drawer ────────────────────────────────────────────
async function openJobDrawer(jobId) {
  document.getElementById('drawer-overlay').classList.remove('hidden');
  const drawer = document.getElementById('job-drawer');
  drawer.classList.remove('hidden');
  document.getElementById('drawer-content').innerHTML = '<div class="loading-spinner"></div>';
  setTimeout(() => drawer.style.transform = 'translateX(0)', 10);
  document.body.style.overflow = 'hidden';

  try {
    const job = await apiGet(`/jobs/${jobId}`);
    renderDrawer(job);
  } catch {
    document.getElementById('drawer-content').innerHTML = '<div style="text-align:center;padding:60px;color:var(--text-muted)">Failed to load job details</div>';
  }
}

function closeDrawer() {
  document.getElementById('job-drawer').classList.add('hidden');
  document.getElementById('drawer-overlay').classList.add('hidden');
  document.body.style.overflow = '';
}

function renderDrawer(job) {
  const trust = job.verification || {};
  const scamPct = Math.round((1 - (trust.scam_probability || 0)) * 100);
  const trustColor = scamPct > 75 ? '#34D399' : scamPct > 45 ? '#FBBF24' : '#F87171';

  const skillsHtml = [...(job.skills?.required || []), ...(job.skills?.tech_stack || [])]
    .filter((v, i, a) => a.indexOf(v) === i).slice(0, 20)
    .map(s => `<span class="skill-tag">${escHtml(s)}</span>`).join('');

  const niceToHave = (job.skills?.nice_to_have || [])
    .map(s => `<span class="skill-tag" style="opacity:0.6">${escHtml(s)}</span>`).join('');

  document.getElementById('drawer-content').innerHTML = `
  <div class="drawer-header">
    <div class="drawer-logo">${escHtml(job.company?.name?.[0] || '?')}</div>
    <div>
      <div class="drawer-title">${escHtml(job.title)}</div>
      <div class="drawer-company">${escHtml(job.company?.name)} · ${escHtml(job.location?.display || 'Unknown')}</div>
    </div>
    <button class="drawer-close-btn" onclick="closeDrawer()">✕</button>
  </div>

  <div class="drawer-actions">
    ${job.apply_url ? `<a href="${escAttr(job.apply_url)}" target="_blank" rel="noopener" class="btn btn-primary">Apply Now →</a>` : ''}
    <button class="btn btn-ghost" onclick="saveCurrentSearch()">🔔 Save Alert</button>
    <button class="btn btn-ghost" onclick="reportJob('${escAttr(job.id)}')">⚑ Report</button>
  </div>

  <div class="drawer-meta-grid drawer-section">
    ${buildMetaItem('Job Type', job.job_type?.replace('_', ' ') || 'Unknown')}
    ${buildMetaItem('Remote', job.remote_type?.replace('_', ' ') || 'Unknown')}
    ${buildMetaItem('Experience', job.experience_level || 'Unknown')}
    ${buildMetaItem('Salary', job.salary?.display || 'Not disclosed')}
    ${buildMetaItem('Posted', formatDate(job.posted_at))}
    ${buildMetaItem('Source', getDomain(job.source_url) || job.source || 'Unknown')}
  </div>

  ${skillsHtml ? `<div class="drawer-section"><h4>Required Skills</h4><div class="job-skills">${skillsHtml}</div></div>` : ''}
  ${niceToHave ? `<div class="drawer-section"><h4>Nice to Have</h4><div class="job-skills">${niceToHave}</div></div>` : ''}

  <div class="drawer-section">
    <h4>About the Role</h4>
    <div class="drawer-description">${escHtml(job.description || 'No description provided.').substring(0, 3000)}</div>
  </div>

  <div class="drawer-section">
    <h4>Trust & Verification</h4>
    <div class="drawer-meta-item" style="background:var(--bg-glass)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <span style="font-weight:700;font-size:1.1rem;color:${trustColor}">${scamPct}% Trust Score</span>
        <span style="font-size:0.8rem;color:var(--text-muted)">${trust.is_verified ? '✅ Verified' : '🔎 Unverified'}</span>
      </div>
      <div class="trust-bar"><div class="trust-fill" style="width:${scamPct}%;background:${trustColor}"></div></div>
      ${(trust.scam_triggered_rules||[]).length ? `<div style="margin-top:10px;font-size:0.8rem;color:var(--text-muted)">Flags: ${trust.scam_triggered_rules.join(', ')}</div>` : ''}
    </div>
  </div>`;
}

function buildMetaItem(label, value) {
  return `<div class="drawer-meta-item"><div class="drawer-meta-label">${label}</div><div class="drawer-meta-value">${escHtml(String(value || '—'))}</div></div>`;
}

// ─── Analytics ─────────────────────────────────────────────
async function loadAnalytics() {
  document.getElementById('analytics-grid').innerHTML = '<div class="analytics-skeleton"></div><div class="analytics-skeleton"></div><div class="analytics-skeleton"></div>';
  try {
    const [skills, salary, remote] = await Promise.all([
      apiGet('/analytics/skill-demand?limit=15'),
      apiGet('/analytics/salary-benchmarks'),
      apiGet('/analytics/remote-breakdown'),
    ]);
    renderAnalytics(skills, salary, remote);
  } catch { showToast('Could not load analytics data', 'error'); }
}

function renderAnalytics(skills, salary, remote) {
  const maxSkill = Math.max(...(skills.top_skills||[]).map(s => s.job_count), 1);
  const skillBars = (skills.top_skills || []).map(s => `
    <div class="skill-bar-row">
      <div class="skill-bar-name" title="${escHtml(s.skill)}">${escHtml(s.skill)}</div>
      <div class="skill-bar-track"><div class="skill-bar-fill" style="width:${(s.job_count/maxSkill)*100}%"></div></div>
      <div class="skill-bar-count">${s.job_count}</div>
    </div>`).join('');

  const salaryRows = (salary.benchmarks || []).map(b => {
    const max = 5000000;
    const minW = Math.min((b.avg_salary_min / max) * 100, 100);
    const maxW = Math.min((b.avg_salary_max / max) * 100, 100);
    const dispMin = b.avg_salary_min >= 100000 ? `₹${(b.avg_salary_min/100000).toFixed(1)}L` : '—';
    const dispMax = b.avg_salary_max >= 100000 ? `₹${(b.avg_salary_max/100000).toFixed(1)}L` : '—';
    return `
    <div class="salary-exp-row">
      <div class="salary-exp-label">${escHtml(b.experience_level || '?')}</div>
      <div class="salary-range-bar" style="position:relative">
        <div class="salary-range-fill" style="left:${minW}%;width:${Math.max(maxW-minW,3)}%"></div>
      </div>
      <div class="salary-range-text">${dispMin} – ${dispMax}</div>
    </div>`;
  }).join('');

  const remoteData = remote.breakdown || {};
  const remoteColors = { remote: '#22D3EE', hybrid: '#8B5CF6', on_site: '#F87171', unknown: '#6B6896' };
  const remoteLegend = Object.entries(remoteData).map(([k, v]) =>
    `<div class="legend-item"><div class="legend-dot" style="background:${remoteColors[k]||'#6B6896'}"></div>${escHtml(k.replace('_',' '))} <b style="margin-left:auto">${v.percentage}%</b></div>`
  ).join('');

  document.getElementById('analytics-grid').innerHTML = `
  <div class="analytics-card">
    <h3>🔥 Top Skills in Demand</h3>
    <div>${skillBars || '<p style="color:var(--text-muted)">No data available yet</p>'}</div>
  </div>
  <div class="analytics-card">
    <h3>💰 Salary Benchmarks (INR)</h3>
    <div class="salary-row">${salaryRows || '<p style="color:var(--text-muted)">No salary data available yet</p>'}</div>
  </div>
  <div class="analytics-card">
    <h3>🌍 Remote vs On-site</h3>
    <div class="remote-legend">${remoteLegend || '<p style="color:var(--text-muted)">No data available yet</p>'}</div>
  </div>`;
}

// ─── Saved Searches ────────────────────────────────────────
async function loadSavedSearches() {
  if (!state.token) return;
  const container = document.getElementById('saved-searches-list');
  container.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await apiGet('/users/me/saved-searches');
    renderSavedSearches(data.saved_searches || []);
  } catch { container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px">Failed to load saved searches</p>'; }
}

function renderSavedSearches(searches) {
  const container = document.getElementById('saved-searches-list');
  if (!searches.length) {
    container.innerHTML = `
      <div style="text-align:center;padding:60px 20px">
        <div style="font-size:3rem;margin-bottom:16px">🔍</div>
        <h3 style="margin-bottom:8px">No saved searches yet</h3>
        <p style="color:var(--text-muted);margin-bottom:24px">Save a search to get alerts when new jobs are posted</p>
        <button class="btn btn-primary" onclick="showSection('jobs')">Browse Jobs</button>
      </div>`;
    return;
  }
  container.innerHTML = searches.map(s => `
  <div class="saved-search-card">
    <div class="ss-info">
      <div class="ss-name">${escHtml(s.name)}</div>
      <div class="ss-meta">
        ${s.query ? `"${escHtml(s.query)}"` : 'All jobs'}
        ${s.last_triggered_at ? ` · Last match: ${formatDate(s.last_triggered_at)}` : ' · No matches yet'}
      </div>
    </div>
    <div class="ss-toggle">
      <span style="font-size:0.8rem">${s.alert_enabled ? 'Alerts on' : 'Alerts off'}</span>
      <div class="toggle ${s.alert_enabled ? 'on' : ''}" onclick="toggleAlert('${s.id}', this, ${!s.alert_enabled})"></div>
    </div>
    <button class="btn btn-ghost" style="font-size:0.82rem;padding:6px 12px" onclick="runSavedSearch('${escAttr(s.query)}')">Search →</button>
    <button class="btn-text" style="color:var(--rose-400)" onclick="deleteSavedSearch('${s.id}')">Delete</button>
  </div>`).join('');
}

async function toggleAlert(searchId, el, newState) {
  el.classList.toggle('on', newState);
  try {
    await apiPatch(`/users/me/saved-searches/${searchId}`, { alert_enabled: newState });
    showToast(`Alerts ${newState ? 'enabled' : 'disabled'}`, 'success');
    el.nextElementSibling && (el.previousElementSibling.textContent = newState ? 'Alerts on' : 'Alerts off');
  } catch { showToast('Failed to update alert', 'error'); el.classList.toggle('on', !newState); }
}

async function deleteSavedSearch(id) {
  if (!confirm('Delete this saved search?')) return;
  try {
    await apiDelete(`/users/me/saved-searches/${id}`);
    showToast('Saved search deleted', 'success');
    loadSavedSearches();
  } catch { showToast('Failed to delete', 'error'); }
}

function runSavedSearch(query) {
  document.getElementById('hero-search').value = query;
  showSection('jobs');
}

function saveCurrentSearch() {
  if (!state.token) { openLoginModal(); return; }
  document.getElementById('ss-name').value = state.searchQuery || 'My Job Search';
  openModal('modal-save-search');
}

async function submitSaveSearch(e) {
  e.preventDefault();
  const name = document.getElementById('ss-name').value.trim();
  const alerts = document.getElementById('ss-alerts').checked;
  try {
    await apiPost('/users/me/saved-searches', {
      name, query: state.searchQuery,
      filters: state.filters,
      alert_enabled: alerts,
    });
    showToast('Search saved! You\'ll get alerts for new matches', 'success');
    closeModal();
  } catch { showToast('Failed to save search', 'error'); }
}

// ─── Notifications ─────────────────────────────────────────
async function loadNotifCount() {
  if (!state.token) return;
  try {
    const data = await apiGet('/notifications/stats');
    const count = data.unread || 0;
    state.notifCount = count;
    const badge = document.getElementById('notif-badge');
    if (badge) { badge.textContent = count; badge.classList.toggle('hidden', count === 0); }
  } catch { /* silent */ }
}

async function loadNotifications() {
  if (!state.token) return;
  const container = document.getElementById('notifications-list');
  container.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const data = await apiGet('/notifications?page_size=30');
    renderNotifications(data.notifications || []);
  } catch { container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px">Could not load notifications</p>'; }
}

function renderNotifications(notifications) {
  const container = document.getElementById('notifications-list');
  if (!notifications.length) {
    container.innerHTML = '<div style="text-align:center;padding:60px;color:var(--text-muted)">No notifications yet</div>';
    return;
  }
  const channelIcons = { email: '📧', telegram: '📱', in_app: '📌', webhook: '🔗' };
  container.innerHTML = notifications.map(n => `
  <div class="notif-card ${!n.is_read ? 'unread' : ''}">
    <div class="notif-icon">${channelIcons[n.channel] || '🔔'}</div>
    <div class="notif-body">
      <div class="notif-subject">${escHtml(n.subject || 'Notification')}</div>
      <div class="notif-time">${formatDate(n.created_at)}</div>
    </div>
    ${!n.is_read ? `<button class="notif-read-btn" onclick="markRead('${n.id}', this)">Mark read</button>` : ''}
  </div>`).join('');
}

async function markRead(id, btn) {
  try {
    await apiPatch(`/notifications/${id}/read`, {});
    btn.closest('.notif-card').classList.remove('unread');
    btn.remove();
    loadNotifCount();
  } catch { /* silent */ }
}

async function markAllRead() {
  try {
    await apiPost('/notifications/read-all', {});
    showToast('All notifications marked as read', 'success');
    loadNotifications();
    loadNotifCount();
  } catch { showToast('Failed to update notifications', 'error'); }
}

async function reportJob(jobId) {
  const reason = prompt('Why are you reporting this job? (scam, misleading, expired, other)');
  if (!reason) return;
  try {
    await apiPost(`/jobs/${jobId}/report?reason=${encodeURIComponent(reason)}`, {});
    showToast('Report submitted. Thank you for keeping TalentLens safe!', 'success');
  } catch { showToast('Failed to submit report', 'error'); }
}

// ─── Auth Modals ───────────────────────────────────────────
function openLoginModal() { openModal('modal-login'); }
function openRegisterModal() { openModal('modal-register'); }
function openModal(id) {
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
}
function switchToLogin() { openModal('modal-login'); }
function switchToRegister() { openModal('modal-register'); }
document.getElementById('modal-overlay')?.addEventListener('click', closeModal);

async function submitLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-submit');
  const err = document.getElementById('login-error');
  btn.textContent = 'Signing in…'; btn.disabled = true; err.classList.add('hidden');
  try {
    const data = await apiPost('/auth/login', {
      email: document.getElementById('login-email').value,
      password: document.getElementById('login-password').value,
    }, false);
    localStorage.setItem('token', data.access_token);
    state.token = data.access_token;
    closeModal();
    await restoreSession();
    showToast('Welcome back!', 'success');
  } catch (ex) {
    err.textContent = ex.message || 'Invalid email or password';
    err.classList.remove('hidden');
  } finally { btn.textContent = 'Sign In'; btn.disabled = false; }
}

async function submitRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('reg-submit');
  const err = document.getElementById('reg-error');
  btn.textContent = 'Creating…'; btn.disabled = true; err.classList.add('hidden');
  try {
    const data = await apiPost('/auth/register', {
      email: document.getElementById('reg-email').value,
      password: document.getElementById('reg-password').value,
      full_name: document.getElementById('reg-name').value,
    }, false);
    localStorage.setItem('token', data.access_token);
    state.token = data.access_token;
    closeModal();
    await restoreSession();
    showToast('Account created! Welcome to TalentLens 🎉', 'success');
  } catch (ex) {
    err.textContent = ex.message || 'Registration failed';
    err.classList.remove('hidden');
  } finally { btn.textContent = 'Create Account'; btn.disabled = false; }
}

// ─── API Helpers ───────────────────────────────────────────
async function apiGet(path) {
  const res = await fetch(API_BASE + path, { headers: authHeader() });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function apiPost(path, body, auth = true) {
  const res = await fetch(API_BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...(auth ? authHeader() : {}) },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function apiPatch(path, body) {
  const res = await fetch(API_BASE + path, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}
async function apiDelete(path) {
  const res = await fetch(API_BASE + path, { method: 'DELETE', headers: authHeader() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json().catch(() => ({}));
}
function authHeader() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }

// ─── UI Helpers ────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  t.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; setTimeout(() => t.remove(), 300); }, 3500);
}

function showError(msg) {
  document.getElementById('jobs-grid').innerHTML = '';
  document.getElementById('empty-state').classList.remove('hidden');
  document.getElementById('empty-state').querySelector('p').textContent = msg;
}

function formatDate(dateStr) {
  if (!dateStr) return 'Unknown';
  try {
    const d = new Date(dateStr);
    const now = Date.now();
    const diff = now - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return dateStr; }
}

function getDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); } catch { return ''; }
}

function escHtml(s) {
  if (typeof s !== 'string') s = String(s || '');
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function escAttr(s) { return String(s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

// Auto-load jobs on section init when first visiting
window.addEventListener('load', () => {
  // Show jobs on page load trigger
  const params = new URLSearchParams(window.location.search);
  if (params.get('q')) {
    document.getElementById('hero-search').value = params.get('q');
    showSection('jobs');
  }
});
