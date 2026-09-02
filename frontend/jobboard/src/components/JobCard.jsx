/**
 * JobCard — Premium job listing card with trust indicators,
 * skill tags, and smooth hover animations.
 */

import { useState } from 'react'

const REMOTE_LABELS = {
  remote: { label: 'Remote', color: 'badge-success' },
  hybrid: { label: 'Hybrid', color: 'badge-brand' },
  on_site: { label: 'On-site', color: 'badge-neutral' },
}

const EXP_LABELS = {
  entry: 'Entry Level',
  mid: 'Mid Level',
  senior: 'Senior',
  lead: 'Lead / Principal',
  executive: 'Executive',
  unknown: '',
}

const SCAM_RISK_CONFIG = {
  very_low: { icon: '✓', label: 'Verified', className: 'trust-high' },
  low:      { icon: '✓', label: 'Safe', className: 'trust-high' },
  medium:   { icon: '⚠', label: 'Review', className: 'trust-medium' },
  high:     { icon: '⚠', label: 'High Risk', className: 'trust-low' },
  very_high:{ icon: '✗', label: 'Suspicious', className: 'trust-low' },
}

function timeAgo(dateStr) {
  if (!dateStr) return 'Recently'
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}

function getCompanyInitials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase()
}

function getCompanyColor(name) {
  const colors = [
    'hsl(220, 80%, 55%)', 'hsl(270, 80%, 55%)', 'hsl(145, 65%, 42%)',
    'hsl(38, 95%, 55%)',  'hsl(330, 75%, 55%)',  'hsl(190, 80%, 50%)',
  ]
  let hash = 0
  for (const c of name) hash = (hash << 5) - hash + c.charCodeAt(0)
  return colors[Math.abs(hash) % colors.length]
}

export default function JobCard({ job, onClick }) {
  const [saved, setSaved] = useState(false)

  const remote = REMOTE_LABELS[job.remote_type] || REMOTE_LABELS.on_site
  const risk = SCAM_RISK_CONFIG[job.scam_risk] || SCAM_RISK_CONFIG.medium
  const companyColor = getCompanyColor(job.company_name)
  const skills = job.required_skills || []
  const displaySkills = skills.slice(0, 4)
  const moreSkills = skills.length - displaySkills.length

  const handleSave = (e) => {
    e.stopPropagation()
    setSaved(s => !s)
  }

  const handleApply = (e) => {
    e.stopPropagation()
    let url = job.apply_url || job.source_url
    if (url && url !== '#') {
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url
      }
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <div className="glass-card job-card" onClick={onClick} role="article" aria-label={`${job.title} at ${job.company_name}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {/* Company Logo */}
          <div className="company-logo" style={{ '--logo-color': companyColor }}>
            {job.company_logo ? (
              <img src={job.company_logo} alt={job.company_name} />
            ) : (
              <span>{getCompanyInitials(job.company_name)}</span>
            )}
          </div>

          {/* Title & Company */}
          <div className="flex-1 min-w-0">
            <h3 className="job-title">{job.title}</h3>
            <p className="company-name">{job.company_name}</p>
          </div>
        </div>

        {/* Save Button */}
        <button
          className={`save-btn ${saved ? 'saved' : ''}`}
          onClick={handleSave}
          aria-label={saved ? 'Unsave job' : 'Save job'}
        >
          {saved ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>
            </svg>
          )}
        </button>
      </div>

      {/* Location & Meta */}
      <div className="job-meta flex items-center flex-wrap gap-2 mt-3">
        {job.location && (
          <span className="meta-item">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
              <circle cx="12" cy="10" r="3"/>
            </svg>
            {job.location}
          </span>
        )}
        {job.experience_level && job.experience_level !== 'unknown' && (
          <span className="meta-item">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="8" r="4"/>
              <path d="M2 20c0-4.4 4.5-8 10-8s10 3.6 10 8"/>
            </svg>
            {EXP_LABELS[job.experience_level]}
          </span>
        )}
        <span className="meta-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
          {timeAgo(job.posted_at)}
        </span>
      </div>

      {/* Badges Row */}
      <div className="flex flex-wrap gap-2 mt-3">
        <span className={`badge ${remote.color}`}>{remote.label}</span>
        {job.job_type && job.job_type !== 'unknown' && (
          <span className="badge badge-neutral">
            {job.job_type.replace('_', ' ')}
          </span>
        )}
        {job.salary_display && (
          <span className="badge badge-neutral salary-badge">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
            </svg>
            {job.salary_display}
          </span>
        )}
      </div>

      {/* Skills */}
      {displaySkills.length > 0 && (
        <div className="skills-row flex flex-wrap gap-1 mt-3">
          {displaySkills.map(skill => (
            <span key={skill} className="skill-tag">{skill}</span>
          ))}
          {moreSkills > 0 && (
            <span className="skill-tag skill-more">+{moreSkills}</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="card-footer flex items-center justify-between mt-4">
        {/* Trust Score */}
        <div className={`trust-score ${risk.className}`}>
          <span>{risk.icon}</span>
          <span>{risk.label}</span>
          {job.is_verified && (
            <span style={{ opacity: 0.6 }}>· Verified</span>
          )}
        </div>

        {/* Apply Button */}
        <button
          className="btn btn-primary btn-sm"
          onClick={handleApply}
        >
          Apply now
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </div>

      <style>{styles}</style>
    </div>
  )
}

const styles = `
.company-logo {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--logo-color) 15%, transparent);
  border: 1px solid color-mix(in srgb, var(--logo-color) 30%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--logo-color);
  letter-spacing: 0.05em;
  overflow: hidden;
  transition: transform var(--transition-fast);
}

.glass-card:hover .company-logo {
  transform: scale(1.05);
}

.company-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.job-title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary);
  transition: color var(--transition-fast);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.glass-card:hover .job-title {
  color: var(--color-brand-300);
}

.company-name {
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin-top: 2px;
}

.save-btn {
  padding: 6px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.save-btn:hover {
  color: var(--color-brand-400);
  background: hsla(220, 80%, 50%, 0.1);
}

.save-btn.saved {
  color: var(--color-brand-400);
}

.job-meta {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.salary-badge {
  font-variant-numeric: tabular-nums;
}

.skill-tag {
  padding: 3px 8px;
  border-radius: var(--radius-md);
  font-size: 0.72rem;
  font-weight: 500;
  font-family: var(--font-mono);
  background: hsla(220, 80%, 50%, 0.08);
  color: var(--color-brand-300);
  border: 1px solid hsla(220, 80%, 50%, 0.15);
  transition: all var(--transition-fast);
}

.skill-tag:hover {
  background: hsla(220, 80%, 50%, 0.15);
}

.skill-more {
  background: hsla(220, 20%, 100%, 0.04);
  color: var(--text-muted);
  border-color: var(--glass-border);
}

.card-footer {
  padding-top: var(--space-3);
  border-top: 1px solid var(--glass-border);
}
`
