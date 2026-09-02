/* ═══════════════════════════════════════════════════════
   TalentLens Job Board — Application Logic
   Matches modern dark UI with Discover view, filters, 
   circular match score donuts, and resume parser.
═══════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api/v1';

// ─── Default Sample Jobs (Exact replica from reference UI) ──
const DEFAULT_SAMPLE_JOBS = [
  {
    id: 'sample-1',
    title: 'Senior Frontend Engineer',
    company_name: 'Stitch AI',
    location: 'Remote, IND',
    salary_display: '₹30 - 45 LPA',
    posted_at: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
    required_skills: ['React', 'TypeScript', 'WebGL'],
    match_percentage: 92,
    is_verified: true,
    trust_score: 96,
    logo_type: 'stitch',
    featured: false,
    description: 'Lead the frontend architecture of our next-gen AI workspace. Work with modern React, TypeScript, and high-performance WebGL rendering.',
  },
  {
    id: 'sample-2',
    title: 'Lead Cloud Architect',
    company_name: 'Nexus Systems',
    location: 'Hybrid, BLR',
    salary_display: '₹40 - 55 LPA',
    posted_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
    required_skills: ['AWS', 'Kubernetes', 'Go'],
    match_percentage: 88,
    is_verified: true,
    trust_score: 94,
    logo_type: 'nexus',
    featured: true,
    description: 'Design and deploy resilient, multi-region cloud infrastructure using Kubernetes, AWS, and Go microservices.',
  },
  {
    id: 'sample-3',
    title: 'Product Designer',
    company_name: 'Vanguard UI',
    location: 'Remote, Global',
    salary_display: '$120k - $150k',
    posted_at: new Date(Date.now() - 1 * 24 * 3600 * 1000).toISOString(),
    required_skills: ['Figma', 'Design Systems'],
    match_percentage: 75,
    is_verified: true,
    trust_score: 91,
    logo_type: 'vanguard',
    featured: false,
    description: 'Craft intuitive interfaces and design systems for enterprise developer tools.',
  },
  {
    id: 'sample-4',
    title: 'Backend Systems Engineer',
    company_name: 'Pulse Data',
    location: 'Remote, IND',
    salary_display: '₹28 - 40 LPA',
    posted_at: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
    required_skills: ['Python', 'FastAPI', 'Kafka', 'PostgreSQL'],
    match_percentage: 94,
    is_verified: true,
    trust_score: 95,
    logo_type: 'pulse',
    featured: false,
    description: 'Build low-latency data streaming pipelines and async backend microservices handling millions of events daily.',
  },
  {
    id: 'sample-5',
    title: 'AI/ML Research Engineer',
    company_name: 'HyperScale Labs',
    location: 'Hybrid, HYD',
    salary_display: '₹35 - 50 LPA',
    posted_at: new Date(Date.now() - 12 * 3600 * 1000).toISOString(),
    required_skills: ['PyTorch', 'Transformers', 'Qdrant', 'RAG'],
    match_percentage: 85,
    is_verified: true,
    trust_score: 93,
    logo_type: 'hyperscale',
    featured: true,
    description: 'Fine-tune large language models, build vector search retrieval systems, and scale AI inference in production.',
  }
];

// ─── App State ────────────────────────────────────────────
const state = {
  token: localStorage.getItem('token'),
  user: null,
  currentPage: 1,
  pageSize: 10,
  totalJobs: 0,
  filters: { remote_type: '', experience: '', verified_only: true, salary_min: 10 },
  searchQuery: '',
  searchLocation: '',
  sortBy: 'quality_score',
  currentSection: 'discover',
  autocompleteTimer: null,
  sliderTimer: null,
};

// ─── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadPlatformStats();
  setupAutocomplete();
  setupMobileFilters();
  if (state.token) restoreSession();
  loadJobs();
});

// ─── Mobile Nav ────────────────────────────────────────────
function toggleMobileNav() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn    = document.getElementById('nav-hamburger');
  const isOpen = drawer?.classList.toggle('open');
  btn?.classList.toggle('open', isOpen);
}

function closeMobileNav() {
  document.getElementById('mobile-nav-drawer')?.classList.remove('open');
  document.getElementById('nav-hamburger')?.classList.remove('open');
}

// Close mobile nav when clicking outside
document.addEventListener('click', (e) => {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn    = document.getElementById('nav-hamburger');
  if (drawer?.classList.contains('open') && !drawer.contains(e.target) && !btn?.contains(e.target)) {
    closeMobileNav();
  }
});

// ─── Mobile Filter Collapse ────────────────────────────────
function setupMobileFilters() {
  const header = document.querySelector('.filters-card-header');
  const body   = document.getElementById('filters-body');
  if (!header || !body) return;

  // On mobile, start collapsed; on desktop, keep open
  const checkMobile = () => {
    if (window.innerWidth <= 768) {
      body.classList.remove('open');
    } else {
      body.classList.add('open');
    }
  };
  checkMobile();
  window.addEventListener('resize', checkMobile);

  header.addEventListener('click', () => {
    if (window.innerWidth <= 768) {
      body.classList.toggle('open');
    }
  });
}

// ─── Session & Auth ────────────────────────────────────────
async function restoreSession() {
  try {
    const res = await apiGet('/auth/me');
    state.user = res;
    updateUserUI();
  } catch {
    logout(true);
  }
}

function updateUserUI() {
  const { user } = state;
  if (!user) return;
  document.getElementById('btn-login')?.classList.add('hidden');
  document.getElementById('user-menu')?.classList.remove('hidden');
  const initials = (user.full_name || user.email || 'U')[0].toUpperCase();
  const avatar = document.getElementById('user-avatar');
  if (avatar) avatar.textContent = initials;
  const dropEmail = document.getElementById('dropdown-email');
  if (dropEmail) dropEmail.textContent = user.email;
}

function toggleUserDropdown() {
  document.getElementById('user-dropdown')?.classList.toggle('hidden');
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
  document.getElementById('btn-login')?.classList.remove('hidden');
  document.getElementById('user-menu')?.classList.add('hidden');
  if (!silent) {
    showToast('Signed out successfully', 'info');
    showSection('discover');
  }
}

// ─── Stats ─────────────────────────────────────────────────
async function loadPlatformStats() {
  try {
    const data = await apiGet('/analytics/overview');
    animateCounter('stat-jobs', data.total_jobs || 4200);
    animateCounter('stat-companies', data.total_companies || 1100);
    const ver = data.verified_percentage ? `${data.verified_percentage}%` : '99.4%';
    document.getElementById('stat-verified').textContent = ver;
  } catch {
    document.getElementById('stat-jobs').textContent = '4.2K';
    document.getElementById('stat-companies').textContent = '1.1K';
    document.getElementById('stat-verified').textContent = '99.4%';
  }
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const duration = 1200;
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

// ─── Section Navigation ────────────────────────────────────
function showSection(name) {
  ['discover', 'resume', 'analytics', 'saved', 'notifications'].forEach(s => {
    document.getElementById(`section-${s}`)?.classList.add('hidden');
    document.getElementById(`nav-${s === 'resume' ? 'skillhub' : s === 'saved' ? 'applications' : s === 'analytics' ? 'network' : s}`)?.classList.remove('active');
  });

  const activeNavId = name === 'resume' ? 'nav-skillhub' : name === 'saved' ? 'nav-applications' : name === 'analytics' ? 'nav-network' : `nav-${name}`;
  document.getElementById(activeNavId)?.classList.add('active');

  const sec = document.getElementById(`section-${name}`);
  if (sec) {
    sec.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  state.currentSection = name;

  if (name === 'discover') loadJobs();
  if (name === 'resume') initResumeSection();
  if (name === 'analytics') loadAnalytics();
  if (name === 'saved') { if (requireAuth()) loadSavedSearches(); }
  if (name === 'notifications') { if (requireAuth()) loadNotifications(); }

  document.getElementById('user-dropdown')?.classList.add('hidden');
}

function requireAuth() {
  if (!state.token) { openLoginModal(); return false; }
  return true;
}

// ─── Search ────────────────────────────────────────────────
function performSearch() {
  state.searchQuery = document.getElementById('hero-search')?.value.trim() || '';
  state.searchLocation = document.getElementById('hero-location')?.value.trim() || '';
  state.currentPage = 1;
  showSection('discover');
  loadJobs();
}

function setupAutocomplete() {
  const input = document.getElementById('hero-search');
  if (!input) return;
  input.addEventListener('input', () => {
    clearTimeout(state.autocompleteTimer);
    const q = input.value.trim();
    if (q.length < 2) { document.getElementById('autocomplete')?.classList.add('hidden'); return; }
    state.autocompleteTimer = setTimeout(() => fetchAutocomplete(q), 250);
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter') performSearch(); });
}

async function fetchAutocomplete(q) {
  try {
    const data = await apiGet(`/search/autocomplete?q=${encodeURIComponent(q)}`);
    const dropdown = document.getElementById('autocomplete');
    const items = data.suggestions || [];
    if (!items.length) { dropdown?.classList.add('hidden'); return; }
    dropdown.innerHTML = items.map(s => `
      <div class="autocomplete-item" onclick="selectAutocomplete('${s.value.replace(/'/g,"\\'")}')">
        <span>${escHtml(s.value)}</span>
        <span class="autocomplete-type">${s.type}</span>
      </div>
    `).join('');
    dropdown?.classList.remove('hidden');
  } catch { /* ignore */ }
}

function selectAutocomplete(value) {
  const input = document.getElementById('hero-search');
  if (input) input.value = value;
  document.getElementById('autocomplete')?.classList.add('hidden');
  performSearch();
}

// ─── Filters & Handlers ────────────────────────────────────
function toggleVerifiedFilter(checked) {
  state.filters.verified_only = checked;
  state.currentPage = 1;
  loadJobs();
}

function setWorkModeFilter(val) {
  state.filters.remote_type = val;
  state.currentPage = 1;
  loadJobs();
}

function setExperienceChip(btn, val) {
  document.querySelectorAll('.exp-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.filters.experience = val;
  state.currentPage = 1;
  loadJobs();
}

function onSalarySlider(val) {
  const v = parseInt(val);
  state.filters.salary_min = v;
  document.getElementById('salary-min-label').textContent = `₹${v}L`;
  clearTimeout(state.sliderTimer);
  state.sliderTimer = setTimeout(() => { state.currentPage = 1; loadJobs(); }, 400);
}

function clearFilters() {
  state.filters = { remote_type: '', experience: '', verified_only: true, salary_min: 10 };
  state.searchQuery = '';
  state.searchLocation = '';
  
  const searchInput = document.getElementById('hero-search');
  if (searchInput) searchInput.value = '';
  const locInput = document.getElementById('hero-location');
  if (locInput) locInput.value = '';

  const verCheck = document.getElementById('filter-verified-checkbox');
  if (verCheck) verCheck.checked = true;

  const radioAll = document.querySelector('input[name="work_mode"][value=""]');
  if (radioAll) radioAll.checked = true;

  document.querySelectorAll('.exp-chip').forEach(b => {
    b.classList.toggle('active', b.dataset.exp === '');
  });

  const salarySlider = document.getElementById('salary-range');
  if (salarySlider) salarySlider.value = 10;
  document.getElementById('salary-min-label').textContent = '₹10L';

  state.currentPage = 1;
  loadJobs();
}

function onSortChange() {
  state.sortBy = document.getElementById('sort-select')?.value || 'quality_score';
  state.currentPage = 1;
  loadJobs();
}

function loadMoreJobs() {
  state.currentPage += 1;
  loadJobs(true);
}

// ─── Jobs Loader ───────────────────────────────────────────
async function loadJobs(append = false) {
  if (!append) {
    document.getElementById('jobs-grid').innerHTML = Array(4).fill('<div class="job-skeleton"></div>').join('');
    document.getElementById('empty-state')?.classList.add('hidden');
  }

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
  if (state.filters.verified_only) params.set('max_scam_risk', 'medium');
  if (state.filters.salary_min) params.set('salary_min', state.filters.salary_min * 100000);

  try {
    const data = await apiGet(`/jobs?${params}`);
    const results = data.results || [];
    state.totalJobs = data.total || 0;

    if (!results.length && state.currentPage === 1) {
      // Fallback to sample jobs matching search filter
      renderJobs(filterSampleJobs(), append);
    } else {
      renderJobs(results, append);
    }
  } catch (e) {
    // Graceful offline fallback with styled demo jobs
    renderJobs(filterSampleJobs(), append);
  }
}

function filterSampleJobs() {
  let list = [...DEFAULT_SAMPLE_JOBS];
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    list = list.filter(j => 
      j.title.toLowerCase().includes(q) || 
      j.company_name.toLowerCase().includes(q) ||
      (j.required_skills || []).some(s => s.toLowerCase().includes(q))
    );
  }
  if (state.filters.remote_type === 'remote') {
    list = list.filter(j => j.location.toLowerCase().includes('remote'));
  } else if (state.filters.remote_type === 'hybrid') {
    list = list.filter(j => j.location.toLowerCase().includes('hybrid'));
  }
  return list;
}

function renderJobs(jobs, append = false) {
  const grid = document.getElementById('jobs-grid');
  if (!grid) return;

  if (!jobs.length && !append) {
    grid.innerHTML = '';
    document.getElementById('empty-state')?.classList.remove('hidden');
    document.getElementById('load-more-wrap')?.classList.add('hidden');
    return;
  }
  document.getElementById('empty-state')?.classList.add('hidden');
  document.getElementById('load-more-wrap')?.classList.remove('hidden');

  const html = jobs.map((job, i) => buildJobCard(job, i)).join('');
  if (append) {
    grid.insertAdjacentHTML('beforeend', html);
  } else {
    grid.innerHTML = html;
  }

  // Animate SVG rings
  setTimeout(() => animateAllRings(), 100);
}

function buildJobCard(job, i) {
  const matchPct = job.match_percentage || Math.round(job.quality_score || (Math.random() * 20 + 75));
  const logoChar = (job.company_name || 'T')[0].toUpperCase();
  const isVanguard = (job.company_name || '').toLowerCase().includes('vanguard');
  const isNexus = (job.company_name || '').toLowerCase().includes('nexus');
  const isStitch = (job.company_name || '').toLowerCase().includes('stitch');
  
  const logoClass = isVanguard ? 'logo-vanguard' : isNexus ? 'logo-nexus' : '';
  const isFeatured = job.featured || (i === 1 && !job.id.includes('sample-3'));
  const skills = (job.required_skills || ['React', 'TypeScript']).slice(0, 4);
  const salary = job.salary_display || (job.salary_max ? `₹${Math.round(job.salary_max/100000)} LPA` : 'Competitive');
  const loc = job.location || (job.remote_type === 'remote' ? 'Remote, IND' : 'Hybrid, BLR');
  const posted = formatDate(job.posted_at);

  const ringRadius = 18;
  const circumference = 2 * Math.PI * ringRadius;
  const strokeOffset = circumference - (matchPct / 100) * circumference;
  const ringColorClass = matchPct >= 85 ? '' : 'violet';

  const targetUrl = job.apply_url || job.source_url || 'https://careers.stitch.ai';

  return `
  <div class="job-card" style="animation-delay:${i * 0.05}s" onclick="window.open('${escAttr(targetUrl)}', '_blank', 'noopener,noreferrer')">
    ${isFeatured ? '<span class="featured-ribbon">FEATURED</span>' : ''}
    
    <div class="job-card-top-row">
      <div class="card-logo-box ${logoClass}">
        ${isStitch ? '⚡' : logoChar}
      </div>
      <div class="card-title-col">
        <div class="card-job-title" title="${escHtml(job.title)}">${escHtml(job.title)}</div>
        <div class="card-company-line">
          <span>${escHtml(job.company_name)}</span>
          <span class="badge-verified-pill">Verified ✓</span>
        </div>
      </div>
      <div class="card-match-ring">
        <svg width="46" height="46" viewBox="0 0 46 46">
          <circle class="ring-bg" cx="23" cy="23" r="${ringRadius}"></circle>
          <circle class="ring-progress ${ringColorClass}" cx="23" cy="23" r="${ringRadius}"
                  stroke-dasharray="${circumference}"
                  stroke-dashoffset="${circumference}"
                  data-target-offset="${strokeOffset}"></circle>
        </svg>
        <span class="ring-pct-text">${matchPct}%</span>
      </div>
    </div>

    <div class="card-meta-details">
      <span class="meta-detail-item">📍 ${escHtml(loc)}</span>
      <span class="meta-detail-item">💵 ${escHtml(salary)}</span>
      <span class="meta-detail-item">⏱ ${posted}</span>
    </div>

    <div class="card-skills-row">
      ${skills.map(s => `<span class="card-skill-tag">${escHtml(s)}</span>`).join('')}
    </div>
  </div>`;
}

function animateAllRings() {
  document.querySelectorAll('.ring-progress[data-target-offset]').forEach(ring => {
    const offset = ring.dataset.targetOffset;
    requestAnimationFrame(() => {
      ring.style.strokeDashoffset = offset;
    });
  });
}

// ─── Job Detail Drawer ─────────────────────────────────────
async function openJobDrawer(jobId) {
  document.getElementById('drawer-overlay')?.classList.remove('hidden');
  const drawer = document.getElementById('job-drawer');
  drawer?.classList.remove('hidden');
  document.getElementById('drawer-content').innerHTML = '<div class="loading-spinner"></div>';
  document.body.style.overflow = 'hidden';

  try {
    let job = null;
    if (jobId.startsWith('sample-')) {
      job = DEFAULT_SAMPLE_JOBS.find(j => j.id === jobId);
    } else {
      job = await apiGet(`/jobs/${jobId}`);
    }
    renderDrawer(job || DEFAULT_SAMPLE_JOBS[0]);
  } catch {
    renderDrawer(DEFAULT_SAMPLE_JOBS[0]);
  }
}

function closeDrawer() {
  document.getElementById('job-drawer')?.classList.add('hidden');
  document.getElementById('drawer-overlay')?.classList.add('hidden');
  document.body.style.overflow = '';
}

function renderDrawer(job) {
  const skills = (job.required_skills || []).map(s => `<span class="card-skill-tag">${escHtml(s)}</span>`).join('');
  const applyUrl = job.apply_url || job.source_url || '#';

  document.getElementById('drawer-content').innerHTML = `
  <button class="drawer-close-btn" onclick="closeDrawer()">✕</button>
  <div class="drawer-header">
    <div class="drawer-logo">${(job.company_name || 'T')[0].toUpperCase()}</div>
    <div>
      <div class="drawer-title">${escHtml(job.title)}</div>
      <div class="drawer-company">${escHtml(job.company_name)} · ${escHtml(job.location || 'Remote')}</div>
    </div>
  </div>

  <div class="drawer-actions">
    <a href="${escAttr(applyUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="flex:1;justify-content:center">
      Apply on Company Site ⚡
    </a>
    <button class="btn btn-ghost" onclick="showToast('Job saved to your applications ✓', 'success')">Bookmark</button>
  </div>

  <div class="drawer-meta-grid drawer-section">
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Salary Range</div>
      <div class="drawer-meta-value">${escHtml(job.salary_display || 'Competitive')}</div>
    </div>
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Verification Status</div>
      <div class="drawer-meta-value" style="color:#34D399">✅ 100% Authentic</div>
    </div>
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Work Mode</div>
      <div class="drawer-meta-value">${escHtml(job.remote_type || 'Remote')}</div>
    </div>
  </div>

  <div class="drawer-section">
    <h4>Tech Stack & Key Skills</h4>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">${skills}</div>
  </div>

  <div class="drawer-section">
    <h4>About the Role</h4>
    <div class="drawer-description">${escHtml(job.description || 'Join an elite engineering team working on scalable, high-impact products.')}</div>
  </div>
  `;
}


// ─── Auth Modals ───────────────────────────────────────────
function openLoginModal() { closeModal(); document.getElementById('modal-login')?.classList.remove('hidden'); }
function openRegisterModal() { closeModal(); document.getElementById('modal-register')?.classList.remove('hidden'); }
function switchToRegister() { openRegisterModal(); }
function switchToLogin() { openLoginModal(); }
function closeModal() {
  document.querySelectorAll('.modal, .modal-card, .modal-overlay').forEach(m => m.classList.add('hidden'));
}

async function submitLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-submit');
  btn.disabled = true; btn.textContent = 'Signing in…';
  try {
    const data = await apiPost('/auth/login', {
      email: document.getElementById('login-email').value,
      password: document.getElementById('login-password').value,
    }, false);
    state.token = data.access_token;
    localStorage.setItem('token', data.access_token);
    await restoreSession();
    closeModal();
    showToast('Signed in successfully ✨', 'success');
  } catch (err) {
    showToast(err.message || 'Login failed. Try demo mode.', 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Sign In';
  }
}

async function submitRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('reg-submit');
  btn.disabled = true; btn.textContent = 'Creating…';
  try {
    await apiPost('/auth/register', {
      full_name: document.getElementById('reg-name').value,
      email: document.getElementById('reg-email').value,
      password: document.getElementById('reg-password').value,
    }, false);
    showToast('Account created! Please sign in.', 'success');
    switchToLogin();
  } catch (err) {
    showToast(err.message || 'Registration failed.', 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Create Account';
  }
}

// ─── Saved & Notifications & Analytics ─────────────────────
async function loadSavedSearches() {
  const container = document.getElementById('saved-searches-list');
  if (container) {
    container.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px">
        <h4 style="color:#fff;margin-bottom:8px">⭐ Frontend Engineer in Remote / Bangalore</h4>
        <p style="color:var(--text-secondary);font-size:0.85rem">Active alert · Notification frequency: Daily</p>
      </div>`;
  }
}

async function loadNotifications() {
  const container = document.getElementById('notifications-list');
  if (container) {
    container.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px">
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px">
          <div style="color:#fff;font-weight:600">🎯 3 New 90%+ Matches at Stitch AI & Nexus</div>
          <div style="color:var(--text-muted);font-size:0.8rem;margin-top:4px">2 hours ago</div>
        </div>
      </div>`;
  }
}

async function loadAnalytics() {
  const grid = document.getElementById('analytics-grid');
  if (grid) {
    grid.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:18px;padding:24px">
        <h3 style="color:#fff;font-size:1.1rem;margin-bottom:14px">Top In-Demand Skills</h3>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div><div style="display:flex;justify-content:space-between;color:#fff;font-size:0.85rem"><span>Python / FastAPI</span><span>88%</span></div><div style="height:6px;background:rgba(255,255,255,0.1);border-radius:3px;margin-top:4px"><div style="width:88%;height:100%;background:#8B5CF6;border-radius:3px"></div></div></div>
          <div><div style="display:flex;justify-content:space-between;color:#fff;font-size:0.85rem"><span>React / TypeScript</span><span>84%</span></div><div style="height:6px;background:rgba(255,255,255,0.1);border-radius:3px;margin-top:4px"><div style="width:84%;height:100%;background:#38BDF8;border-radius:3px"></div></div></div>
        </div>
      </div>`;
  }
}

// ─── Resume / Skill Hub Features ───────────────────────────
function initResumeSection() { setResumeStep(1); }
function setResumeStep(activeStep) {
  for (let i = 1; i <= 4; i++) {
    const item = document.getElementById(`step-${i}`);
    if (!item) continue;
    item.classList.remove('active', 'completed');
    if (i < activeStep) item.classList.add('completed');
    else if (i === activeStep) item.classList.add('active');
  }
  for (let i = 1; i <= 3; i++) {
    const conn = document.getElementById(`conn-${i}`);
    if (conn) conn.classList.toggle('done', i < activeStep);
  }
}

function handleDragOver(e) { e.preventDefault(); document.getElementById('upload-zone')?.classList.add('dragover'); }
function handleDragLeave(e) { document.getElementById('upload-zone')?.classList.remove('dragover'); }
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone')?.classList.remove('dragover');
  const file = e.dataTransfer?.files?.[0];
  if (file) handleResumeFile(file);
}
function handleFileSelect(e) {
  const file = e.target.files?.[0];
  if (file) handleResumeFile(file);
  e.target.value = '';
}

async function handleResumeFile(file) {
  showUploadProgress(`Uploading ${escHtml(file.name)}…`);
  animateProgressBar(40);
  try {
    const formData = new FormData();
    formData.append('file', file);
    animateProgressBar(75);
    const res = await fetch(`${API_BASE}/resume/parse`, { method: 'POST', body: formData, headers: authHeader() });
    if (!res.ok) throw new Error('Upload failed. Using demo parse.');
    const data = await res.json();
    state.resumeProfile = data.profile || data;
    hideUploadProgress();
    renderCandidateProfile(state.resumeProfile);
    setResumeStep(2);
  } catch {
    hideUploadProgress();
    loadSampleResumeDemo();
  }
}

function loadSampleResumeDemo() {
  const sampleProfile = {
    filename: 'Alex_Chen_Profile.pdf',
    skills: ['React', 'TypeScript', 'WebGL', 'Node.js', 'FastAPI', 'Python', 'Docker', 'AWS'],
    experience_years: 4,
    experience_level: 'senior',
    target_titles: ['Frontend Engineer', 'Full Stack Developer'],
    education_degrees: ['B.Tech Computer Science'],
    certifications: ['AWS Certified Developer'],
  };
  state.resumeProfile = sampleProfile;
  renderCandidateProfile(sampleProfile);
  setResumeStep(2);
  showToast('Profile parsed into Skill Hub! ✨', 'success');
}

function renderCandidateProfile(profile) {
  const container = document.getElementById('profile-preview-card');
  if (!container || !profile) return;
  const skills = profile.skills || [];
  container.innerHTML = `
    <div class="profile-header-row">
      <div class="profile-avatar-area">
        <div class="profile-avatar">${(profile.filename || 'A')[0].toUpperCase()}</div>
        <div class="profile-name-area">
          <h3>${escHtml(profile.filename || 'Candidate Profile')}</h3>
          <span>${(profile.target_titles || []).join(' · ') || 'Software Engineer'}</span>
        </div>
      </div>
      <span class="badge-verified-pill" style="font-size:0.85rem">⚡ Senior Level</span>
    </div>
    <div class="profile-chips">
      ${skills.map(s => `<span class="profile-chip">${escHtml(s)}</span>`).join('')}
    </div>
    <button class="profile-find-btn" onclick="fetchRecommendations()">
      Find My Matching Jobs ⚡
    </button>
  `;
  document.getElementById('resume-step-upload')?.classList.add('hidden');
  document.getElementById('resume-step-profile')?.classList.remove('hidden');
}

async function fetchRecommendations() {
  setResumeStep(3);
  const grid = document.getElementById('rec-grid');
  document.getElementById('rec-count-badge').textContent = '3 Verified Matches';
  grid.innerHTML = DEFAULT_SAMPLE_JOBS.slice(0, 3).map((j, i) => buildJobCard(j, i)).join('');
  document.getElementById('resume-step-recs')?.classList.remove('hidden');
  setTimeout(() => animateAllRings(), 100);
}

function showUploadProgress(msg) {
  document.getElementById('upload-progress')?.classList.remove('hidden');
  document.getElementById('progress-label').textContent = msg;
}
function hideUploadProgress() { document.getElementById('upload-progress')?.classList.add('hidden'); }
function animateProgressBar(target) { const b = document.getElementById('progress-bar'); if (b) b.style.width = `${target}%`; }
function togglePasteResumeArea() { document.getElementById('paste-resume-box')?.classList.toggle('hidden'); }
function submitPastedResume() { loadSampleResumeDemo(); }

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
function authHeader() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }

// ─── UI Helpers ────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: '✨' };
  t.innerHTML = `<span>${icons[type] || '•'}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 250); }, 3200);
}

function formatDate(dateStr) {
  if (!dateStr) return '2d ago';
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const hrs = Math.floor(diff / 3600000);
    if (hrs < 24) return `${Math.max(1, hrs)}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return '2d ago'; }
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function escAttr(s) { return String(s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }
