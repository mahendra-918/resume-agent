import { useState, useEffect } from 'react'

const STORAGE_KEY = 'resumeAgentSettings'

const DEFAULTS = {
  jobLocation:        'Bangalore, India',
  jobType:            'internship',
  maxApplications:    20,
  minRelevanceScore:  0.6,
  resultsPerPlatform: 20,
  useLinkedIn:        true,
  useInternshala:     true,
  useNaukri:          true,
  useWellfound:       true,
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS }
  } catch { return { ...DEFAULTS } }
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div style={s.section}>
      <div style={s.sectionTitle}>{title}</div>
      {children}
    </div>
  )
}

// ── Toggle switch ─────────────────────────────────────────────────────────────

function Toggle({ checked, onChange, label }) {
  return (
    <label style={s.toggleWrap}>
      <div
        role="switch"
        aria-checked={checked}
        tabIndex={0}
        style={{ ...s.track, background: checked ? 'var(--accent)' : 'var(--surface-3)', boxShadow: checked ? '0 0 8px rgba(139,92,246,0.4)' : 'none' }}
        onClick={() => onChange(!checked)}
        onKeyDown={e => (e.key === ' ' || e.key === 'Enter') && onChange(!checked)}
      >
        <div style={{ ...s.knob, transform: checked ? 'translateX(20px)' : 'translateX(2px)' }} />
      </div>
      <span style={s.toggleLabel}>{label}</span>
    </label>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [settings,    setSettings]    = useState(loadSettings)
  const [saved,       setSaved]       = useState(false)
  const [llmProvider, setLlmProvider] = useState('groq')
  const [groqKey,     setGroqKey]     = useState('')
  const [geminiKey,   setGeminiKey]   = useState('')
  const [llmSaved,    setLlmSaved]    = useState(false)
  const [llmError,    setLlmError]    = useState('')
  const [llmLoading,  setLlmLoading]  = useState(false)
  const [liEmail,     setLiEmail]     = useState('')
  const [liPassword,  setLiPassword]  = useState('')
  const [liSaved,     setLiSaved]     = useState(false)
  const [liError,     setLiError]     = useState('')
  const [liLoading,   setLiLoading]   = useState(false)

  useEffect(() => {
    fetch('/api/config/llm')
      .then(r => r.json())
      .then(d => { setLlmProvider(d.llm_provider || 'groq'); setGroqKey(d.groq_api_key || ''); setGeminiKey(d.gemini_api_key || '') })
      .catch(() => {})
    fetch('/api/config/linkedin')
      .then(r => r.json())
      .then(d => { setLiEmail(d.linkedin_email === 'set' ? '••••••••' : ''); setLiPassword(d.linkedin_password === 'set' ? '••••••••' : '') })
      .catch(() => {})
  }, [])

  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)) }, [settings])

  function set(key, value) { setSettings(prev => ({ ...prev, [key]: value })) }

  async function handleSaveLLM() {
    setLlmLoading(true); setLlmError('')
    try {
      const res = await fetch('/api/config/llm', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ llm_provider: llmProvider, groq_api_key: groqKey, gemini_api_key: geminiKey }),
      })
      if (!res.ok) throw new Error(await res.text())
      setLlmSaved(true); setTimeout(() => setLlmSaved(false), 2500)
    } catch (e) { setLlmError(e.message || 'Failed to save') }
    finally { setLlmLoading(false) }
  }

  async function handleSaveLinkedIn() {
    if (!liEmail || liEmail === '••••••••' || !liPassword || liPassword === '••••••••') {
      setLiError('Enter new values to update credentials'); return
    }
    setLiLoading(true); setLiError('')
    try {
      const res = await fetch('/api/config/linkedin', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ linkedin_email: liEmail, linkedin_password: liPassword }),
      })
      if (!res.ok) throw new Error(await res.text())
      setLiSaved(true); setTimeout(() => setLiSaved(false), 2500)
      setLiEmail('••••••••'); setLiPassword('••••••••')
    } catch (e) { setLiError(e.message || 'Failed to save') }
    finally { setLiLoading(false) }
  }

  function handleSave() { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); setSaved(true); setTimeout(() => setSaved(false), 2500) }
  function handleReset() { setSettings({ ...DEFAULTS }) }

  const providers = [
    { id:'groq',   label:'Groq',   sub:'llama-3.3-70b · fast',         href:'https://console.groq.com/keys' },
    { id:'gemini', label:'Gemini', sub:'gemini-2.0-flash · free tier',  href:'https://aistudio.google.com/apikey' },
    { id:'ollama', label:'Ollama', sub:'llama3.2:3b · local, no limits', href:'https://ollama.com' },
  ]

  return (
    <div style={s.page}>
      <div style={s.pageHeader}>
        <h1 style={s.title}>Settings</h1>
        <p style={s.subtitle}>Configure your AI provider, job search preferences, and platforms.</p>
      </div>

      {/* ── AI Provider ──────────────────────────────────────────── */}
      <Section title="AI Provider">
        {llmSaved && <div style={s.successBanner}>✓ AI provider saved</div>}
        {llmError && <div style={s.errorBanner}>{llmError}</div>}

        <div style={s.providerGrid}>
          {providers.map(p => (
            <div
              key={p.id}
              onClick={() => setLlmProvider(p.id)}
              style={{ ...s.providerCard, ...(llmProvider === p.id ? s.providerActive : {}) }}
            >
              <div style={s.radioWrap}>
                <div style={{ ...s.radioOuter, borderColor: llmProvider === p.id ? 'var(--accent)' : 'var(--border)' }}>
                  {llmProvider === p.id && <div style={s.radioInner} />}
                </div>
              </div>
              <div>
                <div style={{ ...s.providerName, color: llmProvider === p.id ? 'var(--text)' : 'var(--text-muted)' }}>{p.label}</div>
                <div style={s.providerSub}>{p.sub}</div>
              </div>
            </div>
          ))}
        </div>

        {llmProvider !== 'ollama' && (
          <div style={s.keyGrid}>
            <div style={s.field}>
              <label style={s.label}>
                Groq API Key
                <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" style={s.getKey}>Get key ↗</a>
              </label>
              <input type="password" value={groqKey} onChange={e => setGroqKey(e.target.value)} placeholder="gsk_…" style={s.input} />
            </div>
            <div style={s.field}>
              <label style={s.label}>
                Gemini API Key
                <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" style={s.getKey}>Get key ↗</a>
              </label>
              <input type="password" value={geminiKey} onChange={e => setGeminiKey(e.target.value)} placeholder="AIza…" style={s.input} />
            </div>
          </div>
        )}

        {llmProvider === 'ollama' && (
          <div style={s.ollamaHint}>
            Make sure Ollama is running, then pull a model:<br />
            <code style={s.code}>ollama pull llama3.2:3b</code>
          </div>
        )}

        <button onClick={handleSaveLLM} disabled={llmLoading} style={{ ...s.saveBtn, opacity: llmLoading ? 0.6 : 1, marginTop:'16px' }}>
          {llmLoading ? 'Saving…' : 'Save AI Settings'}
        </button>
      </Section>

      {/* ── Job Search ───────────────────────────────────────────── */}
      <Section title="Job Search">
        {saved && <div style={s.successBanner}>✓ Settings saved</div>}

        <div style={s.field}>
          <label style={s.label}>Location</label>
          <input type="text" value={settings.jobLocation} onChange={e => set('jobLocation', e.target.value)} placeholder="e.g. Bangalore, India" style={s.input} />
        </div>

        <div style={s.field}>
          <label style={s.label}>Job Type</label>
          <select value={settings.jobType} onChange={e => set('jobType', e.target.value)} style={s.select}>
            <option value="internship">Internship</option>
            <option value="full_time">Full Time</option>
            <option value="both">Both</option>
          </select>
        </div>

        <div style={s.twoCol}>
          <div style={s.field}>
            <label style={s.label}>Max Applications</label>
            <input type="number" value={settings.maxApplications} onChange={e => set('maxApplications', Number(e.target.value))} min={1} max={100} style={{ ...s.input, width:'100%' }} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Results / Platform</label>
            <input type="number" value={settings.resultsPerPlatform} onChange={e => set('resultsPerPlatform', Number(e.target.value))} min={1} max={50} style={{ ...s.input, width:'100%' }} />
          </div>
        </div>

        <div style={s.field}>
          <label style={s.label}>
            Min Relevance Score
            <span style={s.sliderVal}>{settings.minRelevanceScore.toFixed(1)}</span>
          </label>
          <input type="range" value={settings.minRelevanceScore} onChange={e => set('minRelevanceScore', parseFloat(e.target.value))} min={0} max={1} step={0.1} style={s.slider} />
          <div style={s.sliderTicks}>
            {[0.0, 0.2, 0.4, 0.6, 0.8, 1.0].map(v => (
              <span key={v} style={{ ...s.tick, color: v === Math.round(settings.minRelevanceScore * 10) / 10 ? 'var(--accent)' : 'var(--text-dim)' }}>{v.toFixed(1)}</span>
            ))}
          </div>
        </div>

        <div style={{ display:'flex', gap:'8px', marginTop:'20px' }}>
          <button onClick={handleSave} style={s.saveBtn}>Save Settings</button>
          <button onClick={handleReset} style={s.ghostBtn}>Reset</button>
        </div>
      </Section>

      {/* ── LinkedIn Credentials ─────────────────────────────────── */}
      <Section title="LinkedIn Credentials">
        {liSaved && <div style={s.successBanner}>✓ LinkedIn credentials saved</div>}
        {liError && <div style={s.errorBanner}>{liError}</div>}
        <p style={{ margin:'0 0 16px', fontSize:'13px', color:'var(--text-muted)', lineHeight:1.6 }}>
          Required for LinkedIn Easy Apply. Credentials are stored in your local <code style={s.code}>.env</code> file.
        </p>
        <div style={s.keyGrid}>
          <div style={s.field}>
            <label style={s.label}>LinkedIn Email</label>
            <input
              type="email"
              value={liEmail}
              onChange={e => setLiEmail(e.target.value)}
              placeholder="you@example.com"
              style={s.input}
              onFocus={e => { if (e.target.value === '••••••••') setLiEmail('') }}
            />
          </div>
          <div style={s.field}>
            <label style={s.label}>LinkedIn Password</label>
            <input
              type="password"
              value={liPassword}
              onChange={e => setLiPassword(e.target.value)}
              placeholder="••••••••"
              style={s.input}
              onFocus={e => { if (e.target.value === '••••••••') setLiPassword('') }}
            />
          </div>
        </div>
        <button onClick={handleSaveLinkedIn} disabled={liLoading} style={{ ...s.saveBtn, opacity: liLoading ? 0.6 : 1, marginTop:'4px' }}>
          {liLoading ? 'Saving…' : 'Save Credentials'}
        </button>
      </Section>

      {/* ── Platforms ────────────────────────────────────────────── */}
      <Section title="Search Platforms">
        <div style={s.platformGrid}>
          {[
            ['useLinkedIn',    'LinkedIn',    '#60a5fa'],
            ['useInternshala', 'Internshala', '#4ade80'],
            ['useNaukri',      'Naukri',      '#fbbf24'],
            ['useWellfound',   'Wellfound',   '#a78bfa'],
          ].map(([key, label, color]) => (
            <div key={key} style={{ ...s.platformCard, ...(settings[key] ? { borderColor: color + '40', background: color + '08' } : {}) }}>
              <Toggle checked={settings[key]} onChange={v => set(key, v)} label={label} />
              {settings[key] && <div style={{ ...s.platformDot, background: color, boxShadow: `0 0 6px ${color}` }} />}
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page:       { padding:'32px', maxWidth:'720px', margin:'0 auto', animation:'fadeIn 0.2s ease' },
  pageHeader: { marginBottom:'32px' },
  title:      { margin:'0 0 4px', fontSize:'24px', fontWeight:800, color:'var(--text)', letterSpacing:'-0.5px' },
  subtitle:   { margin:0, fontSize:'13px', color:'var(--text-muted)' },

  section:      { background:'var(--surface)', border:'1px solid var(--border)', borderRadius:'12px', padding:'24px', marginBottom:'16px' },
  sectionTitle: { fontSize:'11px', fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'20px', paddingBottom:'12px', borderBottom:'1px solid var(--border)' },

  successBanner: { padding:'10px 14px', borderRadius:'8px', background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)', color:'var(--green)', fontSize:'13px', fontWeight:500, marginBottom:'16px' },
  errorBanner:   { padding:'10px 14px', borderRadius:'8px', background:'var(--red-dim)', border:'1px solid rgba(239,68,68,0.2)', color:'var(--red)', fontSize:'13px', marginBottom:'16px' },

  providerGrid:  { display:'flex', gap:'10px', marginBottom:'20px', flexWrap:'wrap' },
  providerCard:  { display:'flex', alignItems:'flex-start', gap:'10px', padding:'12px 16px', borderRadius:'10px', border:'1px solid var(--border)', cursor:'pointer', flex:'1 1 160px', minWidth:'160px', transition:'all 0.15s' },
  providerActive:{ borderColor:'var(--border-accent)', background:'var(--accent-dim)' },
  radioWrap:     { paddingTop:'2px', flexShrink:0 },
  radioOuter:    { width:'16px', height:'16px', borderRadius:'50%', border:'2px solid', display:'flex', alignItems:'center', justifyContent:'center', transition:'border-color 0.15s' },
  radioInner:    { width:'7px', height:'7px', borderRadius:'50%', background:'var(--accent)' },
  providerName:  { fontSize:'13px', fontWeight:700, marginBottom:'2px', transition:'color 0.15s' },
  providerSub:   { fontSize:'11px', color:'var(--text-dim)' },

  keyGrid: { display:'flex', gap:'14px', flexWrap:'wrap' },
  getKey:  { marginLeft:'8px', fontSize:'11px', color:'var(--accent)', textDecoration:'none', fontWeight:500 },

  ollamaHint: { padding:'14px 16px', borderRadius:'8px', background:'var(--surface-2)', border:'1px solid var(--border)', fontSize:'13px', color:'var(--text-muted)', lineHeight:1.7, marginBottom:'4px' },
  code:       { display:'inline-block', marginTop:'6px', padding:'4px 10px', borderRadius:'5px', background:'var(--surface-3)', color:'var(--accent)', fontSize:'12px', fontFamily:'monospace' },

  field:  { display:'flex', flexDirection:'column', gap:'7px', marginBottom:'16px', flex:1 },
  label:  { fontSize:'11px', fontWeight:700, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.07em', display:'flex', alignItems:'center', gap:'4px' },
  input:  { padding:'9px 12px', fontSize:'13px', borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', outline:'none', width:'100%', boxSizing:'border-box', transition:'border-color 0.15s' },
  select: { padding:'9px 12px', fontSize:'13px', borderRadius:'8px', border:'1px solid var(--border)', background:'var(--surface-2)', color:'var(--text)', cursor:'pointer', width:'200px' },
  twoCol: { display:'flex', gap:'14px', flexWrap:'wrap' },

  sliderVal:   { marginLeft:'auto', color:'var(--accent)', fontWeight:700, fontSize:'13px', fontVariantNumeric:'tabular-nums' },
  slider:      { width:'100%', cursor:'pointer', accentColor:'var(--accent)', height:'4px' },
  sliderTicks: { display:'flex', justifyContent:'space-between', marginTop:'4px' },
  tick:        { fontSize:'10px', transition:'color 0.15s' },

  saveBtn:  { padding:'9px 20px', fontSize:'13px', fontWeight:600, borderRadius:'8px', border:'none', background:'var(--accent)', color:'#fff', cursor:'pointer', boxShadow:'0 0 14px rgba(139,92,246,0.25)' },
  ghostBtn: { padding:'9px 18px', fontSize:'13px', fontWeight:500, borderRadius:'8px', border:'1px solid var(--border)', background:'transparent', color:'var(--text-muted)', cursor:'pointer' },

  platformGrid: { display:'flex', gap:'10px', flexWrap:'wrap' },
  platformCard: { display:'flex', alignItems:'center', gap:'10px', padding:'12px 16px', borderRadius:'10px', border:'1px solid var(--border)', flex:'1 1 140px', minWidth:'140px', transition:'all 0.15s', position:'relative' },
  platformDot:  { width:'6px', height:'6px', borderRadius:'50%', marginLeft:'auto', flexShrink:0 },

  toggleWrap:  { display:'flex', alignItems:'center', gap:'10px', cursor:'pointer', userSelect:'none' },
  track:       { position:'relative', width:'40px', height:'22px', borderRadius:'11px', cursor:'pointer', transition:'background 0.2s, box-shadow 0.2s', flexShrink:0 },
  knob:        { position:'absolute', top:'2px', width:'18px', height:'18px', borderRadius:'50%', background:'#fff', boxShadow:'0 1px 4px rgba(0,0,0,0.3)', transition:'transform 0.2s' },
  toggleLabel: { fontSize:'13px', fontWeight:600, color:'var(--text)' },
}
