import { useEffect, useState, useMemo, useRef } from 'react'
import { getApplications, clearApplications } from '../api'

// ── Constants ────────────────────────────────────────────────────────────────

const PLATFORM_COLORS = {
  linkedin:   { bg: 'rgba(10,102,194,0.15)',  color: '#60a5fa', border: 'rgba(10,102,194,0.3)'  },
  naukri:     { bg: 'rgba(245,158,11,0.12)',  color: '#fbbf24', border: 'rgba(245,158,11,0.25)' },
  internshala:{ bg: 'rgba(34,197,94,0.12)',   color: '#4ade80', border: 'rgba(34,197,94,0.25)'  },
  wellfound:  { bg: 'rgba(139,92,246,0.12)',  color: '#a78bfa', border: 'rgba(139,92,246,0.25)' },
}

const PLATFORMS = ['all', 'linkedin', 'naukri', 'internshala', 'wellfound']

// ── Package Modal ─────────────────────────────────────────────────────────────

function PackageModal({ title, url, jobTitle, company, platform, score, jobUrl, onClose }) {
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [copied,  setCopied]  = useState(false)

  useEffect(() => {
    fetch(url)
      .then(r => r.json())
      .then(data => { setContent(data.content); setLoading(false) })
      .catch(err  => { setError(err.message);   setLoading(false) })
  }, [url])

  function handleCopy() {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const pc = PLATFORM_COLORS[platform] || PLATFORM_COLORS.linkedin

  return (
    <div style={m.overlay} onClick={onClose}>
      <div style={m.box} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={m.header}>
          <span style={m.title}>{title}</span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {content && (
              <button onClick={handleCopy} style={copied ? m.copiedBtn : m.copyBtn}>
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            )}
            <button onClick={onClose} style={m.closeBtn}>✕</button>
          </div>
        </div>

        {/* Job context */}
        <div style={m.jobBanner}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div>
              <div style={m.jobTitle}>{jobTitle}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                <span style={m.company}>{company}</span>
                <span style={{ color: 'var(--text-dim)' }}>·</span>
                <span style={{ ...m.platformChip, background: pc.bg, color: pc.color, border: `1px solid ${pc.border}` }}>
                  {platform}
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              {score > 0 && (
                <span style={{
                  ...m.scoreBadge,
                  background: score >= 0.7 ? 'var(--green-dim)' : score >= 0.5 ? 'var(--yellow-dim)' : 'var(--red-dim)',
                  color:      score >= 0.7 ? 'var(--green)'     : score >= 0.5 ? 'var(--yellow)'     : 'var(--red)',
                  border:     `1px solid ${score >= 0.7 ? 'rgba(34,197,94,0.25)' : score >= 0.5 ? 'rgba(245,158,11,0.25)' : 'rgba(239,68,68,0.25)'}`,
                }}>
                  {Math.round(score * 100)}% match
                </span>
              )}
              <a href={jobUrl} target="_blank" rel="noreferrer" style={m.jobLink}>View Job ↗</a>
            </div>
          </div>
        </div>

        {/* Content */}
        <div style={m.body}>
          {loading && <div style={m.loadingText}>Loading…</div>}
          {error   && <div style={m.errorText}>Error: {error}</div>}
          {content && <pre style={m.pre}>{content}</pre>}
        </div>
      </div>
    </div>
  )
}

const m = {
  overlay:    { position:'fixed', inset:0, background:'rgba(0,0,0,0.7)', backdropFilter:'blur(4px)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000, padding:'24px' },
  box:        { background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'14px', width:'100%', maxWidth:'700px', maxHeight:'82vh', display:'flex', flexDirection:'column', boxShadow:'0 24px 80px rgba(0,0,0,0.6)' },
  header:     { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'16px 20px', borderBottom:'1px solid var(--border)' },
  title:      { fontSize:'14px', fontWeight:600, color:'var(--text)' },
  closeBtn:   { background:'var(--surface-2)', border:'1px solid var(--border)', borderRadius:'6px', width:'28px', height:'28px', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', color:'var(--text-muted)', fontSize:'13px', fontWeight:600 },
  copyBtn:    { padding:'5px 12px', fontSize:'12px', fontWeight:600, borderRadius:'6px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', cursor:'pointer' },
  copiedBtn:  { padding:'5px 12px', fontSize:'12px', fontWeight:600, borderRadius:'6px', border:'1px solid rgba(34,197,94,0.3)', background:'rgba(34,197,94,0.1)', color:'var(--green)', cursor:'pointer' },
  body:       { padding:'20px', overflowY:'auto', flex:1 },
  pre:        { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', fontSize:'13px', lineHeight:1.8, fontFamily:"'Inter',system-ui,sans-serif", color:'var(--text)' },
  jobBanner:  { padding:'14px 20px', background:'var(--surface-2)', borderBottom:'1px solid var(--border)' },
  jobTitle:   { fontSize:'15px', fontWeight:700, color:'var(--text)' },
  company:    { fontSize:'13px', color:'var(--text-muted)' },
  platformChip:{ padding:'2px 8px', borderRadius:'4px', fontSize:'11px', fontWeight:600, textTransform:'capitalize' },
  scoreBadge: { padding:'4px 10px', borderRadius:'999px', fontSize:'12px', fontWeight:700 },
  jobLink:    { fontSize:'13px', color:'var(--accent)', fontWeight:600, textDecoration:'none' },
  loadingText:{ color:'var(--text-muted)', fontSize:'14px' },
  errorText:  { color:'var(--red)', fontSize:'14px' },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, accent }) {
  return (
    <div style={{ ...sc.card, ...(accent ? sc.accentCard : {}) }}>
      <div style={{ ...sc.value, ...(accent ? { color: 'var(--accent)' } : {}) }}>{value}</div>
      <div style={sc.label}>{label}</div>
    </div>
  )
}

const sc = {
  card:      { background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'12px', padding:'20px 24px', flex:1, minWidth:'140px' },
  accentCard:{ borderColor:'var(--border-accent)', background:'var(--accent-dim)' },
  value:     { fontSize:'32px', fontWeight:800, color:'var(--text)', lineHeight:1, marginBottom:'6px', letterSpacing:'-1px' },
  label:     { fontSize:'12px', fontWeight:500, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.06em' },
}

function PlatformTag({ platform }) {
  const pc = PLATFORM_COLORS[platform] || { bg:'var(--surface-3)', color:'var(--text-muted)', border:'var(--border)' }
  return (
    <span style={{ padding:'2px 8px', borderRadius:'5px', fontSize:'11px', fontWeight:600, textTransform:'capitalize', background:pc.bg, color:pc.color, border:`1px solid ${pc.border}` }}>
      {platform}
    </span>
  )
}

function ScoreBar({ score }) {
  if (!score) return <span style={{ color:'var(--text-dim)' }}>—</span>
  const pct   = Math.round(score * 100)
  const color = score >= 0.7 ? 'var(--green)' : score >= 0.5 ? 'var(--yellow)' : 'var(--red)'
  const bgCol = score >= 0.7 ? 'rgba(34,197,94,0.15)' : score >= 0.5 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
      <div style={{ flex:1, height:'5px', borderRadius:'3px', background:'var(--surface-3)', overflow:'hidden', minWidth:'60px' }}>
        <div style={{ height:'100%', width:`${pct}%`, borderRadius:'3px', background:color, boxShadow:`0 0 6px ${color}` }} />
      </div>
      <span style={{ fontSize:'12px', fontWeight:700, color, minWidth:'30px' }}>{pct}%</span>
    </div>
  )
}

function MissingSkills({ notes }) {
  if (!notes?.includes('Missing:')) return <span style={{ color:'var(--text-dim)' }}>—</span>
  const skills = notes.split('Missing:')[1]?.split(',').map(s => s.trim()).filter(Boolean) || []
  if (!skills.length) return <span style={{ color:'var(--text-dim)' }}>—</span>
  return (
    <div style={{ display:'flex', flexWrap:'wrap', gap:'4px' }}>
      {skills.slice(0, 3).map(skill => (
        <span key={skill} style={{ padding:'2px 7px', borderRadius:'4px', fontSize:'11px', fontWeight:600, background:'var(--red-dim)', color:'var(--red)', border:'1px solid rgba(239,68,68,0.2)' }}>
          {skill}
        </span>
      ))}
      {skills.length > 3 && (
        <span style={{ fontSize:'11px', color:'var(--text-dim)', alignSelf:'center' }}>+{skills.length - 3}</span>
      )}
    </div>
  )
}

function PackageActions({ app, onOpen }) {
  if (!app.notes?.includes('→')) return <span style={{ color:'var(--text-dim)' }}>—</span>
  const dir = app.notes.split('→')[1].trim()
  const files = [
    { label:'Cover Letter',   file:'cover_letter.txt',  color:'#a78bfa' },
    { label:'Email Draft',    file:'email_draft.txt',   color:'#60a5fa' },
    { label:'Interview Prep', file:'interview_prep.txt', color:'#4ade80' },
  ]
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:'4px' }}>
      {app.tailored_resume_path && (
        <a
          href={`/api/tailored/${app.tailored_resume_path}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ fontSize:'12px', fontWeight:600, color:'var(--green)', textDecoration:'none', display:'inline-flex', alignItems:'center', gap:'4px' }}
        >
          ↗ Resume PDF
        </a>
      )}
      {files.map(({ label, file, color }) => (
        <button
          key={file}
          onClick={() => onOpen({
            title:    `${label} — ${app.job_title} @ ${app.company}`,
            url:      `/api/packages/${dir}/${file}`,
            jobTitle: app.job_title,
            company:  app.company,
            platform: app.platform,
            score:    app.relevance_score,
            jobUrl:   app.job_url,
          })}
          style={{ background:'none', border:'none', padding:'1px 0', textAlign:'left', cursor:'pointer', fontSize:'12px', fontWeight:500, color, display:'inline-flex', alignItems:'center', gap:'4px' }}
        >
          ↗ {label}
        </button>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function HistoryPage({ isRunning }) {
  const [applications, setApplications] = useState([])
  const [loading,      setLoading]      = useState(false)
  const [clearing,     setClearing]     = useState(false)
  const [error,        setError]        = useState(null)
  const [search,       setSearch]       = useState('')
  const [platform,     setPlatform]     = useState('all')
  const [sortKey,      setSortKey]      = useState('id')
  const [sortDir,      setSortDir]      = useState('desc')
  const [activeModal,  setActiveModal]  = useState(null)
  const [hoveredRow,   setHoveredRow]   = useState(null)
  const prevRunningRef = useRef(false)

  async function fetchApplications() {
    setLoading(true); setError(null)
    try {
      const data = await getApplications()
      setApplications(data)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleClear() {
    if (!window.confirm('Delete all packages? This cannot be undone.')) return
    setClearing(true)
    try { await clearApplications(); setApplications([]) }
    catch (err) { setError(err.message) }
    finally { setClearing(false) }
  }

  useEffect(() => { fetchApplications() }, [])

  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(fetchApplications, 5000)
    return () => clearInterval(id)
  }, [isRunning])

  useEffect(() => {
    if (prevRunningRef.current === true && isRunning === false) fetchApplications()
    prevRunningRef.current = isRunning
  }, [isRunning])

  function handleSort(key) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const rows = useMemo(() => {
    let f = applications
    if (search.trim()) {
      const q = search.toLowerCase()
      f = f.filter(a => a.job_title?.toLowerCase().includes(q) || a.company?.toLowerCase().includes(q))
    }
    if (platform !== 'all') f = f.filter(a => a.platform === platform)
    return [...f].sort((a, b) => {
      let va = a[sortKey] ?? '', vb = b[sortKey] ?? ''
      if (typeof va === 'string') { va = va.toLowerCase(); vb = vb.toLowerCase() }
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ?  1 : -1
      return 0
    })
  }, [applications, search, platform, sortKey, sortDir])

  const total     = applications.length
  const generated = applications.filter(a => a.status === 'generated').length
  const avgScore  = applications.length
    ? Math.round(applications.reduce((s, a) => s + (a.relevance_score || 0), 0) / applications.length * 100)
    : 0

  const SortIcon = ({ col }) => (
    <span style={{ marginLeft:'4px', fontSize:'11px', color: sortKey === col ? 'var(--accent)' : 'var(--text-dim)' }}>
      {sortKey === col ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
    </span>
  )

  const TH = ({ col, label, style: extra = {} }) => (
    <th
      onClick={() => col && handleSort(col)}
      style={{ ...s.th, cursor: col ? 'pointer' : 'default', ...extra }}
    >
      {label}{col && <SortIcon col={col} />}
    </th>
  )

  return (
    <div style={s.page}>
      {/* ── Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Dashboard</h1>
          <p style={s.subtitle}>
            {total > 0 ? `${total} application package${total !== 1 ? 's' : ''} generated` : 'No packages yet'}
          </p>
        </div>
        <div style={{ display:'flex', gap:'8px' }}>
          <button onClick={fetchApplications} style={s.ghostBtn} disabled={loading}>
            <span style={{ display:'inline-flex', alignItems:'center', gap:'6px' }}>
              <span style={loading ? { display:'inline-block', animation:'spin 0.8s linear infinite' } : {}}>⟳</span>
              {loading ? 'Refreshing' : 'Refresh'}
            </span>
          </button>
          <button onClick={handleClear} style={s.dangerBtn} disabled={loading || clearing || total === 0}>
            {clearing ? 'Clearing…' : 'Clear All'}
          </button>
        </div>
      </div>

      {/* ── Live banner */}
      {isRunning && (
        <div style={s.liveBanner}>
          <span style={s.liveDot} />
          Agent running · auto-refreshing every 5s
          <a href="/run" style={s.liveLink}>View live feed →</a>
        </div>
      )}

      {/* ── Stat cards */}
      <div style={s.statRow}>
        <StatCard label="Packages Ready" value={generated} accent />
        <StatCard label="Total Generated" value={total} />
        <StatCard label="Avg Match Score" value={total ? `${avgScore}%` : '—'} />
      </div>

      {/* ── Filters */}
      <div style={s.filterBar}>
        <div style={s.searchWrap}>
          <span style={s.searchIcon}>⌕</span>
          <input
            placeholder="Search by role or company…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={s.searchInput}
          />
          {search && (
            <button onClick={() => setSearch('')} style={s.clearX}>✕</button>
          )}
        </div>
        <div style={s.pillRow}>
          {PLATFORMS.map(p => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              style={{
                ...s.filterPill,
                ...(platform === p ? s.filterPillActive : {}),
              }}
            >
              {p === 'all' ? 'All' : p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Error */}
      {error && <div style={s.errorBanner}>{error}</div>}

      {/* ── Empty state */}
      {!loading && !error && rows.length === 0 && (
        <div style={s.emptyState}>
          <div style={s.emptyIcon}>📭</div>
          <p style={s.emptyTitle}>
            {applications.length === 0 ? 'No packages yet' : 'No results match your filters'}
          </p>
          <p style={s.emptyHint}>
            {applications.length === 0 ? 'Go to New Run to start the agent.' : 'Try clearing your filters.'}
          </p>
        </div>
      )}

      {/* ── Table */}
      {rows.length > 0 && (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr>
                <TH col="job_title"       label="Role"          />
                <TH col="company"         label="Company"       />
                <TH col="platform"        label="Platform"      />
                <TH col="relevance_score" label="Match"         />
                <TH col={null}            label="Missing Skills" />
                <TH col={null}            label="Job"           style={{ width:'60px' }} />
                <TH col={null}            label="Package Files" style={{ width:'160px' }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((app, i) => (
                <tr
                  key={i}
                  onMouseEnter={() => setHoveredRow(i)}
                  onMouseLeave={() => setHoveredRow(null)}
                  style={{ background: hoveredRow === i ? 'var(--surface-2)' : 'transparent', transition:'background 0.12s' }}
                >
                  <td style={s.td}>
                    <span style={s.jobTitle}>{app.job_title}</span>
                  </td>
                  <td style={{ ...s.td, color:'var(--text-muted)' }}>{app.company || '—'}</td>
                  <td style={s.td}><PlatformTag platform={app.platform} /></td>
                  <td style={s.td}><ScoreBar score={app.relevance_score} /></td>
                  <td style={s.td}><MissingSkills notes={app.notes} /></td>
                  <td style={s.td}>
                    {app.job_url
                      ? <a href={app.job_url} target="_blank" rel="noopener noreferrer" style={s.link}>↗</a>
                      : <span style={{ color:'var(--text-dim)' }}>—</span>
                    }
                  </td>
                  <td style={s.td}>
                    <PackageActions app={app} onOpen={setActiveModal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={s.tableFooter}>
            Showing {rows.length} of {total} packages
          </div>
        </div>
      )}

      {/* ── Modal */}
      {activeModal && (
        <PackageModal {...activeModal} onClose={() => setActiveModal(null)} />
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page:     { padding:'32px', maxWidth:'1280px', margin:'0 auto', animation:'fadeIn 0.2s ease' },
  header:   { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'28px' },
  title:    { margin:'0 0 4px', fontSize:'24px', fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px' },
  subtitle: { margin:0, fontSize:'13px', color:'var(--text-muted)' },

  ghostBtn: { padding:'7px 14px', fontSize:'13px', fontWeight:500, borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', cursor:'pointer', display:'inline-flex', alignItems:'center', gap:'6px' },
  dangerBtn:{ padding:'7px 14px', fontSize:'13px', fontWeight:500, borderRadius:'8px', border:'1px solid rgba(239,68,68,0.3)', background:'rgba(239,68,68,0.08)', color:'var(--red)', cursor:'pointer' },

  liveBanner:{ display:'flex', alignItems:'center', gap:'10px', padding:'10px 16px', marginBottom:'24px', borderRadius:'10px', background:'rgba(34,197,94,0.07)', border:'1px solid rgba(34,197,94,0.2)', color:'#4ade80', fontSize:'13px', fontWeight:500 },
  liveDot:   { display:'inline-block', width:'7px', height:'7px', borderRadius:'50%', background:'#22c55e', flexShrink:0, boxShadow:'0 0 6px #22c55e', animation:'pulse 1.4s ease-in-out infinite' },
  liveLink:  { marginLeft:'auto', color:'var(--accent)', fontWeight:600, textDecoration:'none', fontSize:'13px' },

  statRow: { display:'flex', gap:'12px', marginBottom:'24px', flexWrap:'wrap' },

  filterBar: { display:'flex', gap:'12px', marginBottom:'20px', alignItems:'center', flexWrap:'wrap' },
  searchWrap:{ position:'relative', flex:1, minWidth:'200px', display:'flex', alignItems:'center' },
  searchIcon:{ position:'absolute', left:'12px', color:'var(--text-muted)', fontSize:'16px', pointerEvents:'none' },
  searchInput:{ width:'100%', padding:'8px 36px', fontSize:'13px', borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', outline:'none' },
  clearX:    { position:'absolute', right:'10px', background:'none', border:'none', color:'var(--text-muted)', cursor:'pointer', fontSize:'13px', padding:'2px 4px' },
  pillRow:   { display:'flex', gap:'6px', flexWrap:'wrap' },
  filterPill:{ padding:'6px 14px', borderRadius:'999px', fontSize:'12px', fontWeight:500, border:'1px solid var(--border)', background:'transparent', color:'var(--text-muted)', cursor:'pointer', transition:'all 0.15s' },
  filterPillActive:{ background:'var(--accent-dim)', border:'1px solid var(--border-accent)', color:'var(--accent)' },

  errorBanner:{ padding:'12px 16px', borderRadius:'8px', background:'var(--red-dim)', border:'1px solid rgba(239,68,68,0.2)', color:'var(--red)', fontSize:'14px', marginBottom:'20px' },

  emptyState:{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'100px 0', gap:'8px' },
  emptyIcon: { fontSize:'48px', marginBottom:'8px' },
  emptyTitle:{ margin:0, fontSize:'16px', fontWeight:600, color:'var(--text-muted)' },
  emptyHint: { margin:0, fontSize:'13px', color:'var(--text-dim)' },

  tableWrap:  { borderRadius:'12px', border:'1px solid var(--border)', overflow:'hidden', background:'var(--surface)' },
  table:      { width:'100%', borderCollapse:'collapse', fontSize:'13px' },
  th:         { textAlign:'left', padding:'11px 16px', background:'var(--surface-2)', borderBottom:'1px solid var(--border)', fontWeight:600, color:'var(--text-muted)', whiteSpace:'nowrap', userSelect:'none', fontSize:'12px', textTransform:'uppercase', letterSpacing:'0.04em' },
  td:         { padding:'12px 16px', borderBottom:'1px solid var(--border)', color:'var(--text)', verticalAlign:'middle' },

  jobTitle: { fontWeight:600, color:'var(--text)', fontSize:'13px' },
  link:     { color:'var(--accent)', textDecoration:'none', fontWeight:600, fontSize:'15px' },

  tableFooter:{ padding:'10px 16px', fontSize:'12px', color:'var(--text-dim)', textAlign:'right', borderTop:'1px solid var(--border)', background:'var(--surface-2)' },
}
