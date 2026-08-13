import { useState, useEffect, useCallback, useRef } from 'react'
import JobCard from './components/JobCard.jsx'
import SearchBar from './components/SearchBar.jsx'
import FilterPanel from './components/FilterPanel.jsx'
import Navbar from './components/Navbar.jsx'
import HeroSection from './components/HeroSection.jsx'
import StatsBar from './components/StatsBar.jsx'
import JobDetailModal from './components/JobDetailModal.jsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

function App() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [totalJobs, setTotalJobs] = useState(0)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [selectedJob, setSelectedJob] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState({
    location: '',
    remote: '',
    job_type: '',
    experience: '',
    salary_min: '',
    salary_max: '',
    posted_within_days: '',
  })
  const [stats, setStats] = useState({
    total_jobs: 0,
    verified_jobs: 0,
    scam_detected: 0,
    companies: 0,
  })

  const searchTimeoutRef = useRef(null)

  // ─── Fetch Jobs ────────────────────────────────────────────────────────────

  const fetchJobs = useCallback(async (reset = false) => {
    setLoading(true)
    const currentPage = reset ? 1 : page

    try {
      const params = new URLSearchParams({
        page: currentPage,
        page_size: 20,
        sort_by: 'posted_at',
        sort_order: 'desc',
      })

      if (searchQuery) params.set('q', searchQuery)
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.set(k, v)
      })

      const response = await fetch(`${API_URL}/jobs?${params}`)
      if (!response.ok) throw new Error('Failed to fetch jobs')

      const data = await response.json()

      if (reset) {
        setJobs(data.results || [])
        setPage(1)
      } else {
        setJobs(prev => [...prev, ...(data.results || [])])
      }

      setTotalJobs(data.total || 0)
      setHasMore((data.results || []).length === 20)
    } catch (err) {
      console.error('Fetch error:', err)
      // Load mock data for demo
      if (reset) setJobs(MOCK_JOBS)
    } finally {
      setLoading(false)
    }
  }, [searchQuery, filters, page])

  // ─── Fetch Stats ───────────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/analytics/stats`)
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch {
      setStats({ total_jobs: 124_532, verified_jobs: 98_234, scam_detected: 2_891, companies: 4_201 })
    }
  }, [])

  // ─── Effects ───────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchStats()
  }, [])

  useEffect(() => {
    clearTimeout(searchTimeoutRef.current)
    searchTimeoutRef.current = setTimeout(() => {
      fetchJobs(true)
    }, 300)
    return () => clearTimeout(searchTimeoutRef.current)
  }, [searchQuery, filters])

  const handleLoadMore = () => {
    setPage(p => p + 1)
    fetchJobs(false)
  }

  const handleSearch = (query) => {
    setSearchQuery(query)
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const handleFilterReset = () => {
    setFilters({
      location: '', remote: '', job_type: '',
      experience: '', salary_min: '', salary_max: '', posted_within_days: '',
    })
  }

  return (
    <div className="app">
      <Navbar />

      {/* Hero Section — visible when no search active */}
      {!searchQuery && jobs.length === 0 && !loading && (
        <HeroSection onSearch={handleSearch} />
      )}

      {/* Main Content */}
      <main className="main-content">
        <div className="container">

          {/* Stats Bar */}
          <StatsBar stats={stats} />

          {/* Search + Filters Row */}
          <section className="search-section">
            <SearchBar
              value={searchQuery}
              onChange={handleSearch}
              totalResults={totalJobs}
            />
            <FilterPanel
              filters={filters}
              onFilterChange={handleFilterChange}
              onReset={handleFilterReset}
            />
          </section>

          {/* Results Area */}
          <div className="results-area">
            {loading && jobs.length === 0 ? (
              <div className="jobs-grid">
                {Array.from({ length: 6 }).map((_, i) => (
                  <JobCardSkeleton key={i} />
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="empty-state animate-fade-in">
                <div className="empty-state-icon">🔍</div>
                <h3 className="text-xl font-semibold">No jobs found</h3>
                <p className="text-secondary">Try adjusting your search query or filters</p>
                <button className="btn btn-secondary" onClick={handleFilterReset}>
                  Clear all filters
                </button>
              </div>
            ) : (
              <>
                {/* Results Header */}
                <div className="results-header flex items-center justify-between mb-6">
                  <p className="text-secondary text-sm">
                    Showing <span className="text-primary font-semibold">{jobs.length}</span> of{' '}
                    <span className="text-primary font-semibold">{totalJobs.toLocaleString()}</span> jobs
                    {searchQuery && <> for <strong className="text-brand">"{searchQuery}"</strong></>}
                  </p>
                  <div className="flex gap-2">
                    <span className="badge badge-success">
                      <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
                        <circle cx="4" cy="4" r="4"/>
                      </svg>
                      {stats.verified_jobs?.toLocaleString()} Verified
                    </span>
                  </div>
                </div>

                {/* Jobs Grid */}
                <div className="jobs-grid">
                  {jobs.map((job, idx) => (
                    <div
                      key={job.id}
                      className="animate-fade-in"
                      style={{ animationDelay: `${Math.min(idx * 40, 400)}ms` }}
                    >
                      <JobCard
                        job={job}
                        onClick={() => setSelectedJob(job)}
                      />
                    </div>
                  ))}
                </div>

                {/* Load More */}
                {hasMore && (
                  <div className="load-more-container">
                    <button
                      className="btn btn-secondary btn-lg"
                      onClick={handleLoadMore}
                      disabled={loading}
                    >
                      {loading ? (
                        <><span className="spinner" /> Loading...</>
                      ) : (
                        'Load more jobs'
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {/* Job Detail Modal */}
      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
        />
      )}

      <style>{appStyles}</style>
    </div>
  )
}

// ─── Skeleton Card ─────────────────────────────────────────────────────────────

function JobCardSkeleton() {
  return (
    <div className="glass-card job-card">
      <div className="flex gap-4 items-start">
        <div className="skeleton" style={{ width: 48, height: 48, borderRadius: 10, flexShrink: 0 }} />
        <div className="flex-1">
          <div className="skeleton mb-2" style={{ height: 20, width: '70%' }} />
          <div className="skeleton mb-3" style={{ height: 14, width: '45%' }} />
          <div className="flex gap-2">
            {[60, 80, 50].map((w, i) => (
              <div key={i} className="skeleton" style={{ height: 22, width: w }} />
            ))}
          </div>
        </div>
      </div>
      <div className="skeleton mt-4" style={{ height: 40 }} />
    </div>
  )
}

// ─── Mock Data (for demo when API unavailable) ─────────────────────────────────

const MOCK_JOBS = [
  {
    id: '1', title: 'Senior Python Engineer', company_name: 'Razorpay',
    location: 'Bangalore, Karnataka', remote_type: 'hybrid', job_type: 'full_time',
    experience_level: 'senior', salary_display: '₹30L - ₹50L/year',
    required_skills: ['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Kafka'],
    tech_stack: ['AWS', 'Docker', 'Kubernetes'],
    posted_at: new Date(Date.now() - 86400000).toISOString(),
    scam_risk: 'very_low', is_verified: true, quality_score: 92,
    apply_url: '#', source_url: '#',
  },
  {
    id: '2', title: 'ML Engineer — GenAI', company_name: 'Google DeepMind',
    location: 'Hyderabad, Telangana', remote_type: 'remote', job_type: 'full_time',
    experience_level: 'senior', salary_display: '₹60L - ₹120L/year',
    required_skills: ['PyTorch', 'TensorFlow', 'Python', 'LLM', 'MLOps'],
    tech_stack: ['GCP', 'Vertex AI', 'Kubernetes'],
    posted_at: new Date(Date.now() - 172800000).toISOString(),
    scam_risk: 'very_low', is_verified: true, quality_score: 98,
    apply_url: '#', source_url: '#',
  },
  {
    id: '3', title: 'Full Stack Developer', company_name: 'Zepto',
    location: 'Mumbai, Maharashtra', remote_type: 'on_site', job_type: 'full_time',
    experience_level: 'mid', salary_display: '₹15L - ₹25L/year',
    required_skills: ['React', 'Node.js', 'TypeScript', 'PostgreSQL'],
    tech_stack: ['AWS', 'Docker'],
    posted_at: new Date(Date.now() - 259200000).toISOString(),
    scam_risk: 'very_low', is_verified: true, quality_score: 85,
    apply_url: '#', source_url: '#',
  },
  {
    id: '4', title: 'DevOps / Platform Engineer', company_name: 'CRED',
    location: 'Bangalore, Karnataka', remote_type: 'hybrid', job_type: 'full_time',
    experience_level: 'senior', salary_display: '₹35L - ₹55L/year',
    required_skills: ['Kubernetes', 'Terraform', 'AWS', 'Python', 'Go'],
    tech_stack: ['Istio', 'Prometheus', 'ArgoCD'],
    posted_at: new Date(Date.now() - 345600000).toISOString(),
    scam_risk: 'very_low', is_verified: true, quality_score: 90,
    apply_url: '#', source_url: '#',
  },
  {
    id: '5', title: 'Data Scientist', company_name: 'PhonePe',
    location: 'Bangalore, Karnataka', remote_type: 'hybrid', job_type: 'full_time',
    experience_level: 'mid', salary_display: '₹18L - ₹32L/year',
    required_skills: ['Python', 'Machine Learning', 'SQL', 'Spark', 'Statistics'],
    tech_stack: ['GCP', 'BigQuery', 'Airflow'],
    posted_at: new Date(Date.now() - 432000000).toISOString(),
    scam_risk: 'very_low', is_verified: true, quality_score: 88,
    apply_url: '#', source_url: '#',
  },
  {
    id: '6', title: 'Frontend Engineer — React', company_name: 'Meesho',
    location: 'Bangalore, Karnataka', remote_type: 'remote', job_type: 'full_time',
    experience_level: 'mid', salary_display: '₹12L - ₹22L/year',
    required_skills: ['React', 'TypeScript', 'GraphQL', 'CSS'],
    tech_stack: ['Next.js', 'Storybook', 'Jest'],
    posted_at: new Date(Date.now() - 518400000).toISOString(),
    scam_risk: 'low', is_verified: true, quality_score: 82,
    apply_url: '#', source_url: '#',
  },
]

// ─── Component Styles ──────────────────────────────────────────────────────────

const appStyles = `
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  padding: var(--space-8) 0;
}

.search-section {
  margin-bottom: var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.jobs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: var(--space-4);
}

.load-more-container {
  display: flex;
  justify-content: center;
  margin-top: var(--space-10);
  padding-bottom: var(--space-10);
}

@media (max-width: 768px) {
  .jobs-grid {
    grid-template-columns: 1fr;
  }
}
`

export default App
