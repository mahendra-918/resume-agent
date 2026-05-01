import { useEffect, useRef, useState } from 'react'
import { startRun, openRunSocket, uploadResume } from '../api'

const STORAGE_KEY = 'resumeAgentSettings'

const EVENT_STYLE = {
  node_done:         { color: '#4ade80', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.15)',   icon: '✓' },
  package_generated: { color: '#a78bfa', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.15)',  icon: '⬡' },
  applied:           { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',   border: 'rgba(34,197,94,0.3)',    icon: '✅' },
  skipped:           { color: '#71717a', bg: 'rgba(113,113,122,0.06)', border: 'rgba(113,113,122,0.12)', icon: '·'  },
  failed:            { color: '#f87171', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.15)',   icon: '✕' },
  error:             { color: '#f87171', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.15)',   icon: '!' },
  done:              { color: '#a78bfa', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.15)',  icon: '◆' },
}

function loadSettings() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null }
  catch { return null }
}

function fmtTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-IN', { hour12: false })
}

function eventMessage(ev) {
  if (ev.type === 'package_generated') return `Package ready — ${ev.job} @ ${ev.company}`
  if (ev.type === 'done') {
    const s = ev.summary || {}
    return `Run complete · ${s.packages ?? 0} packages generated · ${s.jobs_found ?? 0} jobs found`
  }
  if (ev.type === 'applied') return ev.message || `Applied → ${ev.job} @ ${ev.company}`
  return ev.message || ev.node || ev.type || 'Event received'
}

// Don't render low-signal skipped-apply events when apply is disabled
function shouldShowEvent(ev) {
  if (ev.type === 'skipped' && ev.message && ev.message.startsWith('Apply disabled')) return false
  return true
}

// ── Event Row ─────────────────────────────────────────────────────────────────

function EventRow({ ev }) {
  const style = EVENT_STYLE[ev.type] ?? EVENT_STYLE.node_done
  let pdfUrl = null
  if (ev.file_path) {
    const filename = ev.file_path.split(/[/\\]/).pop()
    pdfUrl = `/api/tailored/${filename}`
  }

  return (
    <div style={{ ...s.eventRow, background: style.bg, borderColor: style.border }}>
      <span style={{ ...s.eventIcon, color: style.color }}>{style.icon}</span>
      <span style={{ ...s.eventMsg, color: style.color }}>
        {eventMessage(ev)}
        {pdfUrl && (
          <a href={pdfUrl} target="_blank" rel="noreferrer" style={s.pdfLink}>
            View PDF ↗
          </a>
        )}
      </span>
      <span style={s.eventTime}>{fmtTime(ev.ts)}</span>
    </div>
  )
}

// ── Summary Cards ─────────────────────────────────────────────────────────────

function SummaryCards({ summary }) {
  const cards = [
    { label: 'Jobs Found',  value: summary.jobs_found  ?? 0, color: 'var(--blue)',   dim: 'var(--blue-dim)'   },
    { label: 'Jobs Ranked', value: summary.jobs_ranked ?? 0, color: 'var(--green)',  dim: 'var(--green-dim)'  },
    { label: 'Packages',    value: summary.packages    ?? 0, color: 'var(--accent)', dim: 'var(--accent-dim)' },
  ]
  return (
    <div style={s.summaryCards}>
      {cards.map(c => (
        <div key={c.label} style={{ ...s.summaryCard, background: c.dim, border: `1px solid ${c.color}30` }}>
          <span style={{ ...s.summaryCount, color: c.color }}>{c.value}</span>
          <span style={s.summaryLabel}>{c.label}</span>
        </div>
      ))}
    </div>
  )
}

// ── File Drop Zone ────────────────────────────────────────────────────────────

function FileDropZone({ uploadedName, isDragging, uploading, uploadError, disabled, onDrop, onDragOver, onDragLeave }) {
  const inputRef = useRef(null)

  function handleFiles(files) {
    if (files?.[0]) onDrop(files[0])
  }

  const borderColor = isDragging ? 'var(--accent)' : uploadedName ? 'rgba(34,197,94,0.5)' : 'var(--border)'
  const bgColor     = isDragging ? 'var(--accent-dim)' : uploadedName ? 'rgba(34,197,94,0.05)' : 'var(--surface-2)'

  return (
    <div
      style={{ ...s.dropZone, borderColor, background: bgColor, opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto' }}
      onDragOver={e => { e.preventDefault(); onDragOver() }}
      onDragLeave={onDragLeave}
      onDrop={e => { e.preventDefault(); onDragLeave(); handleFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
    >
      <input ref={inputRef} type="file" accept=".pdf,.docx,.md" style={{ display: 'none' }} onChange={e => handleFiles(e.target.files)} />

      {uploading ? (
        <><span style={s.spinner} /><span style={s.dropText}>Uploading…</span></>
      ) : uploadedName ? (
        <>
          <div style={s.fileIcon}>📄</div>
          <span style={{ ...s.dropText, color: 'var(--green)' }}>{uploadedName}</span>
          <span style={s.dropHint}>Click or drag to replace</span>
        </>
      ) : (
        <>
          <div style={s.uploadIcon}>↑</div>
          <span style={s.dropText}>Drop your resume here</span>
          <span style={s.dropHint}>PDF · DOCX · MD · Click to browse</span>
        </>
      )}

      {uploadError && <span style={s.dropError}>{uploadError}</span>}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function RunPage({ runEvents, setRunEvents, runSummary, setRunSummary, isRunning, setIsRunning, runError, setRunError, wsRef, resetRun }) {
  const feedRef = useRef(null)
  const settings = loadSettings() || {}

  const [uploadedPath, setUploadedPath] = useState(settings.resumePath || '')
  const [uploadedName, setUploadedName] = useState(settings.resumePath ? settings.resumePath.split('/').pop() : '')
  const [isDragging,   setIsDragging]   = useState(false)
  const [uploading,    setUploading]    = useState(false)
  const [uploadError,  setUploadError]  = useState(null)
  const [applyEnabled, setApplyEnabled] = useState(false)

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [runEvents])

  async function handleSubmit(e) {
    e.preventDefault()
    if (isRunning) return
    setRunEvents([]); setRunSummary(null); setRunError(null); setIsRunning(true)
    if (!uploadedPath) { setRunError('Please upload a resume file first.'); setIsRunning(false); return }
    try {
      const { run_id } = await startRun({ resumePath: uploadedPath, settings: loadSettings(), applyEnabled })
      wsRef.current = openRunSocket(run_id, (ev) => {
        setRunEvents(prev => [...prev, ev])
        if (ev.type === 'done')  { setRunSummary(ev.summary); setIsRunning(false); wsRef.current?.close(); wsRef.current = null }
        if (ev.type === 'error') { setRunError(ev.message);   setIsRunning(false); wsRef.current?.close(); wsRef.current = null }
      }, () => setIsRunning(false))
    } catch (err) { setRunError(err.message); setIsRunning(false) }
  }

  function handleStop() {
    wsRef.current?.close(); wsRef.current = null; setIsRunning(false)
    setRunEvents(prev => [...prev, { type:'error', message:'Run stopped by user', ts: new Date().toISOString() }])
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div>
          <h1 style={s.title}>New Run</h1>
          <p style={s.subtitle}>
            {isRunning
              ? <span style={{ color:'var(--accent)' }}>Agent is active — you can safely browse other pages.</span>
              : 'Upload your resume and start the agent. It will search, rank, and package applications.'}
          </p>
        </div>
        {isRunning && (
          <div style={s.runningBadge}>
            <span style={s.liveDot} />
            Running
          </div>
        )}
      </div>

      {/* ── Form */}
      <div style={s.card}>
        <form onSubmit={handleSubmit}>
          <div style={s.field}>
            <label style={s.label}>Resume File</label>
            <FileDropZone
              uploadedName={uploadedName}
              isDragging={isDragging}
              uploading={uploading}
              uploadError={uploadError}
              disabled={isRunning}
              onDrop={async (file) => {
                setUploadError(null); setUploading(true)
                try { const r = await uploadResume(file); setUploadedPath(r.path); setUploadedName(r.filename) }
                catch (err) { setUploadError(err.message) }
                finally { setUploading(false) }
              }}
              onDragOver={() => setIsDragging(true)}
              onDragLeave={() => setIsDragging(false)}
            />
          </div>

          <div style={s.applyToggleRow}>
            <label style={s.applyToggleLabel}>
              <div
                role="switch"
                aria-checked={applyEnabled}
                tabIndex={0}
                style={{ ...s.track, background: applyEnabled ? 'var(--accent)' : 'var(--surface-3)', boxShadow: applyEnabled ? '0 0 8px rgba(139,92,246,0.4)' : 'none', opacity: isRunning ? 0.5 : 1, pointerEvents: isRunning ? 'none' : 'auto' }}
                onClick={() => !isRunning && setApplyEnabled(v => !v)}
                onKeyDown={e => !isRunning && (e.key === ' ' || e.key === 'Enter') && setApplyEnabled(v => !v)}
              >
                <div style={{ ...s.knob, transform: applyEnabled ? 'translateX(20px)' : 'translateX(2px)' }} />
              </div>
              <span style={s.applyToggleText}>Apply to Jobs (LinkedIn Easy Apply)</span>
            </label>
            {applyEnabled && (
              <div style={s.applyWarning}>
                Browser window will open during the run — make sure LinkedIn credentials are set in Settings.
              </div>
            )}
          </div>

          <div style={s.btnRow}>
            <button type="submit" disabled={isRunning} style={{ ...s.btn, ...s.btnPrimary, opacity: isRunning ? 0.5 : 1 }}>
              {isRunning ? <><span style={s.spinner} /> Running…</> : '▶  Start Run'}
            </button>
            {isRunning && (
              <button type="button" onClick={handleStop} style={{ ...s.btn, ...s.btnDanger }}>■  Stop</button>
            )}
            {(runEvents.length > 0 || runSummary) && !isRunning && (
              <button type="button" onClick={resetRun} style={{ ...s.btn, ...s.btnGhost }}>✕  Clear</button>
            )}
          </div>

          {runError && <div style={s.errorBanner}>{runError}</div>}
        </form>
      </div>

      {/* ── Live feed */}
      {runEvents.length > 0 && (
        <div style={{ ...s.card, marginTop:'16px' }}>
          <div style={s.feedHeader}>
            <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
              {isRunning && <span style={s.liveDot} />}
              <span style={s.feedTitle}>{isRunning ? 'Live Activity' : 'Run Log'}</span>
            </div>
            <span style={s.feedBadge}>{runEvents.length} events</span>
          </div>
          <div style={s.feed} ref={feedRef}>
            {runEvents.filter(shouldShowEvent).map((ev, i) => <EventRow key={i} ev={ev} />)}
            {isRunning && (
              <div style={s.workingRow}>
                <span style={s.workingDot} />
                <span style={s.workingText}>Processing…</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Summary */}
      {runSummary && (
        <div style={{ ...s.card, marginTop:'16px' }}>
          <div style={s.summaryHead}>
            <span style={s.doneIcon}>◆</span>
            <span style={s.summaryTitle}>Run Complete</span>
          </div>
          <SummaryCards summary={runSummary} />
          <p style={s.summaryHint}>
            Head to the <a href="/" style={s.link}>Dashboard</a> to view your packages.
          </p>
        </div>
      )}
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page:    { padding:'32px', maxWidth:'680px', margin:'0 auto', animation:'fadeIn 0.2s ease' },
  header:  { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'24px', gap:'16px' },
  title:   { margin:'0 0 4px', fontSize:'24px', fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px' },
  subtitle:{ margin:0, fontSize:'13px', color:'var(--text-muted)', lineHeight:1.6 },

  runningBadge: { display:'inline-flex', alignItems:'center', gap:'8px', padding:'6px 14px', borderRadius:'999px', background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)', color:'var(--green)', fontSize:'13px', fontWeight:600, flexShrink:0 },
  liveDot:      { display:'inline-block', width:'7px', height:'7px', borderRadius:'50%', background:'var(--green)', boxShadow:'0 0 6px var(--green)', animation:'pulse 1.4s ease-in-out infinite', flexShrink:0 },

  card:  { background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'12px', padding:'24px' },
  field: { marginBottom:'20px' },
  label: { display:'block', fontSize:'11px', fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'10px' },

  dropZone: { display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'8px', padding:'36px 24px', borderRadius:'10px', border:'1.5px dashed', cursor:'pointer', transition:'all 0.2s ease', userSelect:'none' },
  uploadIcon:{ width:'42px', height:'42px', borderRadius:'10px', background:'var(--surface-3)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'20px', color:'var(--text-muted)', marginBottom:'4px' },
  fileIcon:  { fontSize:'28px', marginBottom:'4px' },
  dropText:  { fontSize:'14px', fontWeight:600, color:'var(--text)' },
  dropHint:  { fontSize:'12px', color:'var(--text-muted)' },
  dropError: { fontSize:'12px', color:'var(--red)', marginTop:'4px' },

  btnRow:     { display:'flex', gap:'10px', alignItems:'center' },
  btn:        { display:'inline-flex', alignItems:'center', gap:'8px', padding:'9px 20px', fontSize:'13px', fontWeight:600, borderRadius:'8px', border:'none', cursor:'pointer' },
  btnPrimary: { background:'var(--accent)', color:'#fff', boxShadow:'0 0 16px rgba(139,92,246,0.3)' },
  btnDanger:  { background:'var(--red-dim)', color:'var(--red)', border:'1px solid rgba(239,68,68,0.25)' },
  btnGhost:   { background:'var(--surface-2)', color:'var(--text-muted)', border:'1px solid var(--border)' },
  spinner:    { display:'inline-block', width:'13px', height:'13px', border:'2px solid rgba(255,255,255,0.25)', borderTop:'2px solid #fff', borderRadius:'50%', animation:'spin 0.7s linear infinite', flexShrink:0 },

  errorBanner: { marginTop:'16px', padding:'12px 16px', borderRadius:'8px', background:'var(--red-dim)', border:'1px solid rgba(239,68,68,0.2)', color:'var(--red)', fontSize:'13px' },

  feedHeader: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'14px' },
  feedTitle:  { fontSize:'13px', fontWeight:700, color:'var(--text)', textTransform:'uppercase', letterSpacing:'0.06em' },
  feedBadge:  { fontSize:'11px', color:'var(--text-muted)', background:'var(--surface-2)', border:'1px solid var(--border)', padding:'2px 10px', borderRadius:'999px' },
  feed:       { display:'flex', flexDirection:'column', gap:'5px', maxHeight:'400px', overflowY:'auto' },

  eventRow:  { display:'flex', alignItems:'center', gap:'10px', padding:'9px 14px', borderRadius:'7px', border:'1px solid', fontSize:'13px', animation:'fadeIn 0.15s ease' },
  eventIcon: { fontSize:'13px', fontWeight:700, width:'16px', textAlign:'center', flexShrink:0, fontFamily:'monospace' },
  eventMsg:  { flex:1, fontWeight:500 },
  eventTime: { fontSize:'11px', color:'var(--text-dim)', flexShrink:0, fontVariantNumeric:'tabular-nums' },
  pdfLink:   { marginLeft:'12px', color:'var(--accent)', textDecoration:'none', fontWeight:600, fontSize:'12px' },

  workingRow:  { display:'flex', alignItems:'center', gap:'10px', padding:'9px 14px' },
  workingDot:  { display:'inline-block', width:'8px', height:'8px', borderRadius:'50%', background:'var(--accent)', animation:'pulse 1.2s ease-in-out infinite', flexShrink:0 },
  workingText: { fontSize:'13px', color:'var(--text-muted)', fontStyle:'italic' },

  summaryHead:  { display:'flex', alignItems:'center', gap:'10px', marginBottom:'16px' },
  doneIcon:     { fontSize:'18px', color:'var(--accent)' },
  summaryTitle: { fontSize:'15px', fontWeight:700, color:'var(--text)' },
  summaryCards: { display:'flex', gap:'12px' },
  summaryCard:  { flex:1, display:'flex', flexDirection:'column', alignItems:'center', padding:'16px', borderRadius:'10px' },
  summaryCount: { fontSize:'32px', fontWeight:800, lineHeight:1, letterSpacing:'-1px' },
  summaryLabel: { marginTop:'6px', fontSize:'11px', fontWeight:600, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.06em' },
  summaryHint:  { margin:'16px 0 0', fontSize:'13px', color:'var(--text-muted)' },
  link:         { color:'var(--accent)', textDecoration:'none', fontWeight:600 },

  applyToggleRow:   { marginBottom:'20px' },
  applyToggleLabel: { display:'flex', alignItems:'center', gap:'12px', cursor:'pointer', userSelect:'none' },
  track:            { position:'relative', width:'40px', height:'22px', borderRadius:'11px', cursor:'pointer', transition:'background 0.2s, box-shadow 0.2s', flexShrink:0 },
  knob:             { position:'absolute', top:'2px', width:'18px', height:'18px', borderRadius:'50%', background:'#fff', boxShadow:'0 1px 4px rgba(0,0,0,0.3)', transition:'transform 0.2s' },
  applyToggleText:  { fontSize:'13px', fontWeight:600, color:'var(--text)' },
  applyWarning:     { marginTop:'8px', padding:'10px 14px', borderRadius:'8px', background:'rgba(245,158,11,0.08)', border:'1px solid rgba(245,158,11,0.2)', color:'#fbbf24', fontSize:'12px', lineHeight:1.5 },
}
