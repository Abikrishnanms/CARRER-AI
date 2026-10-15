/* ═══════════════════════════════════════════════════════
   TalentLens — Human & Minimal Job Board Logic
   Clean rendering, theme toggle, keyboard nav
═══════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api/v1';

const SUGGESTED_SEARCHES = ['React Developer', 'Python', 'Data Scientist', 'Product Manager', 'DevOps', 'UI/UX Designer'];

// ─── Sample Data ────────────────────────────────────────
const DEFAULT_SAMPLE_JOBS = [
  {
    id: 'sample-1',
    title: 'Senior Frontend Engineer',
    company_name: 'Stitch AI',
    location: 'Remote, IND',
    salary_display: '₹30 – 45 LPA',
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
    salary_display: '₹40 – 55 LPA',
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
    salary_display: '$120k – $150k',
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
    salary_display: '₹28 – 40 LPA',
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
    salary_display: '₹35 – 50 LPA',
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

// ─── App State ──────────────────────────────────────────
function safeGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function safeSet(key, val) { try { localStorage.setItem(key, val); } catch {} }
function safeRemove(key) { try { localStorage.removeItem(key); } catch {} }

const state = {
  token: safeGet('token'),
  user: null,
  currentPage: 1,
  pageSize: 10,
  totalJobs: 0,
  filters: { remote_type: '', experience: '', verified_only: true, salary_min: 0 },
  searchQuery: '',
  searchLocation: '',
  sortBy: 'quality_score',
  currentSection: 'discover',
  autocompleteTimer: null,
  sliderTimer: null,
  savedJobs: JSON.parse(safeGet('saved_jobs') || '[]'),
   resumeProfile: null,
  drawerJob: null,
  unreadNotifications: 3,
};

const DEFAULT_FILTERS = { remote_type: '', experience: '', verified_only: true, salary_min: 0 };

function saveFilters() {
  try {
    const prefs = {
      filters: state.filters,
      searchQuery: state.searchQuery,
      searchLocation: state.searchLocation,
      sortBy: state.sortBy,
    };
    localStorage.setItem('search_prefs', JSON.stringify(prefs));
  } catch {}
}

function loadFilters() {
  const prefs = JSON.parse(safeGet('search_prefs') || '{}');
  if (prefs.filters) state.filters = { ...DEFAULT_FILTERS, ...prefs.filters };
  if (prefs.searchQuery) state.searchQuery = prefs.searchQuery;
  if (prefs.searchLocation) state.searchLocation = prefs.searchLocation;
   if (prefs.sortBy) state.sortBy = prefs.sortBy;
}

function applyFiltersToUI() {
  const verCheck = document.getElementById('filter-verified-checkbox');
  if (verCheck) verCheck.checked = state.filters.verified_only;

  const radioAll = document.querySelector('input[name="work_mode"][value=""]');
  if (radioAll) radioAll.checked = true;
  if (state.filters.remote_type) {
    const radio = document.querySelector(`input[name="work_mode"][value="${state.filters.remote_type}"]`);
    if (radio) radio.checked = true;
  }

  const expActive = document.querySelector('.exp-chip.active');
  if (expActive) expActive.classList.remove('active');
  const expChip = document.querySelector(`.exp-chip[data-exp="${state.filters.experience || ''}"]`);
  if (expChip) expChip.classList.add('active');

   const salarySlider = document.getElementById('salary-range');
   if (salarySlider) salarySlider.value = state.filters.salary_min || 0;
   const salaryLabel = document.getElementById('salary-min-label');
   if (salaryLabel) salaryLabel.textContent = `₹${state.filters.salary_min || 0}L - No minimum`;

  const searchInput = document.getElementById('hero-search');
  if (searchInput) searchInput.value = state.searchQuery || '';
  const locInput = document.getElementById('hero-location');
  if (locInput) locInput.value = state.searchLocation || '';

  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) sortSelect.value = state.sortBy || 'quality_score';
}

// ─── Utilities ──────────────────────────────────────────
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function highlightSearch(text, query) {
  if (!query || !text) return escHtml(text);
  const terms = escHtml(query).toLowerCase().split(/\s+/).filter(t => t.length > 1);
  if (!terms.length) return escHtml(text);
  const escaped = escHtml(text);
  let result = '';
  let remaining = escaped;
  while (remaining) {
    let bestIdx = -1;
    let bestTerm = '';
    for (const term of terms) {
      const idx = remaining.toLowerCase().indexOf(term);
      if (idx !== -1 && (bestIdx === -1 || idx < bestIdx)) {
        bestIdx = idx;
        bestTerm = term;
      }
    }
    if (bestIdx === -1) {
      result += remaining;
      break;
    }
    const endIdx = bestIdx + bestTerm.length;
    result += remaining.slice(0, bestIdx);
    result += `<mark>${remaining.slice(bestIdx, endIdx)}</mark>`;
    remaining = remaining.slice(endIdx);
  }
  return result;
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function escAttr(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escJsonForAttr(obj) {
  return JSON.stringify(obj).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatDate(dateStr) {
  if (!dateStr) return '2d ago';
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const hrs = Math.floor(diff / 3600000);
    if (hrs < 1) return 'Just now';
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return '2d ago'; }
}

function isStaleJob(dateStr) {
  if (!dateStr) return false;
  try {
    return Date.now() - new Date(dateStr).getTime() > 30 * 24 * 3600 * 1000;
  } catch { return false; }
}

function getTrustLabel(score) {
  if (score == null) return { label: null, class: '' };
  if (score >= 90) return { label: 'High Trust', class: 'trust-high' };
  if (score >= 70) return { label: 'Good Trust', class: 'trust-medium' };
  return { label: 'Review', class: 'trust-low' };
}

// ─── Theme ──────────────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'light';
  const next = current === 'light' ? 'dark' : 'light';
  html.setAttribute('data-theme', next);
  safeSet('theme', next);
}

function loadTheme() {
  const saved = safeGet('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setupBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  let ticking = false;
  const onScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        btn.classList.toggle('hidden', window.scrollY < 400);
        ticking = false;
      });
      ticking = true;
    }
  };
  window.addEventListener('scroll', onScroll);
  onScroll();
}

// ─── Init ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
   loadTheme();
  loadFilters();
  applyFiltersToUI();
  setupAutocomplete();
  setupMobileFilters();
   setupKeyboardShortcuts();
   setupBackToTop();
  setupClearSearch();
  const urlParams = new URLSearchParams(window.location.search);
  const jobId = urlParams.get('job');
  if (jobId) {
    loadJobs().then(() => {
      setTimeout(() => openJobDrawer(jobId), 300);
    });
  } else {
    Promise.all([
      loadPlatformStats(),
      loadJobs(),
      state.token ? restoreSession() : Promise.resolve(),
    ]);
  }
});

// ─── Keyboard Shortcuts ─────────────────────────────────
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDrawer();
      closeModal();
      closeMobileNav();
    }
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('hero-search')?.focus();
    }
    // Ctrl/Cmd + Enter to submit search
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const searchInput = document.getElementById('hero-search');
      if (document.activeElement === searchInput || document.activeElement === document.getElementById('hero-location')) {
        e.preventDefault();
        performSearch();
      }
    }
    // Drawer shortcuts (only when drawer is open)
    const drawer = document.getElementById('job-drawer');
    if (!drawer?.classList.contains('hidden') && state.drawerJob) {
      if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        const jobId = state.drawerJob.id || state.drawerJob._id;
        saveJob(jobId);
        showToast(isJobSaved(jobId) ? 'Saved to your jobs' : 'Removed from saved', 'info');
        const btn = document.querySelector('.drawer-actions .btn-ghost');
        if (btn) btn.textContent = isJobSaved(jobId) ? '★ Saved' : '☆ Save';
      }
      if (e.key.toLowerCase() === 'a' && validateApplyUrl(state.drawerJob.apply_url || state.drawerJob.source_url || '#')) {
        e.preventDefault();
        trackApplyClick({ id: state.drawerJob.id, company_name: state.drawerJob.company_name, title: state.drawerJob.title }, state.drawerJob.apply_url || state.drawerJob.source_url);
        window.open(state.drawerJob.apply_url || state.drawerJob.source_url, '_blank', 'noopener,noreferrer');
        closeDrawer();
      }
    }
  });
}

// ─── Global Error Handler ─────────────────────────────────
window.addEventListener('error', (e) => {
  trackError('global_error', { message: e.message, filename: e.filename, lineno: e.lineno });
  showToast('Something went wrong. Please refresh the page.', 'error');
});

window.addEventListener('unhandledrejection', (e) => {
  if (e.reason?.message === 'timeout' || e.reason?.message?.includes('fetch')) return;
  e.preventDefault();
  trackError('unhandled_rejection', e.reason);
  showToast('An unexpected error occurred.', 'error');
});

// ─── Mobile Nav ─────────────────────────────────────────
function toggleMobileNav() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn = document.getElementById('nav-hamburger');
  const isOpen = drawer?.classList.toggle('open');
  btn?.classList.toggle('open', isOpen);
}

function closeMobileNav() {
  document.getElementById('mobile-nav-drawer')?.classList.remove('open');
  document.getElementById('nav-hamburger')?.classList.remove('open');
}

document.addEventListener('click', (e) => {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn = document.getElementById('nav-hamburger');
  if (drawer?.classList.contains('open') && !drawer.contains(e.target) && !btn?.contains(e.target)) {
    closeMobileNav();
  }
});

// ─── Mobile Filter Collapse ────────────────────────────
function setupMobileFilters() {
  const header = document.querySelector('.filters-card-header');
  const body = document.getElementById('filters-body');
  if (!header || !body) return;

  const checkMobile = () => {
    if (window.innerWidth <= 768) {
      body.classList.remove('open');
    } else {
      body.classList.add('open');
    }
  };
  checkMobile();
  window.addEventListener('resize', debounce(checkMobile, 150));

  header.addEventListener('click', () => {
    if (window.innerWidth <= 768) {
      body.classList.toggle('open');
    }
  });
}

// ─── Session & Auth ─────────────────────────────────────
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
  safeRemove('token');
  state.token = null;
  state.user = null;
  document.getElementById('btn-login')?.classList.remove('hidden');
  document.getElementById('user-menu')?.classList.add('hidden');
  if (!silent) {
    showToast('Signed out', 'info');
    showSection('discover');
  }
}

// ─── Stats ──────────────────────────────────────────────
async function loadPlatformStats() {
  try {
    const data = await apiGet('/analytics/overview');
    animateCounter('stat-jobs', data.total_jobs || 4200);
    animateCounter('stat-companies', data.total_companies || 1100);
    const ver = data.platform_trust_rate ? `${data.platform_trust_rate}%` : '99.4%';
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
  const duration = 1000;
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

// ─── Section Navigation ─────────────────────────────────
function showSection(name) {
  const sections = ['discover', 'resume', 'analytics', 'saved', 'notifications'];
  const navMap = { resume: 'skillhub', saved: 'applications', analytics: 'network' };

  sections.forEach(s => {
    document.getElementById(`section-${s}`)?.classList.add('hidden');
    const navId = navMap[s] || s;
    document.getElementById(`nav-${navId}`)?.classList.remove('active');
  });

  const activeNavId = `nav-${navMap[name] || name}`;
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

function setSuggestionSearch(query) {
  const input = document.getElementById('hero-search');
  if (input) input.value = query;
  state.searchQuery = query;
  performSearch();
}

function setupClearSearch() {
  const input = document.getElementById('hero-search');
  const btn = document.getElementById('clear-search');
  if (!input || !btn) return;
  const toggle = () => btn.classList.toggle('hidden', !input.value.trim());
  input.addEventListener('input', toggle);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      input.value = '';
      btn.classList.add('hidden');
      document.getElementById('autocomplete')?.classList.add('hidden');
    }
  });
}

function clearSearch() {
  const input = document.getElementById('hero-search');
  const btn = document.getElementById('clear-search');
  if (input) input.value = '';
  if (btn) btn.classList.add('hidden');
  document.getElementById('autocomplete')?.classList.add('hidden');
  state.searchQuery = '';
}

function copyJobLink(jobId) {
  const url = window.location.origin + window.location.pathname + '?job=' + encodeURIComponent(jobId || '');
  navigator.clipboard.writeText(url).then(() => {
    showToast('Link copied to clipboard', 'info');
    trackEvent('copy_link', { job_id: jobId });
  }).catch(() => {
    showToast('Failed to copy link', 'error');
  });
}

// ─── Search ─────────────────────────────────────────────
function performSearch() {
  state.searchQuery = document.getElementById('hero-search')?.value.trim() || '';
   state.searchLocation = document.getElementById('hero-location')?.value.trim() || '';
   state.currentPage = 1;
  saveFilters();
  trackSearch(state.searchQuery, {
    location: state.searchLocation,
    ...state.filters,
    sort_by: state.sortBy,
  });
  showSection('discover');
  const btn = document.getElementById('btn-search');
  if (btn) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.innerHTML = '<span class="spinner"></span> Searching...';
  }
  loadJobs().finally(() => {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Search';
    }
  });
}

function setupAutocomplete() {
  const input = document.getElementById('hero-search');
  if (!input) return;

  const debouncedFetch = debounce((q) => fetchAutocomplete(q), 250);

  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (q.length < 2) {
      document.getElementById('autocomplete')?.classList.add('hidden');
      return;
    }
    debouncedFetch(q);
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') performSearch();
  });
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

// ─── Filters ────────────────────────────────────────────
function toggleVerifiedFilter(checked) {
  state.filters.verified_only = checked;
  state.currentPage = 1;
  saveFilters();
  loadJobs();
}

function setWorkModeFilter(val) {
  state.filters.remote_type = val;
  state.currentPage = 1;
  saveFilters();
  loadJobs();
}

function setExperienceChip(btn, val) {
  document.querySelectorAll('.exp-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.filters.experience = val;
  state.currentPage = 1;
  saveFilters();
  loadJobs();
}

function onSalarySlider(val) {
  const v = parseInt(val);
  state.filters.salary_min = v;
  document.getElementById('salary-min-label').textContent = `₹${v}L`;
  clearTimeout(state.sliderTimer);
  state.sliderTimer = setTimeout(() => { state.currentPage = 1; saveFilters(); loadJobs(); }, 400);
}

function clearFilters() {
  state.filters = { remote_type: '', experience: '', verified_only: true, salary_min: 0 };
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
  saveFilters();
  loadJobs();
}

function onSortChange() {
  state.sortBy = document.getElementById('sort-select')?.value || 'quality_score';
  state.currentPage = 1;
  saveFilters();
  loadJobs();
}

function loadMoreJobs() {
  state.currentPage += 1;
  loadJobs(true);
}

// ─── Results Status ──────────────────────────────────────
function showResultsStatus(msg) {
  const el = document.getElementById('results-status');
  const text = document.getElementById('results-status-text');
  if (el && text) {
    text.textContent = msg;
    el.classList.remove('hidden');
    const refresh = document.getElementById('results-refresh');
    if (refresh) refresh.classList.remove('hidden');
  }
}

function updateResultsStatus(total, shown) {
  showResultsStatus(`Showing ${shown} of ${total} jobs`);
}

function hideResultsStatus() {
  document.getElementById('results-status')?.classList.add('hidden');
  document.getElementById('results-refresh')?.classList.add('hidden');
}

function refreshResults() {
  const refresh = document.getElementById('results-refresh');
  if (refresh) {
    refresh.style.transform = 'rotate(90deg)';
    setTimeout(() => refresh.style.transform = '', 500);
  }
  state.currentPage = 1;
  loadJobs();
}

// ─── Jobs Loader ────────────────────────────────────────
async function loadJobs(append = false) {
  if (!append) {
    document.getElementById('jobs-grid').innerHTML =
      Array(4).fill('<div class="job-skeleton"></div>').join('');
    document.getElementById('empty-state')?.classList.add('hidden');
    document.getElementById('load-more-wrap')?.classList.add('hidden');
  }
  showResultsStatus('Searching…');

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
  if (state.filters.verified_only) params.set('verified_only', 'true');
   if (state.filters.salary_min > 0) params.set('salary_min', state.filters.salary_min * 100000);

  try {
    const data = await apiGet(`/jobs?${params}`);
    const results = data.results || [];
    state.totalJobs = data.total || 0;

    if (!results.length && state.currentPage === 1) {
      renderJobs(filterSampleJobs(), append);
      updateResultsStatus(state.totalJobs, state.pageSize * (state.currentPage - 1) + (filterSampleJobs().length));
    } else {
      renderJobs(results, append);
      updateResultsStatus(data.total, state.pageSize * (state.currentPage - 1) + results.length);
    }
  } catch (err) {
    trackError('loadJobs', err);
    hideResultsStatus();
    if (!append) {
      const isTimeout = err.message === 'timeout';
      document.getElementById('jobs-grid').innerHTML = `
        <div class="error-state" style="grid-column:1/-1">
          <div class="error-icon">⚠️</div>
          <h3>Couldn't load jobs</h3>
          <p>${isTimeout ? 'Request timed out. ' : 'Failed to load jobs. '}<a href="#" onclick="loadJobs()">Retry</a></p>
        </div>
      `;
      document.getElementById('empty-state')?.classList.add('hidden');
    } else {
      showToast('Failed to load more jobs. Please try again.', 'error');
    }
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
    hideResultsStatus();
    const emptyTitle = document.getElementById('empty-state-title');
    const emptyDesc = document.getElementById('empty-state-desc');
    const suggestions = document.getElementById('empty-state-suggestions');
    if (emptyTitle) emptyTitle.textContent = state.searchQuery
      ? `No results for "${state.searchQuery}"`
      : 'No matching jobs found';
    if (emptyDesc) emptyDesc.textContent = state.searchQuery
      ? 'Try a different keyword or adjust your filters.'
      : 'Try broadening your search or clearing filters.';
    if (suggestions) suggestions.innerHTML = state.searchQuery
      ? SUGGESTED_SEARCHES.map(s => `<button class="suggestion-chip" onclick="setSuggestionSearch('${escAttr(s)}')">${escHtml(s)}</button>`).join('')
      : '';
    document.getElementById('empty-state')?.classList.remove('hidden');
    document.getElementById('load-more-wrap')?.classList.add('hidden');
    return;
  }
  document.getElementById('empty-state')?.classList.add('hidden');
  const hasMore = state.totalJobs > state.pageSize * state.currentPage;
  if (hasMore) {
    document.getElementById('load-more-wrap')?.classList.remove('hidden');
  } else {
    document.getElementById('load-more-wrap')?.classList.add('hidden');
    showToast('All matching jobs loaded', 'info');
  }

  const html = jobs.map((job, i) => buildJobCard(job, i)).join('');
  if (append) {
    grid.insertAdjacentHTML('beforeend', html);
  } else {
    grid.innerHTML = html;
  }
}

function buildJobCard(job, i, match) {
  const matchPct = (match && typeof match.match_percentage === 'number')
    ? match.match_percentage
    : (job.match_percentage || Math.round(job.quality_score || (Math.random() * 20 + 75)));
  const logoChar = (job.company_name || 'T')[0].toUpperCase();
  const isVanguard = (job.company_name || '').toLowerCase().includes('vanguard');
  const isNexus = (job.company_name || '').toLowerCase().includes('nexus');
  const logoClass = isVanguard ? 'logo-vanguard' : isNexus ? 'logo-nexus' : '';
  const isFeatured = job.featured;

  const skills = (job.required_skills || ['React', 'TypeScript']).slice(0, 3);
  const salary = job.salary_display || (job.salary_max ? `₹${Math.round(job.salary_max / 100000)} LPA` : 'Competitive');
  const loc = job.location || (job.remote_type === 'remote' ? 'Remote' : 'Hybrid');
  const posted = formatDate(job.posted_at);
  const stale = isStaleJob(job.posted_at);
  const trustInfo = getTrustLabel(job.trust_score);
  const targetUrl = job.apply_url || job.source_url || '#';
  const validUrl = validateApplyUrl(targetUrl);
  const jobIdStr = job.id || job._id || '';
  const saved = isJobSaved(jobIdStr);
  const jobJson = escJsonForAttr({ id: job.id, company_name: job.company_name, title: job.title });
  const cardOnClick = validUrl
    ? "trackCardClick(" + jobJson + "); trackApplyClick(" + jobJson + ", '" + escAttr(targetUrl) + "'); window.open('" + escAttr(targetUrl) + "', '_blank', 'noopener,noreferrer')"
    : "trackCardClick(" + jobJson + "); showToast('Application link not available for this job', 'error')";

  return `
  <div class="job-card${isFeatured ? ' featured' : ''}"
        onclick="${cardOnClick}"
       style="animation: fadeInUp 0.3s ${i * 0.04}s both var(--ease-out)">

    <div class="job-card-top-row">
      <div class="card-logo-box ${logoClass}">${logoChar}</div>
      <div class="card-title-col">
         <div class="card-job-title" title="${escHtml(job.title)}">${highlightSearch(job.title, state.searchQuery)}</div>
         <div class="card-company-line">
           <span>${highlightSearch(job.company_name, state.searchQuery)}</span>
          ${job.is_verified !== false ? '<span class="badge-verified-pill">Verified</span>' : ''}
           ${stale ? '<span class="badge-stale-pill">Stale</span>' : ''}
           ${trustInfo.label ? `<span class="badge-trust-pill ${trustInfo.class}">${trustInfo.label}</span>` : ''}
        </div>
      </div>
    </div>

    <div class="card-meta-details">
      <span class="meta-detail-item">${escHtml(loc)}</span>
      <span class="meta-detail-item">${escHtml(salary)}</span>
      <span class="meta-detail-item ${stale ? 'stale' : ''}">${posted}${stale ? ' (stale)' : ''}</span>
    </div>

    <div class="card-skills-row">
      ${skills.map(s => `<span class="card-skill-tag">${escHtml(s)}</span>`).join('')}
    </div>

    <div class="card-footer-row">
      <span class="card-match-pct">${matchPct}%</span>
      <button class="card-save-btn ${saved ? 'saved' : ''}"
              onclick="event.stopPropagation(); toggleSaveCard('"${jobIdStr}'", this); trackBookmark({id: '" + jobIdStr + "'})"
              title="${saved ? 'Remove from saved' : 'Save job'}"
              aria-label="${saved ? 'Remove from saved' : 'Save job'}">
        ${saved ? '★' : '☆'}
      </button>
    </div>
  </div>`;
}

// ─── Job Detail Drawer ──────────────────────────────────
async function openJobDrawer(jobId) {
  document.getElementById('drawer-overlay')?.classList.remove('hidden');
  const drawer = document.getElementById('job-drawer');
  drawer?.classList.remove('hidden');
  document.getElementById('drawer-content').innerHTML = '<div class="loading-spinner centered"></div>';
  document.body.style.overflow = 'hidden';

  let job = null;
  try {
    if (jobId.startsWith('sample-')) {
      job = DEFAULT_SAMPLE_JOBS.find(j => j.id === jobId);
    } else {
      job = await apiGet(`/jobs/${jobId}`);
    }
    renderDrawer(job || DEFAULT_SAMPLE_JOBS[0]);
    state.drawerJob = job || DEFAULT_SAMPLE_JOBS[0];
  } catch (err) {
    trackError('openJobDrawer', err);
    const isTimeout = err.message === 'timeout';
    document.getElementById('drawer-content').innerHTML = `
      <div style="padding:var(--space-lg);text-align:center">
        <div style="font-size:2rem;margin-bottom:var(--space-md)">⚠️</div>
        <h3 style="margin-bottom:var(--space-sm)">Couldn't load job details</h3>
        <p style="color:var(--text-secondary);margin-bottom:var(--space-lg)">
          ${isTimeout ? 'Request timed out. ' : 'Failed to load. '}
        </p>
        <button class="btn btn-primary" onclick="retryOpenDrawer('${jobId}')">Retry</button>
        <button class="btn btn-ghost" onclick="closeDrawer()" style="margin-left:8px">Close</button>
      </div>
    `;
  }
}

function retryOpenDrawer(jobId) {
  openJobDrawer(jobId);
}

function closeDrawer() {
  document.getElementById('job-drawer')?.classList.add('hidden');
  document.getElementById('drawer-overlay')?.classList.add('hidden');
  document.body.style.overflow = '';
  state.drawerJob = null;
}

function renderTrustSection(job) {
  const trustScore = job.trust_score || job.company?.trust_score;
  const trustInfo = getTrustLabel(trustScore);
  const warningSignals = job.warning_signals || [];
  const trustReasons = job.trust_reasons || [];
  const isUrlReachable = job.is_url_reachable !== false;
  const scamRisk = job.scam_risk || job.scam_probability;

  if (!trustScore && !warningSignals.length && !trustReasons.length && !scamRisk) return '';

  const trustPct = Math.round(trustScore || 0);
  const trustColor = trustInfo.class === 'trust-high' ? 'var(--green)'
    : trustInfo.class === 'trust-medium' ? 'var(--amber)'
    : trustScore ? 'var(--red)' : 'var(--text-muted)';
  const isStale = isStaleJob(job.posted_at);

  let riskClass = 'trust-medium';
  let riskLabel = 'Unknown';
  if (typeof scamRisk === 'string') {
    if (scamRisk === 'very_low' || scamRisk === 'low') { riskClass = 'trust-high'; riskLabel = 'Low Risk'; }
    else if (scamRisk === 'high' || scamRisk === 'very_high') { riskClass = 'trust-low'; riskLabel = 'High Risk'; }
    else { riskClass = 'trust-medium'; riskLabel = 'Medium Risk'; }
  } else if (typeof scamRisk === 'number') {
    riskLabel = `${Math.round(scamRisk * 100)}%`;
    riskClass = scamRisk > 0.7 ? 'trust-low' : scamRisk > 0.4 ? 'trust-medium' : 'trust-high';
  }

  return `
  <div class="drawer-section">
    <h4>Trust & Safety</h4>

    ${trustScore != null ? `
    <div class="trust-score-bar">
      <div class="trust-score-header">
        <span class="trust-score-label">${trustPct}% Trust Score</span>
        <span class="badge-trust-pill ${trustInfo.class}">${trustInfo.label || 'Review'}</span>
      </div>
      <div class="trust-score-track">
        <div class="trust-score-fill" style="width:${trustPct}%;background:${trustColor}"></div>
      </div>
    </div>
    ` : ''}

    ${scamRisk ? `
    <div class="trust-score-bar" style="margin-top:8px">
      <div class="trust-score-header">
        <span class="trust-score-label">Scam Risk</span>
        <span class="badge-trust-pill ${riskClass}">${riskLabel}</span>
      </div>
    </div>
    ` : ''}

    ${!isUrlReachable ? `
    <div class="trust-warning-block">
      <span class="trust-warning-icon">⚠️</span>
      <span>Application link status could not be verified</span>
    </div>` : ''}

    ${isStale ? `
    <div class="trust-warning-block">
      <span class="trust-warning-icon">⚠️</span>
      <span>This job was posted more than 30 days ago. The listing may be expired.</span>
    </div>` : ''}

    ${warningSignals.length ? `
    <div class="trust-warnings-list">
      <div class="trust-warnings-title">Warning signals</div>
      ${warningSignals.map(s => `<div class="trust-warning-item">• ${escHtml(s)}</div>`).join('')}
    </div>` : ''}

    ${trustReasons.length ? `
    <div class="trust-reasons-list">
      <div class="trust-reasons-title">Verified details</div>
      ${trustReasons.map(r => `<div class="trust-reason-item">✓ ${escHtml(r)}</div>`).join('')}
    </div>` : ''}
  </div>`;
}

function renderDrawer(job) {
  const skills = (job.required_skills || job.skills?.required || []).map(s =>
    `<span class="card-skill-tag">${escHtml(s)}</span>`
  ).join('');
  const applyUrl = job.apply_url || job.source_url || '#';
  const companyName = job.company_name || job.company?.name || 'Company';
  const location = job.location?.display || job.location || (typeof job.location === 'string' ? job.location : 'Remote');
  const salaryDisplay = job.salary_display || job.salary?.display || 'Competitive';
  const remoteType = job.remote_type || 'Remote';
  const description = job.description || 'Join an engineering team working on scalable, high-impact products.';
  const stale = isStaleJob(job.posted_at);
  const drawerJobJson = escJsonForAttr({ id: job.id, company_name: companyName, title: job.title });
  const drawerApplyOnClick = validateApplyUrl(applyUrl)
    ? "trackApplyClick(" + drawerJobJson + ", '" + escAttr(applyUrl) + "'); window.open('" + escAttr(applyUrl) + "', '_blank', 'noopener,noreferrer'); closeDrawer()"
    : "trackApplyClick(" + drawerJobJson + ", '" + escAttr(applyUrl) + "'); showToast('Application link not available for this job', 'error')";

  document.getElementById('drawer-content').innerHTML = `
  <button class="drawer-close-btn" onclick="closeDrawer()">✕</button>

  <div class="drawer-header">
    <div class="drawer-logo">${(companyName || 'T')[0].toUpperCase()}</div>
    <div>
      <div class="drawer-title">${escHtml(job.title)}</div>
      <div class="drawer-company">${escHtml(companyName)} · ${escHtml(location)}</div>
    </div>
  </div>

   <div class="drawer-actions">
      <button class="btn btn-primary" style="flex:1;justify-content:center"
         onclick="${drawerApplyOnClick}"
         aria-label="Apply on company site">
        Apply on Company Site
      </button>
     <button class="btn btn-ghost" onclick="event.stopPropagation(); toggleSaveCard('" + (job.id || job._id) + "', this); trackBookmark({id: '" + (job.id || job._id) + "', company_name: '" + escHtml(companyName) + "'}); showToast(isJobSaved('" + (job.id || job._id) + "') ? 'Saved to your jobs' : 'Removed from saved', 'info')" title="Bookmark this job" aria-label="Save this job">
       ☆ Save
     </button>
     <button class="btn btn-ghost" onclick="copyJobLink('${job.id || job._id}')" title="Copy shareable link" aria-label="Copy link to this job">
       ↗
     </button>
   </div>

  <div class="drawer-meta-grid">
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Salary</div>
      <div class="drawer-meta-value">${escHtml(salaryDisplay)}</div>
    </div>
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Status</div>
       <div class="drawer-meta-value" style="color:${job.is_verified !== false ? 'var(--green-text)' : 'var(--text-secondary)'}">
         ${job.is_verified !== false ? 'Verified' : 'Pending Verification'}
       </div>
    </div>
    <div class="drawer-meta-item">
      <div class="drawer-meta-label">Work Mode</div>
      <div class="drawer-meta-value">${escHtml(remoteType)}</div>
    </div>
    ${job.trust_score != null ? `<div class="drawer-meta-item">
      <div class="drawer-meta-label">Trust Score</div>
      <div class="drawer-meta-value">${Math.round(job.trust_score)}%</div>
    </div>` : ''}
    ${stale ? `<div class="drawer-meta-item">
      <div class="drawer-meta-label">Age</div>
      <div class="drawer-meta-value" style="color:var(--amber-text)">Stale Posting</div>
    </div>` : ''}
  </div>

  <div class="drawer-section">
    <h4>Skills</h4>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${skills}</div>
  </div>

  <div class="drawer-section">
    <h4>About the Role</h4>
    <div class="drawer-description">${escHtml(description)}</div>
  </div>

  ${renderTrustSection(job)}
  `;
}

// ─── Auth Modals ────────────────────────────────────────
function openLoginModal() {
  closeModal();
  document.getElementById('modal-overlay')?.classList.remove('hidden');
  document.getElementById('modal-login')?.classList.remove('hidden');
}
function openRegisterModal() {
  closeModal();
  document.getElementById('modal-overlay')?.classList.remove('hidden');
  document.getElementById('modal-register')?.classList.remove('hidden');
}
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
    safeSet('token', data.access_token);
    await restoreSession();
    closeModal();
    showToast('Signed in', 'success');
  } catch (err) {
    showToast(err.message || 'Login failed', 'error');
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
    showToast('Account created — please sign in', 'success');
    switchToLogin();
  } catch (err) {
    showToast(err.message || 'Registration failed', 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Create Account';
  }
}

// ─── Saved & Notifications & Analytics ──────────────────
async function loadSavedSearches() {
  const container = document.getElementById('saved-searches-list');
  if (!container) return;
  
  const savedIds = state.savedJobs;
  const countLabel = document.getElementById('saved-jobs-count');
  const clearBtn = document.getElementById('clear-saved-btn');
  if (countLabel) countLabel.textContent = `${savedIds.length} job${savedIds.length === 1 ? '' : 's'} saved`;
  if (clearBtn) clearBtn.classList.toggle('hidden', !savedIds.length);

  if (!savedIds.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <h3>No saved jobs yet</h3>
        <p>Browse jobs and click the ★ button on any card to save it for later.</p>
      </div>`;
    return;
  }

  try {
    const results = await Promise.all(
      savedIds.map(async (id) => {
        try {
          if (id.startsWith('sample-')) {
            return DEFAULT_SAMPLE_JOBS.find(j => j.id === id);
          }
          return await apiGet(`/jobs/${id}`);
        } catch {
          return null;
        }
      })
    );
    const jobs = results.filter(Boolean);
    
    if (!jobs.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h3>No saved jobs yet</h3>
          <p>Browse jobs and click the ★ button on any card to save it for later.</p>
        </div>`;
      return;
    }

    container.innerHTML = jobs.map(job => `
      <div class="saved-job-row">
        <div class="saved-job-main" onclick="openJobDrawer('${job.id || job._id}')">
          <div class="saved-job-title">${highlightSearch(job.title, state.searchQuery)}</div>
          <div class="saved-job-company">${escHtml(job.company_name)}</div>
          <div class="saved-job-meta">${escHtml(job.location || 'Remote')} · ${escHtml(formatDate(job.posted_at))}</div>
        </div>
        <button class="btn btn-ghost btn-small" onclick="event.stopPropagation(); toggleSaveCard('${job.id || job._id}', null); loadSavedSearches()" aria-label="Remove from saved">
          ✕
        </button>
      </div>
    `).join('');
  } catch (err) {
    trackError('loadSavedSearches', err);
    container.innerHTML = `
      <div class="error-state">
        <div class="error-icon">⚠️</div>
        <h3>Couldn't load saved jobs</h3>
        <p>${err.message === 'timeout' ? 'Request timed out. ' : ''}Failed to load. <a href="#" onclick="loadSavedSearches()">Retry</a></p>
      </div>`;
  }
}

async function loadNotifications() {
  const container = document.getElementById('notifications-list');
  if (!container) return;
  try {
    const notifs = [
      { text: '3 new 90%+ matches at Stitch AI & Nexus', time: '2 hours ago', unread: true },
    ];
    state.unreadNotifications = notifs.filter(n => n.unread).length;
    updateNotificationBadge(state.unreadNotifications);
    if (!notifs.length) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><h3>No notifications yet</h3><p>We will let you know when new jobs match your criteria.</p></div>';
      return;
    }
    container.innerHTML = notifs.map(n => `
      <div class="notification-row ${n.unread ? 'unread' : ''}">
        <div class="notif-text">${escHtml(n.text)}</div>
        <div class="notif-time">${escHtml(n.time)}</div>
      </div>
    `).join('');
  } catch (err) {
    trackError('loadNotifications', err);
    container.innerHTML = '<div class="error-state"><div class="error-icon">⚠️</div><h3>Failed to load notifications</h3><p><a href="#" onclick="loadNotifications()">Retry</a></p></div>';
  }
}

function updateNotificationBadge(count) {
  const dot = document.getElementById('notif-dot');
  const badge = document.getElementById('notif-badge');
  if (dot) dot.classList.toggle('hidden', count === 0);
  if (badge) {
    badge.textContent = String(count);
    badge.classList.toggle('hidden', count === 0);
  }
}

function markAllRead() {
  state.unreadNotifications = 0;
  updateNotificationBadge(0);
  const rows = document.querySelectorAll('.notification-row.unread');
  rows.forEach(row => row.classList.remove('unread'));
  showToast('All notifications marked as read', 'info');
}

function clearAllSavedJobs() {
  if (!confirm('Remove all saved jobs?')) return;
  state.savedJobs = [];
  safeSet('saved_jobs', '[]');
  const btn = document.getElementById('clear-saved-btn');
  if (btn) btn.classList.add('hidden');
  showToast('All saved jobs removed', 'info');
  loadSavedSearches();
}

function markAllRead() {
  showToast('All notifications marked as read', 'info');
}

async function loadAnalytics() {
  const grid = document.getElementById('analytics-grid');
  if (grid) {
    grid.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-lg)">
        <h3 style="color:var(--text-primary);font-size:1rem;margin-bottom:var(--space-md)">Top In-Demand Skills</h3>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div>
            <div style="display:flex;justify-content:space-between;color:var(--text-primary);font-size:0.82rem"><span>Python / FastAPI</span><span>88%</span></div>
            <div style="height:4px;background:var(--bg-inset);border-radius:2px;margin-top:4px"><div style="width:88%;height:100%;background:var(--accent);border-radius:2px"></div></div>
          </div>
          <div>
            <div style="display:flex;justify-content:space-between;color:var(--text-primary);font-size:0.82rem"><span>React / TypeScript</span><span>84%</span></div>
            <div style="height:4px;background:var(--bg-inset);border-radius:2px;margin-top:4px"><div style="width:84%;height:100%;background:var(--green);border-radius:2px"></div></div>
          </div>
          <div>
            <div style="display:flex;justify-content:space-between;color:var(--text-primary);font-size:0.82rem"><span>AWS / Kubernetes</span><span>76%</span></div>
            <div style="height:4px;background:var(--bg-inset);border-radius:2px;margin-top:4px"><div style="width:76%;height:100%;background:var(--amber);border-radius:2px"></div></div>
          </div>
        </div>
      </div>
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-lg)">
        <h3 style="color:var(--text-primary);font-size:1rem;margin-bottom:var(--space-md)">Salary Ranges</h3>
        <div style="display:flex;flex-direction:column;gap:8px;font-size:0.85rem;color:var(--text-secondary)">
          <div style="display:flex;justify-content:space-between"><span>Entry Level</span><span style="color:var(--text-primary);font-weight:600">₹8–15 LPA</span></div>
          <div style="display:flex;justify-content:space-between"><span>Mid Level</span><span style="color:var(--text-primary);font-weight:600">₹15–30 LPA</span></div>
          <div style="display:flex;justify-content:space-between"><span>Senior</span><span style="color:var(--text-primary);font-weight:600">₹30–55 LPA</span></div>
          <div style="display:flex;justify-content:space-between"><span>Lead / Staff</span><span style="color:var(--text-primary);font-weight:600">₹50–80 LPA</span></div>
        </div>
      </div>`;
  }
}

// ─── Resume / Skill Hub ─────────────────────────────────
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
function handleDragLeave() { document.getElementById('upload-zone')?.classList.remove('dragover'); }
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
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed');
    }
    const data = await res.json();
    state.resumeProfile = data.profile || data;
    animateProgressBar(100);
    hideUploadProgress();
    renderCandidateProfile(state.resumeProfile);
    setResumeStep(2);
    showToast('Resume parsed successfully', 'success');
  } catch (err) {
    hideUploadProgress();
    showToast(err.message || 'Failed to parse resume', 'error');
    console.error('Resume parse error:', err);
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
  showToast('Demo profile loaded', 'success');
}

function renderCandidateProfile(profile) {
  const container = document.getElementById('profile-preview-card');
  if (!container || !profile) return;
  const skills = profile.skills || [];
  const levelRaw = profile.experience_level || 'entry';
  const levelLabel = ({
    entry: 'Entry Level', junior: 'Junior Level', mid: 'Mid Level',
    senior: 'Senior Level', lead: 'Lead / Staff', principal: 'Principal',
  })[levelRaw] || (levelRaw.charAt(0).toUpperCase() + levelRaw.slice(1) + ' Level');
  const years = profile.experience_years;
  const yearsText = (years && years > 0) ? `${years} yr · ${levelLabel}` : levelLabel;
  container.innerHTML = `
    <div class="profile-header-row">
      <div class="profile-avatar-area">
        <div class="profile-avatar">${(profile.filename || 'A')[0].toUpperCase()}</div>
        <div class="profile-name-area">
          <h3>${escHtml(profile.filename || 'Candidate Profile')}</h3>
          <span>${(profile.target_titles || []).join(' · ') || 'Software Engineer'}</span>
        </div>
      </div>
      <span class="badge-verified-pill" style="font-size:0.8rem">${escHtml(yearsText)}</span>
    </div>
    <div class="profile-chips">
      ${skills.map(s => `<span class="profile-chip">${escHtml(s)}</span>`).join('')}
    </div>
    <button class="profile-find-btn" onclick="fetchRecommendations()">
      Find Matching Jobs
    </button>
  `;
  document.getElementById('resume-step-upload')?.classList.add('hidden');
  document.getElementById('resume-step-profile')?.classList.remove('hidden');
  document.getElementById('resume-step-recs')?.classList.add('hidden');
  document.getElementById('resume-step-gap')?.classList.add('hidden');
}

async function fetchRecommendations() {
  if (!state.resumeProfile) {
    showToast('Please upload or paste a resume first', 'error');
    return;
  }
  setResumeStep(3);
  const grid = document.getElementById('rec-grid');
  const badge = document.getElementById('rec-count-badge');
  grid.innerHTML = '<div class="job-skeleton"></div>'.repeat(4);
  badge.textContent = 'Matching…';
  document.getElementById('resume-step-recs')?.classList.remove('hidden');
  document.getElementById('resume-step-gap')?.classList.add('hidden');

  try {
    const data = await apiPost('/resume/recommendations', { profile: state.resumeProfile }, false);
    const recs = data.recommendations || [];
    state.lastSkillGap = data.skill_gap_analysis || null;
    badge.textContent = `${data.total_recommendations || recs.length} matches`;
    if (!recs.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:24px;text-align:center;color:var(--text-secondary)">No matching jobs yet — try expanding your skill set or work mode.</div>`;
      return;
    }
    grid.innerHTML = recs.map((r, i) => buildJobCard(r.job, i, r.match)).join('');
    renderSkillGap(data.skill_gap_analysis);
    setResumeStep(4);
  } catch (err) {
    trackError('fetchRecommendations', err);
    const isTimeout = err.message === 'timeout';
    grid.innerHTML = `
      <div class="error-state" style="grid-column:1/-1">
        <div class="error-icon">⚠️</div>
        <h3>Couldn't fetch recommendations</h3>
        <p>${isTimeout ? 'Request timed out. ' : 'Failed to fetch recommendations. '}<a href="#" onclick="fetchRecommendations()">Retry</a></p>
      </div>
    `;
    badge.textContent = '0 matches';
    showToast(err.message || 'Failed to fetch recommendations', 'error');
    console.error('Resume recommendations error:', err);
  }
}

function renderSkillGap(gap) {
  const panel = document.getElementById('skill-gap-panel');
  const wrap = document.getElementById('resume-step-gap');
  if (!panel || !wrap || !gap) return;
  const missing = (gap.missing_high_demand_skills || []).map(s =>
    `<span class="profile-chip" style="border-color:var(--amber);color:var(--amber-text)">${escHtml(s.skill)} <small>${s.demand_pct || 0}%</small></span>`
  ).join('');
  const strengths = (gap.top_strength_categories || []).map(c =>
    `<li><strong>${escHtml(c.category)}</strong> — ${(c.skills || []).map(escHtml).join(', ')}</li>`
  ).join('');
  const learning = (gap.recommended_learning_path || []).map(step =>
    `<li>Learn <strong>${escHtml(step)}</strong></li>`
  ).join('');
  panel.innerHTML = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-lg)">
      <h3 style="color:var(--text-primary);font-size:1rem;margin-bottom:var(--space-md)">Top Skills to Learn Next</h3>
      <div style="display:flex;flex-wrap:wrap;gap:8px">${missing || '<span style="color:var(--text-muted)">No gaps detected — great match!</span>'}</div>
    </div>
    ${strengths ? `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-lg);margin-top:var(--space-md)">
      <h3 style="color:var(--text-primary);font-size:1rem;margin-bottom:var(--space-md)">Your Strength Areas</h3>
      <ul style="margin:0;padding-left:18px;color:var(--text-secondary);font-size:0.9rem">${strengths}</ul>
    </div>` : ''}
    ${learning ? `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-lg);margin-top:var(--space-md)">
      <h3 style="color:var(--text-primary);font-size:1rem;margin-bottom:var(--space-md)">Suggested Learning Path</h3>
      <ol style="margin:0;padding-left:18px;color:var(--text-secondary);font-size:0.9rem">${learning}</ol>
    </div>` : ''}
  `;
  wrap.classList.remove('hidden');
}

function showUploadProgress(msg) {
  document.getElementById('upload-progress')?.classList.remove('hidden');
  document.getElementById('progress-label').textContent = msg;
}
function hideUploadProgress() { document.getElementById('upload-progress')?.classList.add('hidden'); }
function animateProgressBar(target) {
  const b = document.getElementById('progress-bar');
  if (b) b.style.width = `${target}%`;
}
function togglePasteResumeArea() { document.getElementById('paste-resume-box')?.classList.toggle('hidden'); }

async function submitPastedResume() {
  const text = document.getElementById('paste-resume-text')?.value?.trim() || '';
  if (text.length < 20) {
    showToast('Please paste at least 20 characters of resume text', 'error');
    return;
  }
  showUploadProgress('Analyzing pasted text…');
  animateProgressBar(50);
  try {
    const data = await apiPost('/resume/parse-text', { text, filename: 'Pasted Resume.txt' }, false);
    state.resumeProfile = data.profile || data;
    hideUploadProgress();
    animateProgressBar(100);
    renderCandidateProfile(state.resumeProfile);
    setResumeStep(2);
    showToast('Resume parsed successfully', 'success');
  } catch (err) {
    hideUploadProgress();
    showToast(err.message || 'Failed to parse resume', 'error');
  }
}

// ─── API Helpers ────────────────────────────────────────
function withTimeout(promise, ms = 10000) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('timeout')), ms)
    ),
  ]);
}

function validateApplyUrl(url) {
  return url && url !== '#' && /^https?:\/\//i.test(url);
}

const circuitBreaker = {
  failures: {},
  cooldownUntil: {},
};

function getRouteKey(path) {
  return path.split('?')[0].replace(/\/\d+/g, '/:id');
}

function isCircuitOpen(path) {
  const key = getRouteKey(path);
  const until = circuitBreaker.cooldownUntil[key];
  return until && Date.now() < until;
}

function recordFailure(path) {
  const key = getRouteKey(path);
  circuitBreaker.failures[key] = (circuitBreaker.failures[key] || 0) + 1;
  if (circuitBreaker.failures[key] >= 3) {
    circuitBreaker.cooldownUntil[key] = Date.now() + 30000;
  }
}

function recordSuccess(path) {
  const key = getRouteKey(path);
  circuitBreaker.failures[key] = 0;
  delete circuitBreaker.cooldownUntil[key];
}

async function apiCall(path, options = {}, retries = 2) {
  if (isCircuitOpen(path)) {
    throw new Error('Service temporarily unavailable. Try again in a moment.');
  }
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await withTimeout(fetch(API_BASE + path, options), 10000);
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || res.statusText);
      }
      const data = await res.json();
      recordSuccess(path);
      return data;
    } catch (err) {
      lastErr = err;
      recordFailure(path);
      if (attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt + 1) * 500));
      }
    }
  }
  throw lastErr;
}

async function apiGet(path) {
  return apiCall(path, { headers: authHeader() });
}

async function apiPost(path, body, auth = true) {
  return apiCall(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(auth ? authHeader() : {}) },
    body: JSON.stringify(body),
  });
}

function authHeader() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

// ─── Analytics & Event Tracking ─────────────────────────
function trackEvent(eventName, properties = {}) {
  const event = {
    event: eventName,
    properties: { ...properties },
    timestamp: new Date().toISOString(),
    session_id: state.token ? 'authenticated' : 'anonymous',
  };
  if (typeof console !== 'undefined' && console.debug) {
    console.debug('[Analytics]', event);
  }
  try {
    const events = JSON.parse(safeGet('analytics_events') || '[]');
    events.push(event);
    if (events.length > 100) events.shift();
    safeSet('analytics_events', JSON.stringify(events));
  } catch {}
}

function trackSearch(query, filters = {}) {
  trackEvent('search_submitted', { query, ...filters });
}

function trackCardClick(job) {
  trackEvent('job_card_clicked', {
    job_id: job.id || job._id,
    company: job.company_name,
    title: job.title,
  });
}

function trackApplyClick(job, url) {
  trackEvent('apply_clicked', {
    job_id: job.id || job._id,
    company: job.company_name,
    title: job.title,
    has_url: validateApplyUrl(url),
    url_domain: validateApplyUrl(url) ? new URL(url).hostname : null,
  });
}

function trackBookmark(job) {
  trackEvent('job_bookmarked', {
    job_id: job.id || job._id,
    company: job.company_name,
  });
}

function trackError(component, error) {
  trackEvent('error', { component, message: error.message || String(error) });
}

// ─── UI Helpers ─────────────────────────────────────────
function showToast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.2s'; setTimeout(() => t.remove(), 200); }, 3000);
}

// ─── Saved Jobs ─────────────────────────────────────────
function saveJob(jobId) {
  if (state.savedJobs.includes(jobId)) {
    state.savedJobs = state.savedJobs.filter(id => id !== jobId);
    safeSet('saved_jobs', JSON.stringify(state.savedJobs));
    showToast('Removed from saved jobs', 'info');
  } else {
    state.savedJobs.push(jobId);
    safeSet('saved_jobs', JSON.stringify(state.savedJobs));
    showToast('Saved to your jobs', 'success');
  }
}

function isJobSaved(jobId) {
  return state.savedJobs.includes(jobId);
}

function toggleSaveJob(jobId, event) {
  event?.stopPropagation();
  saveJob(jobId);
  const btn = event?.currentTarget;
  if (btn) btn.textContent = isJobSaved(jobId) ? '★ Saved' : '☆ Save';
}

function toggleSaveCard(jobId, btn) {
  saveJob(jobId);
  btn.textContent = isJobSaved(jobId) ? '★' : '☆';
  btn.classList.toggle('saved', isJobSaved(jobId));
}

// ─── Card Animation Keyframe (added via JS to avoid CSS bloat) ──
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
`;
document.head.appendChild(styleSheet);
