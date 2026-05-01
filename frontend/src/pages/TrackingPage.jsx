import { useState, useEffect } from 'react'

const COLUMNS = [
  { key: 'ready',        label: 'Package Ready', icon: '⬡', accent: '#8b5cf6', dim: 'rgba(139,92,246,0.1)',  border: 'rgba(139,92,246,0.2)'  },
  { key: 'applied',      label: 'Applied',       icon: '→', accent: '#3b82f6', dim: 'rgba(59,130,246,0.1)',  border: 'rgba(59,130,246,0.2)'  },
  { key: 'phone_screen', label: 'Phone Screen',  icon: '◎', accent: '#f59e0b', dim: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.2)'  },
  { key: 'interview',    label: 'Interview',     icon: '◈', accent: '#22c55e', dim: 'rgba(34,197,94,0.1)',   border: 'rgba(34,197,94,0.2)'   },
  { key: 'offer',        label: 'Offer',         icon: '◆', accent: '#10b981', dim: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.2)'  },
  { key: 'rejected',     label: 'Rejected',      icon: '✕', accent: '#ef4444', dim: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.2)'   },
]

const PLATFORM_COLORS = {
  linkedin:    '#60a5fa',
  naukri:      '#fbbf24',
  internshala: '#4ade80',
  wellfound:   '#a78bfa',
}

// ── Note Modal ─────────────────────────────────────────────────────────────────

function NoteModal({ card, onClose, onSave }) {
  const [notes,  setNotes]  = useState(card.notes || '')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    await onSave(card.package_dir, card.status, notes)
    setSaving(false); onClose()
  }

  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.noteBox} onClick={e => e.stopPropagation()}>
        <div style={s.noteHeader}>
          <div>
            <div style={s.noteTitle}>{card.job_title}</div>
            <div style={s.noteSubtitle}>{card.company}</div>
          </div>
          <button onClick={onClose} style={s.closeBtn}>✕</button>
        </div>
        <textarea
          style={s.textarea}
          rows={6}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Add notes — interview date, contact name, follow-up needed…"
          autoFocus
        />
        <div style={{ display:'flex', gap:'8px', justifyContent:'flex-end', marginTop:'14px' }}>
          <button onClick={onClose} style={s.ghostBtn}>Cancel</button>
          <button onClick={handleSave} disabled={saving} style={s.primaryBtn}>
            {saving ? 'Saving…' : 'Save Notes'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Job Card ───────────────────────────────────────────────────────────────────

function JobCard({ card, columns, onMove, onNote }) {
  const pct         = Math.round((card.relevance_score || 0) * 100)
  const scoreColor  = pct >= 70 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444'
  const platformCol = PLATFORM_COLORS[card.platform] || 'var(--text-muted)'
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={s.card}>
      {/* Top row */}
      <div style={s.cardTop}>
        <div style={s.cardTitleWrap}>
          <span style={s.cardTitle}>{card.job_title}</span>
        </div>
        <span style={{ ...s.scorePill, color: scoreColor, background: scoreColor + '18', border: `1px solid ${scoreColor}30` }}>
          {pct}%
        </span>
      </div>

      {/* Company + platform */}
      <div style={s.cardMeta}>
        <span style={s.cardCompany}>{card.company}</span>
        <span style={{ ...s.cardPlatform, color: platformCol }}>· {card.platform}</span>
      </div>

      {/* Notes preview */}
      {card.notes && (
        <div style={s.cardNotes}>
          {card.notes.length > 80 ? card.notes.slice(0, 80) + '…' : card.notes}
        </div>
      )}

      {/* Actions */}
      <div style={s.cardFooter}>
        {card.job_url && (
          <a href={card.job_url} target="_blank" rel="noreferrer" style={s.cardLink}>View ↗</a>
        )}
        <button onClick={() => onNote(card)} style={s.noteBtn}>
          {card.notes ? 'Edit note' : '+ Note'}
        </button>
        <button onClick={() => setExpanded(x => !x)} style={s.moreBtn}>
          {expanded ? '▲' : '▼'}
        </button>
      </div>

      {/* Move to column buttons */}
      {expanded && (
        <div style={s.moveGrid}>
          {columns.filter(c => c.key !== card.status).map(col => (
            <button
              key={col.key}
              onClick={() => { onMove(card.package_dir, col.key, card.notes); setExpanded(false) }}
              style={{ ...s.moveBtn, color: col.accent, background: col.dim, border: `1px solid ${col.border}` }}
            >
              {col.icon} {col.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Kanban Column ──────────────────────────────────────────────────────────────

function KanbanColumn({ col, cards, allColumns, onMove, onNote }) {
  return (
    <div style={s.column}>
      <div style={{ ...s.colHeader, background: col.dim, borderBottom: `1px solid ${col.border}` }}>
        <div style={{ display:'flex', alignItems:'center', gap:'7px' }}>
          <span style={{ color: col.accent, fontSize:'14px', fontWeight:700 }}>{col.icon}</span>
          <span style={{ ...s.colLabel, color: col.accent }}>{col.label}</span>
        </div>
        <span style={{ ...s.colCount, background: col.dim, color: col.accent, border: `1px solid ${col.border}` }}>
          {cards.length}
        </span>
      </div>
      <div style={s.colBody}>
        {cards.length === 0 && <div style={s.emptyCol}>Empty</div>}
        {cards.map(card => (
          <JobCard
            key={card.package_dir}
            card={card}
            columns={allColumns}
            onMove={onMove}
            onNote={onNote}
          />
        ))}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function TrackingPage() {
  const [cards,    setCards]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)
  const [noteCard, setNoteCard] = useState(null)

  async function fetchCards() {
    setLoading(true)
    try {
      const r = await fetch('/api/tracking')
      setCards(await r.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchCards() }, [])

  async function handleMove(packageDir, newStatus, notes) {
    await fetch(`/api/tracking/${packageDir}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, notes: notes || '' }),
    })
    setCards(prev => prev.map(c => c.package_dir === packageDir ? { ...c, status: newStatus } : c))
  }

  async function handleSaveNote(packageDir, status, notes) {
    await fetch(`/api/tracking/${packageDir}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, notes }),
    })
    setCards(prev => prev.map(c => c.package_dir === packageDir ? { ...c, notes } : c))
  }

  if (loading) return (
    <div style={s.page}>
      <div style={s.loadingRow}><span style={s.spinner} /> Loading tracker…</div>
    </div>
  )

  if (error) return (
    <div style={s.page}>
      <div style={s.errorBanner}>Error: {error}</div>
    </div>
  )

  const total    = cards.length
  const pipeline = COLUMNS.slice(1, 5).reduce((n, c) => n + cards.filter(x => x.status === c.key).length, 0)

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Job Tracker</h1>
          <p style={s.subtitle}>
            {total} packages · {pipeline} in pipeline
          </p>
        </div>
        <button onClick={fetchCards} style={s.ghostBtn}>⟳ Refresh</button>
      </div>

      {/* Pipeline progress bar */}
      {total > 0 && (
        <div style={s.progressWrap}>
          {COLUMNS.map(col => {
            const count = cards.filter(c => c.status === col.key).length
            const pct   = total > 0 ? (count / total) * 100 : 0
            if (pct === 0) return null
            return (
              <div
                key={col.key}
                title={`${col.label}: ${count}`}
                style={{ flex: pct, minWidth:'4px', height:'100%', background: col.accent, transition:'flex 0.4s ease' }}
              />
            )
          })}
        </div>
      )}

      {/* Empty state */}
      {total === 0 && (
        <div style={s.empty}>
          <div style={s.emptyIcon}>📋</div>
          <p style={s.emptyTitle}>No packages tracked yet</p>
          <p style={s.emptyHint}>Run the agent to generate application packages.</p>
        </div>
      )}

      {/* Board */}
      {total > 0 && (
        <div style={s.board}>
          {COLUMNS.map(col => (
            <KanbanColumn
              key={col.key}
              col={col}
              cards={cards.filter(c => c.status === col.key)}
              allColumns={COLUMNS}
              onMove={handleMove}
              onNote={setNoteCard}
            />
          ))}
        </div>
      )}

      {/* Note modal */}
      {noteCard && (
        <NoteModal
          card={noteCard}
          onClose={() => setNoteCard(null)}
          onSave={handleSaveNote}
        />
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page:    { padding:'32px', animation:'fadeIn 0.2s ease', minHeight:'calc(100vh - 52px)' },
  header:  { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'20px' },
  title:   { margin:'0 0 4px', fontSize:'24px', fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px' },
  subtitle:{ margin:0, fontSize:'13px', color:'var(--text-muted)' },

  ghostBtn: { padding:'7px 14px', fontSize:'13px', fontWeight:500, borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', cursor:'pointer' },

  progressWrap: { display:'flex', height:'4px', borderRadius:'2px', overflow:'hidden', background:'var(--surface-2)', marginBottom:'24px', gap:'2px' },

  loadingRow:  { display:'flex', alignItems:'center', gap:'10px', padding:'40px 0', color:'var(--text-muted)', fontSize:'14px' },
  errorBanner: { padding:'12px 16px', borderRadius:'8px', background:'var(--red-dim)', border:'1px solid rgba(239,68,68,0.2)', color:'var(--red)', fontSize:'14px' },
  spinner:     { display:'inline-block', width:'14px', height:'14px', border:'2px solid var(--border)', borderTop:'2px solid var(--accent)', borderRadius:'50%', animation:'spin 0.7s linear infinite', flexShrink:0 },

  empty:      { display:'flex', flexDirection:'column', alignItems:'center', padding:'100px 0', gap:'8px' },
  emptyIcon:  { fontSize:'48px', marginBottom:'8px' },
  emptyTitle: { margin:0, fontSize:'16px', fontWeight:600, color:'var(--text-muted)' },
  emptyHint:  { margin:0, fontSize:'13px', color:'var(--text-dim)' },

  board:   { display:'flex', gap:'12px', overflowX:'auto', paddingBottom:'20px', alignItems:'flex-start' },
  column:  { minWidth:'220px', width:'220px', flexShrink:0, borderRadius:'12px', border:'1px solid var(--border)', background:'var(--surface)', overflow:'hidden' },
  colHeader:{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'10px 12px' },
  colLabel: { fontSize:'12px', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.05em' },
  colCount: { fontSize:'11px', fontWeight:700, padding:'1px 8px', borderRadius:'999px' },
  colBody:  { padding:'10px', display:'flex', flexDirection:'column', gap:'8px', minHeight:'100px' },
  emptyCol: { textAlign:'center', color:'var(--text-dim)', fontSize:'12px', padding:'24px 0', borderRadius:'8px', border:'1px dashed var(--border)' },

  card:     { background:'var(--surface-2)', border:'1px solid var(--border)', borderRadius:'9px', padding:'12px', transition:'border-color 0.15s' },
  cardTop:  { display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'6px', marginBottom:'4px' },
  cardTitleWrap: { flex:1, minWidth:0 },
  cardTitle:{ fontSize:'12px', fontWeight:700, color:'var(--text)', lineHeight:1.35, wordBreak:'break-word' },
  scorePill:{ fontSize:'10px', fontWeight:700, padding:'2px 7px', borderRadius:'999px', flexShrink:0 },
  cardMeta: { display:'flex', alignItems:'center', gap:'4px', marginBottom:'8px' },
  cardCompany: { fontSize:'11px', color:'var(--text-muted)', fontWeight:500 },
  cardPlatform:{ fontSize:'11px', textTransform:'capitalize' },
  cardNotes:   { fontSize:'11px', color:'var(--text-muted)', background:'var(--surface-3)', borderRadius:'5px', padding:'6px 8px', marginBottom:'8px', lineHeight:1.5 },
  cardFooter:  { display:'flex', alignItems:'center', gap:'6px' },
  cardLink:    { fontSize:'11px', color:'var(--accent)', fontWeight:600, textDecoration:'none' },
  noteBtn:     { fontSize:'11px', color:'var(--text-muted)', background:'none', border:'1px solid var(--border)', borderRadius:'4px', padding:'2px 7px', cursor:'pointer', marginLeft:'auto' },
  moreBtn:     { fontSize:'10px', color:'var(--text-dim)', background:'none', border:'1px solid var(--border)', borderRadius:'4px', padding:'2px 6px', cursor:'pointer' },
  moveGrid:    { display:'flex', flexWrap:'wrap', gap:'4px', marginTop:'8px', paddingTop:'8px', borderTop:'1px solid var(--border)' },
  moveBtn:     { fontSize:'10px', fontWeight:600, borderRadius:'4px', padding:'3px 7px', cursor:'pointer' },

  overlay:    { position:'fixed', inset:0, background:'rgba(0,0,0,0.7)', backdropFilter:'blur(4px)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000, padding:'24px' },
  noteBox:    { background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'14px', padding:'24px', width:'100%', maxWidth:'500px', boxShadow:'0 24px 80px rgba(0,0,0,0.6)' },
  noteHeader: { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'16px' },
  noteTitle:  { fontSize:'15px', fontWeight:700, color:'var(--text)' },
  noteSubtitle:{ fontSize:'13px', color:'var(--text-muted)', marginTop:'2px' },
  closeBtn:   { background:'var(--surface-2)', border:'1px solid var(--border)', borderRadius:'6px', width:'28px', height:'28px', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', color:'var(--text-muted)', fontSize:'13px', fontWeight:700, flexShrink:0 },
  textarea:   { width:'100%', padding:'12px', fontSize:'13px', borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', outline:'none', resize:'vertical', fontFamily:'inherit', boxSizing:'border-box', lineHeight:1.6 },
  ghostBtn:   { padding:'7px 16px', fontSize:'13px', fontWeight:500, borderRadius:'8px', border:'1px solid var(--border)', background:'transparent', color:'var(--text-muted)', cursor:'pointer' },
  primaryBtn: { padding:'7px 18px', fontSize:'13px', fontWeight:600, borderRadius:'8px', border:'none', background:'var(--accent)', color:'#fff', cursor:'pointer', boxShadow:'0 0 12px rgba(139,92,246,0.3)' },
}
