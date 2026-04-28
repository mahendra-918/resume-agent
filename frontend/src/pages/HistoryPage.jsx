import { useEffect, useState, useMemo } from 'react'
import { getApplications, clearApplications } from '../api'

// ── Constants ────────────────────────────────────────────────────────────────

const STATUS_META = {
  applied: { label: 'Applied', bg: '#d1fae5', color: '#065f46', icon: '✅' },
  skipped: { label: 'Skipped', bg: '#fef9c3', color: '#854d0e', icon: '⊘'  },
  failed:  { label: 'Failed',  bg: '#fee2e2', color: '#991b1b', icon: '❌' },
}

const PLATFORMS = ['all', 'linkedin', 'naukri', 'internshala', 'wellfound']

// ── Sub-components ───────────────────────────────────────────────────────────

function SummaryCard({ label, count, bg, color }) {
  return (
    <div style={{ ...s.summaryCard, background: bg }}>
      <span style={{ ...s.summaryCount, color }}>{count}</span>
      <span style={{ ...s.summaryLabel, color }}>{label}</span>
    </div>
  )
}

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, bg: '#f3f4f6', color: '#374151', icon: '•' }
  return (
    <span style={{ ...s.badge, background: meta.bg, color: meta.color }}>
      {meta.icon} {meta.label}
    </span>
  )
}

function ScoreBar({ score }) {
  if (score == null || score === 0) return <span style={s.dimText}>—</span>
  const pct = Math.round(score * 100)
  const color = score >= 0.7 ? '#059669' : score >= 0.5 ? '#d97706' : '#dc2626'
  return (
    <div style={s.scoreWrapper}>
      <div style={{ ...s.scoreBar, width: `${pct}%`, background: color }} />
      <span style={{ ...s.scoreText, color }}>{pct}%</span>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function HistoryPage({ isRunning }) {
  const [applications, setApplications] = useState([])
  const [loading,      setLoading]      = useState(false)
  const [clearing,     setClearing]     = useState(false)
  const [error,        setError]        = useState(null)

  // ── Filter & Sort State
  const [search,      setSearch]      = useState('')
  const [platform,    setPlatform]    = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortKey,     setSortKey]     = useState('id')
  const [sortDir,     setSortDir]     = useState('desc')

  async function fetchApplications() {
    setLoading(true)
    setError(null)
    try {
      const data = await getApplications()
      setApplications(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    if (!window.confirm('Delete all application history? This cannot be undone.')) return
    setClearing(true)
    try {
      await clearApplications()
      setApplications([])
    } catch (err) {
      setError(err.message)
    } finally {
      setClearing(false)
    }
  }

  useEffect(() => { fetchApplications() }, [])

  // Auto-refresh every 5s while a run is live
  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(fetchApplications, 5000)
    return () => clearInterval(id)
  }, [isRunning])

  // ── Sorting handler
  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // ── Filtered + sorted data (memoized for performance)
  const rows = useMemo(() => {
    let filtered = applications

    if (search.trim()) {
      const q = search.toLowerCase()
      filtered = filtered.filter(a =>
        a.job_title?.toLowerCase().includes(q) ||
        a.company?.toLowerCase().includes(q)
      )
    }
    if (platform !== 'all') {
      filtered = filtered.filter(a => a.platform === platform)
    }
    if (statusFilter !== 'all') {
      filtered = filtered.filter(a => a.status === statusFilter)
    }

    filtered = [...filtered].sort((a, b) => {
      let va = a[sortKey] ?? ''
      let vb = b[sortKey] ?? ''
      if (typeof va === 'string') va = va.toLowerCase()
      if (typeof vb === 'string') vb = vb.toLowerCase()
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ?  1 : -1
      return 0
    })

    return filtered
  }, [applications, search, platform, statusFilter, sortKey, sortDir])

  // ── Summary counts
  const total   = applications.length
  const applied = applications.filter(a => a.status === 'applied').length
  const skipped = applications.filter(a => a.status === 'skipped').length
  const failed  = applications.filter(a => a.status === 'failed').length

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span style={s.sortIcon}>⇅</span>
    return <span style={{ ...s.sortIcon, color: '#6366f1' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  return (
    <div style={s.page}>
      {/* ── Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Dashboard</h1>
          <p style={s.subtitle}>{total} total applications recorded</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={fetchApplications} style={s.ghostBtn} disabled={loading}>
            {loading ? '⟳ Refreshing…' : '⟳ Refresh'}
          </button>
          <button
            onClick={handleClear}
            style={s.dangerBtn}
            disabled={loading || clearing || total === 0}
          >
            {clearing ? 'Clearing…' : '🗑 Clear All'}
          </button>
        </div>
      </div>

      {/* ── Live run banner */}
      {isRunning && (
        <div style={s.liveBanner}>
          <span style={s.liveDot} />
          Agent is running — auto-refreshing every 5 seconds
          <a href="/run" style={s.liveLink}>View live feed →</a>
        </div>
      )}

      {/* ── Summary cards */}
      <div style={s.summaryRow}>
        <SummaryCard label="Applied" count={applied} bg="#d1fae5" color="#065f46" />
        <SummaryCard label="Skipped" count={skipped} bg="#fef9c3" color="#854d0e" />
        <SummaryCard label="Failed"  count={failed}  bg="#fee2e2" color="#991b1b" />
        <SummaryCard label="Total"   count={total}   bg="#ede9fe" color="#4c1d95" />
      </div>

      {/* ── Filters */}
      <div style={s.filters}>
        <input
          placeholder="Search by job title or company…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={s.searchInput}
        />
        <select value={platform} onChange={e => setPlatform(e.target.value)} style={s.select}>
          {PLATFORMS.map(p => (
            <option key={p} value={p}>{p === 'all' ? 'All Platforms' : p.charAt(0).toUpperCase() + p.slice(1)}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={s.select}>
          <option value="all">All Statuses</option>
          <option value="applied">Applied</option>
          <option value="skipped">Skipped</option>
          <option value="failed">Failed</option>
        </select>
        {(search || platform !== 'all' || statusFilter !== 'all') && (
          <button
            style={s.ghostBtn}
            onClick={() => { setSearch(''); setPlatform('all'); setStatusFilter('all') }}
          >
            ✕ Clear Filters
          </button>
        )}
      </div>

      {/* ── Error */}
      {error && <div style={s.errorBanner}>{error}</div>}

      {/* ── Empty state */}
      {!loading && !error && rows.length === 0 && (
        <div style={s.emptyState}>
          <span style={{ fontSize: '48px' }}>📭</span>
          <p style={s.emptyText}>
            {applications.length === 0
              ? 'No applications yet. Start a run to begin!'
              : 'No results match your filters.'}
          </p>
        </div>
      )}

      {/* ── Table */}
      {rows.length > 0 && (
        <div style={s.tableWrapper}>
          <table style={s.table}>
            <thead>
              <tr>
                {[
                  { key: 'job_title', label: 'Role' },
                  { key: 'company',   label: 'Company' },
                  { key: 'platform',  label: 'Platform' },
                  { key: 'status',    label: 'Status' },
                  { key: 'relevance_score', label: 'Score' },
                  { key: null,        label: 'Job Link' },
                  { key: null,        label: 'Resume' },
                ].map(({ key, label }) => (
                  <th
                    key={label}
                    style={{ ...s.th, cursor: key ? 'pointer' : 'default' }}
                    onClick={() => key && handleSort(key)}
                  >
                    {label} {key && <SortIcon col={key} />}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((app, i) => (
                <tr key={i} style={i % 2 === 0 ? s.rowEven : s.rowOdd}>
                  <td style={s.td}>
                    <span style={s.jobTitle}>{app.job_title}</span>
                  </td>
                  <td style={s.td}>{app.company || '—'}</td>
                  <td style={s.td}>
                    <span style={s.platformTag}>{app.platform}</span>
                  </td>
                  <td style={s.td}>
                    <StatusBadge status={app.status} />
                  </td>
                  <td style={s.td}>
                    <ScoreBar score={app.relevance_score} />
                  </td>
                  <td style={s.td}>
                    <a
                      href={app.job_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={s.link}
                    >
                      View ↗
                    </a>
                  </td>
                  <td style={s.td}>
                    {app.tailored_resume_path ? (
                      <a
                        href={`/tailored/${app.tailored_resume_path.split(/[/\\]/).pop()}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ ...s.link, color: '#4f46e5', fontWeight: 600 }}
                      >
                        📄 PDF
                      </a>
                    ) : (
                      <span style={s.dimText}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={s.rowCount}>Showing {rows.length} of {total} applications</p>
        </div>
      )}
    </div>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────

const s = {
  page:      { padding: '32px', fontFamily: "'Inter', system-ui, sans-serif", maxWidth: '1200px', margin: '0 auto' },
  header:    { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' },
  title:     { margin: '0 0 4px', fontSize: '26px', fontWeight: 700, color: '#111827' },
  subtitle:  { margin: 0, fontSize: '14px', color: '#6b7280' },
  ghostBtn:  { padding: '8px 16px', fontSize: '13px', fontWeight: 500, borderRadius: '8px', border: '1.5px solid #d1d5db', background: '#fff', color: '#374151', cursor: 'pointer', fontFamily: 'inherit' },
  dangerBtn: { padding: '8px 16px', fontSize: '13px', fontWeight: 500, borderRadius: '8px', border: '1.5px solid #fca5a5', background: '#fff', color: '#dc2626', cursor: 'pointer', fontFamily: 'inherit' },

  liveBanner: { display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 16px', marginBottom: '24px', borderRadius: '8px', background: '#ede9fe', color: '#4c1d95', fontSize: '13px', fontWeight: 500 },
  liveDot:    { display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#7c3aed', animation: 'pulse 1.2s ease-in-out infinite', flexShrink: 0 },
  liveLink:   { marginLeft: 'auto', color: '#6366f1', fontWeight: 600, textDecoration: 'none', fontSize: '13px' },

  summaryRow:   { display: 'flex', gap: '16px', marginBottom: '28px' },
  summaryCard:  { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px', borderRadius: '12px', gap: '4px' },
  summaryCount: { fontSize: '36px', fontWeight: 800, lineHeight: 1 },
  summaryLabel: { fontSize: '13px', fontWeight: 600 },

  filters:     { display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' },
  searchInput: { flex: 1, minWidth: '200px', padding: '9px 14px', fontSize: '14px', borderRadius: '8px', border: '1.5px solid #d1d5db', outline: 'none', fontFamily: 'inherit' },
  select:      { padding: '9px 12px', fontSize: '14px', borderRadius: '8px', border: '1.5px solid #d1d5db', background: '#fff', cursor: 'pointer', fontFamily: 'inherit' },

  errorBanner: { padding: '12px 16px', borderRadius: '8px', background: '#fee2e2', color: '#991b1b', fontSize: '14px', marginBottom: '20px' },
  emptyState:  { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 0', gap: '12px' },
  emptyText:   { margin: 0, fontSize: '15px', color: '#9ca3af' },

  tableWrapper: { overflowX: 'auto', borderRadius: '12px', border: '1.5px solid #e5e7eb' },
  table:        { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th:           { textAlign: 'left', padding: '12px 16px', background: '#f9fafb', borderBottom: '1.5px solid #e5e7eb', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap', userSelect: 'none' },
  sortIcon:     { marginLeft: '4px', fontSize: '12px', color: '#9ca3af' },
  td:           { padding: '12px 16px', borderBottom: '1px solid #f3f4f6', color: '#111827', verticalAlign: 'middle' },
  rowEven:      { background: '#fff' },
  rowOdd:       { background: '#fafafa' },

  jobTitle:    { fontWeight: 500, color: '#111827' },
  platformTag: { display: 'inline-block', padding: '2px 8px', borderRadius: '4px', background: '#f3f4f6', fontSize: '12px', fontWeight: 500, color: '#374151', textTransform: 'capitalize' },
  badge:       { display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 10px', borderRadius: '999px', fontSize: '12px', fontWeight: 600 },
  link:        { color: '#6366f1', textDecoration: 'none', fontWeight: 500, fontSize: '13px' },
  dimText:     { color: '#9ca3af' },

  scoreWrapper: { display: 'flex', alignItems: 'center', gap: '8px' },
  scoreBar:     { height: '6px', borderRadius: '3px', minWidth: '4px', transition: 'width 0.3s ease' },
  scoreText:    { fontSize: '12px', fontWeight: 600, minWidth: '32px' },

  rowCount: { textAlign: 'right', fontSize: '12px', color: '#9ca3af', margin: '10px 16px 4px' },
}
