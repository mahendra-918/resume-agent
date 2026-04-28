import { useEffect, useRef, useState } from 'react'
import { startRun, openRunSocket, uploadResume } from '../api'

// ── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'resumeAgentSettings'

const EVENT_STYLE = {
  node_done: { icon: '✅', color: '#065f46', bg: '#d1fae5' },
  applied:   { icon: '🎯', color: '#1e40af', bg: '#dbeafe' },
  skipped:   { icon: '⊘',  color: '#854d0e', bg: '#fef9c3' },
  failed:    { icon: '❌', color: '#991b1b', bg: '#fee2e2' },
  error:     { icon: '🚨', color: '#991b1b', bg: '#fee2e2' },
  done:      { icon: '🏁', color: '#4c1d95', bg: '#ede9fe' },
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function fmtTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-IN', { hour12: false })
}

function eventMessage(ev) {
  if (ev.type === 'applied') {
    const label = { applied: 'Applied', skipped: 'Skipped', failed: 'Failed' }[ev.status] ?? ev.status
    return `${label} — ${ev.job} @ ${ev.company}`
  }
  if (ev.type === 'done') {
    const s = ev.summary || {}
    return `Run complete — ${s.applied ?? 0} applied · ${s.skipped ?? 0} skipped · ${s.failed ?? 0} failed`
  }
  return ev.message || ev.node || 'Event received'
}

// ── Sub-components ───────────────────────────────────────────────────────────

function EventRow({ ev }) {
  const style = EVENT_STYLE[ev.type] ?? EVENT_STYLE.node_done
  
  let pdfUrl = null
  if (ev.file_path) {
    const filename = ev.file_path.split(/[/\\]/).pop()
    pdfUrl = `/tailored/${filename}`
  }

  return (
    <div style={{ ...s.eventRow, background: style.bg }}>
      <span style={s.eventIcon}>{style.icon}</span>
      <span style={{ ...s.eventMsg, color: style.color }}>
        {eventMessage(ev)}
        {pdfUrl && (
          <a href={pdfUrl} target="_blank" rel="noreferrer" style={{ marginLeft: '12px', color: '#4f46e5', textDecoration: 'none', fontWeight: 600 }}>
            [📄 View PDF]
          </a>
        )}
      </span>
      <span style={s.eventTime}>{fmtTime(ev.ts)}</span>
    </div>
  )
}

function SummaryCards({ summary }) {
  const cards = [
    { label: 'Applied', value: summary.applied ?? 0, color: '#065f46', bg: '#d1fae5' },
    { label: 'Skipped', value: summary.skipped ?? 0, color: '#854d0e', bg: '#fef9c3' },
    { label: 'Failed',  value: summary.failed  ?? 0, color: '#991b1b', bg: '#fee2e2' },
  ]
  return (
    <div style={s.summaryCards}>
      {cards.map(c => (
        <div key={c.label} style={{ ...s.summaryCard, background: c.bg }}>
          <span style={{ ...s.summaryCount, color: c.color }}>{c.value}</span>
          <span style={{ ...s.summaryLabel, color: c.color }}>{c.label}</span>
        </div>
      ))}
    </div>
  )
}

// ── FileDropZone component ───────────────────────────────────────────────────

function FileDropZone({ uploadedName, isDragging, uploading, uploadError, disabled, onDrop, onDragOver, onDragLeave }) {
  const inputRef = useRef(null)

  function handleFiles(files) {
    if (files && files[0]) onDrop(files[0])
  }

  return (
    <div
      style={{
        ...s.dropZone,
        borderColor: isDragging ? '#6366f1' : uploadedName ? '#10b981' : '#d1d5db',
        background:  isDragging ? '#eef2ff' : uploadedName ? '#f0fdf4' : '#f9fafb',
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : 'auto',
      }}
      onDragOver={e => { e.preventDefault(); onDragOver() }}
      onDragLeave={onDragLeave}
      onDrop={e => { e.preventDefault(); onDragLeave(); handleFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.md"
        style={{ display: 'none' }}
        onChange={e => handleFiles(e.target.files)}
      />

      {uploading ? (
        <><span style={s.spinner} /> <span style={s.dropText}>Uploading…</span></>
      ) : uploadedName ? (
        <>
          <span style={{ fontSize: '20px' }}>✅</span>
          <span style={{ ...s.dropText, color: '#065f46', fontWeight: 600 }}>{uploadedName}</span>
          <span style={s.dropHint}>Click or drag to replace</span>
        </>
      ) : (
        <>
          <span style={{ fontSize: '28px' }}>📄</span>
          <span style={s.dropText}>Drag & drop your resume here</span>
          <span style={s.dropHint}>or click to browse · PDF, DOCX, MD</span>
        </>
      )}

      {uploadError && <span style={s.dropError}>{uploadError}</span>}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
// All run state comes from App.jsx via props — survives navigation.

export default function RunPage({
  runEvents, setRunEvents,
  runSummary, setRunSummary,
  isRunning, setIsRunning,
  runError, setRunError,
  wsRef,
  resetRun,
}) {
  // We still need a local resumePath and dryRun for the form inputs
  const feedRef = useRef(null)

  // Read persisted form values from localStorage
  const settings = loadSettings() || {}
  const defaultPath = './Mahendra_Kasula_Resume.pdf'

  // Local form state
  const [uploadedPath, setUploadedPath] = useState(settings.resumePath || '')
  const [uploadedName, setUploadedName] = useState(
    settings.resumePath ? settings.resumePath.split('/').pop() : ''
  )
  const [isDragging, setIsDragging]   = useState(false)
  const [uploading, setUploading]     = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const dryRunRef = useRef(true)

  // Auto-scroll feed to bottom when new events arrive
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [runEvents])

  async function handleSubmit(e) {
    e.preventDefault()
    if (isRunning) return

    // Clear previous run's data
    setRunEvents([])
    setRunSummary(null)
    setRunError(null)
    setIsRunning(true)

    const resumePath = uploadedPath
    const dryRun     = dryRunRef.current

    if (!resumePath) {
      setRunError('Please upload a resume file first.')
      setIsRunning(false)
      return
    }

    try {
      const result = await startRun({
        resumePath,
        dryRun,
        settings: loadSettings(),
      })
      const { run_id } = result

      wsRef.current = openRunSocket(
        run_id,
        (ev) => {
          setRunEvents(prev => [...prev, ev])
          if (ev.type === 'done') {
            setRunSummary(ev.summary)
            setIsRunning(false)
            wsRef.current?.close()
            wsRef.current = null
          }
          if (ev.type === 'error') {
            setRunError(ev.message)
            setIsRunning(false)
            wsRef.current?.close()
            wsRef.current = null
          }
        },
        () => setIsRunning(false)
      )
    } catch (err) {
      setRunError(err.message)
      setIsRunning(false)
    }
  }

  function handleStop() {
    wsRef.current?.close()
    wsRef.current = null
    setIsRunning(false)
    setRunEvents(prev => [...prev, {
      type: 'error',
      message: 'Run stopped by user',
      ts: new Date().toISOString(),
    }])
  }

  return (
    <div style={s.page}>
      <h1 style={s.title}>Start a Run</h1>
      <p style={s.subtitle}>
        The agent will search jobs, tailor your resume, and apply automatically.
        {isRunning && <strong style={{ color: '#6366f1' }}> Agent is active — you can safely browse other pages.</strong>}
      </p>

      {/* ── Form ───────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} style={s.form}>
        <div style={s.field}>
          <label style={s.label}>Resume</label>
          <FileDropZone
            uploadedName={uploadedName}
            isDragging={isDragging}
            uploading={uploading}
            uploadError={uploadError}
            disabled={isRunning}
            onDrop={async (file) => {
              setUploadError(null)
              setUploading(true)
              try {
                const result = await uploadResume(file)
                setUploadedPath(result.path)
                setUploadedName(result.filename)
              } catch (err) {
                setUploadError(err.message)
              } finally {
                setUploading(false)
              }
            }}
            onDragOver={() => setIsDragging(true)}
            onDragLeave={() => setIsDragging(false)}
          />
        </div>

        <div style={s.checkboxRow}>
          <input
            id="dryRun"
            type="checkbox"
            defaultChecked={dryRunRef.current}
            onChange={e => { dryRunRef.current = e.target.checked }}
            disabled={isRunning}
            style={s.checkbox}
          />
          <label htmlFor="dryRun" style={s.checkboxLabel}>
            Dry Run
            <span style={s.checkboxHint}> — tailor but don't submit anything</span>
          </label>
        </div>

        <div style={s.buttonRow}>
          <button
            type="submit"
            disabled={isRunning}
            style={{ ...s.btn, ...s.btnPrimary, opacity: isRunning ? 0.6 : 1 }}
          >
            {isRunning
              ? <><span style={s.spinner} /> Running…</>
              : '▶ Start Run'
            }
          </button>

          {isRunning && (
            <button type="button" onClick={handleStop} style={{ ...s.btn, ...s.btnDanger }}>
              ■ Stop
            </button>
          )}

          {(runEvents.length > 0 || runSummary) && !isRunning && (
            <button type="button" onClick={resetRun} style={{ ...s.btn, ...s.btnGhost }}>
              ✕ Clear
            </button>
          )}
        </div>

        {runError && <div style={s.errorBanner}>{runError}</div>}
      </form>

      {/* ── Live Activity Feed ──────────────────────────────────── */}
      {runEvents.length > 0 && (
        <div style={s.feedSection}>
          <div style={s.feedHeader}>
            <span style={s.feedTitle}>
              {isRunning ? '⚡ Live Activity' : '📋 Run Log'}
            </span>
            <span style={s.feedCount}>{runEvents.length} events</span>
          </div>

          <div style={s.feed} ref={feedRef}>
            {runEvents.map((ev, i) => <EventRow key={i} ev={ev} />)}

            {isRunning && (
              <div style={s.workingRow}>
                <span style={s.pulse} />
                <span style={s.workingText}>Agent is working…</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Summary ─────────────────────────────────────────────── */}
      {runSummary && (
        <div style={s.summarySection}>
          <p style={s.summaryTitle}>🏁 Run Complete</p>
          <SummaryCards summary={runSummary} />
          <p style={s.summaryHint}>
            View all applications on the{' '}
            <a href="/" style={s.link}>Status page</a>.
          </p>
        </div>
      )}
    </div>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────

const s = {
  page:     { padding: '32px', fontFamily: "'Inter', system-ui, sans-serif", maxWidth: '680px', margin: '0 auto' },
  title:    { margin: '0 0 6px', fontSize: '26px', fontWeight: 700, color: '#111827' },
  subtitle: { margin: '0 0 28px', fontSize: '14px', color: '#6b7280', lineHeight: 1.5 },
  form:     { display: 'flex', flexDirection: 'column', gap: '20px' },
  field:    { display: 'flex', flexDirection: 'column', gap: '6px' },
  label:    { fontSize: '13px', fontWeight: 600, color: '#374151', textTransform: 'uppercase', letterSpacing: '0.05em' },
  input:    { padding: '10px 14px', fontSize: '14px', borderRadius: '8px', border: '1.5px solid #d1d5db', outline: 'none', width: '100%', boxSizing: 'border-box', fontFamily: 'inherit' },
  hint:     { margin: 0, fontSize: '12px', color: '#9ca3af' },
  checkboxRow: { display: 'flex', alignItems: 'center', gap: '10px' },
  checkbox:    { width: '16px', height: '16px', accentColor: '#6366f1', cursor: 'pointer' },
  checkboxLabel: { fontSize: '14px', fontWeight: 500, color: '#374151', cursor: 'pointer' },
  checkboxHint:  { fontWeight: 400, color: '#9ca3af' },
  buttonRow: { display: 'flex', gap: '10px', alignItems: 'center' },
  btn: { display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 22px', fontSize: '14px', fontWeight: 600, borderRadius: '8px', border: 'none', cursor: 'pointer', fontFamily: 'inherit' },
  btnPrimary: { background: '#6366f1', color: '#fff' },
  btnDanger:  { background: '#fee2e2', color: '#dc2626' },
  btnGhost:   { background: '#f3f4f6', color: '#374151' },
  spinner:    { display: 'inline-block', width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.4)', borderTop: '2px solid #fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' },
  errorBanner: { padding: '12px 16px', borderRadius: '8px', background: '#fee2e2', color: '#991b1b', fontSize: '14px' },
  feedSection: { marginTop: '32px' },
  feedHeader:  { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' },
  feedTitle:   { fontSize: '15px', fontWeight: 700, color: '#111827' },
  feedCount:   { fontSize: '12px', color: '#6b7280', background: '#f3f4f6', padding: '2px 10px', borderRadius: '999px' },
  feed:        { display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '420px', overflowY: 'auto', padding: '4px 0' },
  eventRow:    { display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 14px', borderRadius: '8px', fontSize: '13px', animation: 'fadeIn 0.2s ease' },
  eventIcon:   { fontSize: '16px', flexShrink: 0 },
  eventMsg:    { flex: 1, fontWeight: 500 },
  eventTime:   { fontSize: '11px', color: '#9ca3af', flexShrink: 0, fontVariantNumeric: 'tabular-nums' },
  workingRow:  { display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 14px' },
  pulse:       { display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#6366f1', animation: 'pulse 1.2s ease-in-out infinite' },
  workingText: { fontSize: '13px', color: '#6b7280', fontStyle: 'italic' },
  summarySection: { marginTop: '28px', padding: '20px', borderRadius: '12px', border: '1.5px solid #e5e7eb', background: '#f9fafb' },
  summaryTitle:   { margin: '0 0 16px', fontSize: '16px', fontWeight: 700, color: '#111827' },
  summaryCards:   { display: 'flex', gap: '12px' },
  summaryCard:    { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px', borderRadius: '8px' },
  summaryCount:   { fontSize: '32px', fontWeight: 800, lineHeight: 1 },
  summaryLabel:   { marginTop: '4px', fontSize: '13px', fontWeight: 600 },
  summaryHint:    { margin: '16px 0 0', fontSize: '13px', color: '#6b7280' },
  link:           { color: '#6366f1', textDecoration: 'none', fontWeight: 500 },
  dropZone: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    gap: '6px', padding: '28px 16px', borderRadius: '12px', border: '2px dashed #d1d5db',
    cursor: 'pointer', transition: 'all 0.2s ease', userSelect: 'none',
  },
  dropText:  { fontSize: '14px', fontWeight: 600, color: '#374151' },
  dropHint:  { fontSize: '12px', color: '#9ca3af' },
  dropError: { fontSize: '12px', color: '#dc2626', marginTop: '4px' },
}
