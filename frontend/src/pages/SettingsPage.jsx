import { useState, useEffect } from 'react'
import { saveSession, deleteSession, getSessionStatus, startInteractiveLogin, finishInteractiveLogin, cancelInteractiveLogin } from '../api'

const STORAGE_KEY = 'resumeAgentSettings'

const DEFAULTS = {
  // Job Search Preferences
  jobLocation: 'Bangalore, India',
  jobType: 'internship',
  maxApplications: 20,
  minRelevanceScore: 0.6,
  resultsPerPlatform: 20,
  // Platforms
  useLinkedIn: true,
  useInternshala: true,
  useNaukri: true,
  useWellfound: true,
  // Credentials
  linkedinEmail: '',
  linkedinPassword: '',
  internshalaEmail: '',
  internshalaPassword: '',
  naukriEmail: '',
  naukriPassword: '',
  wellfoundEmail: '',
  wellfoundPassword: '',
  // Agent Behaviour
  headless: true,
  browserSlowMo: 500,
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}
function SessionManager({ platform }) {
  const [sessionJson, setSessionJson] = useState('')
  const [status, setStatus] = useState('checking') // 'checking', 'exists', 'none'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Interactive mode state
  const [isInteractiveMode, setIsInteractiveMode] = useState(false)

  useEffect(() => {
    getSessionStatus(platform).then(data => {
      setStatus(data.exists ? 'exists' : 'none')
    }).catch(err => {
      console.error(err)
      setStatus('none')
    })
  }, [platform])

  async function handleInteractiveStart() {
    setError(null)
    setLoading(true)
    try {
      await startInteractiveLogin(platform)
      setIsInteractiveMode(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleInteractiveFinish() {
    setError(null)
    setLoading(true)
    try {
      await finishInteractiveLogin(platform)
      setIsInteractiveMode(false)
      setStatus('exists')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleInteractiveCancel() {
    setError(null)
    setLoading(true)
    try {
      await cancelInteractiveLogin(platform)
      setIsInteractiveMode(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!sessionJson.trim()) return
    setError(null)
    setLoading(true)
    try {
      let payload
      try {
        payload = JSON.parse(sessionJson)
      } catch (e) {
        throw new Error('Invalid JSON format. Please ensure you are pasting valid JSON.')
      }
      
      await saveSession(platform, payload)
      setStatus('exists')
      setSessionJson('') // clear input on success
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    setError(null)
    setLoading(true)
    try {
      await deleteSession(platform)
      setStatus('none')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.sessionBox}>
      <div style={styles.sessionHeader}>
        <span style={styles.sessionTitle}>Playwright Session State (Cookies)</span>
        {status === 'exists' ? (
          <span style={styles.statusActive}>● Active Session Saved</span>
        ) : (
          <span style={styles.statusNone}>○ No Session Found</span>
        )}
      </div>

      {isInteractiveMode ? (
        <div style={{ padding: '12px', background: '#e0e7ff', borderRadius: '6px', border: '1px solid #c7d2fe', marginTop: '8px' }}>
          <p style={{ margin: '0 0 12px', fontSize: '13px', color: '#3730a3', fontWeight: 500 }}>
            🚀 A visible browser has opened. Please log in manually. Once you are successfully logged in, click the "Save Session" button below.
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={handleInteractiveFinish} disabled={loading} style={{ ...styles.smBtnPrimary, background: '#4338ca' }}>
              {loading ? 'Saving...' : "I'm Logged In - Save Session"}
            </button>
            <button onClick={handleInteractiveCancel} disabled={loading} style={styles.smBtnGhost}>
              Cancel
            </button>
          </div>
          {error && <div style={{ color: '#dc2626', fontSize: '13px', marginTop: '8px' }}>{error}</div>}
        </div>
      ) : (
        <>
          <p style={styles.hint}>
            If automatic login fails (e.g. captchas), you can either launch an interactive browser to log in manually, or paste your exported JSON cookies below.
          </p>
          
          <div style={{ marginBottom: '12px' }}>
            <button onClick={handleInteractiveStart} disabled={loading} style={styles.smBtnPrimary}>
              {loading ? 'Launching...' : '🌐 Launch Browser Login'}
            </button>
          </div>

          <textarea
            style={styles.textarea}
            rows={3}
            placeholder='[ { "name": "li_at", "value": "...", "domain": ".linkedin.com" } ]'
            value={sessionJson}
            onChange={e => setSessionJson(e.target.value)}
          />
          {error && <div style={{ color: '#dc2626', fontSize: '13px', marginTop: '4px' }}>{error}</div>}
          <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
            <button onClick={handleSave} disabled={loading || !sessionJson.trim()} style={styles.smBtnGhost}>
              {loading ? 'Saving...' : 'Save JSON'}
            </button>
            {status === 'exists' && (
              <button onClick={handleClear} disabled={loading} style={styles.smBtnDanger}>
                Clear Session
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default function SettingsPage() {
  const [settings, setSettings] = useState(loadSettings)
  const [showPasswords, setShowPasswords] = useState({
    linkedin: false,
    internshala: false,
    naukri: false,
    wellfound: false,
  })
  const [saved, setSaved] = useState(false)

  // Persist to localStorage on every change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  function set(key, value) {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  function handleSave() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  function handleReset() {
    setSettings({ ...DEFAULTS })
  }

  function togglePassword(platform) {
    setShowPasswords(prev => ({ ...prev, [platform]: !prev[platform] }))
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Settings</h1>

      {saved && (
        <div style={styles.successBanner}>Settings saved successfully.</div>
      )}

      {/* ── Job Search Preferences ─────────────────────────────── */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Job Search Preferences</h2>

        <div style={styles.field}>
          <label style={styles.label} htmlFor="jobLocation">Job Location</label>
          <input
            id="jobLocation"
            type="text"
            value={settings.jobLocation}
            onChange={e => set('jobLocation', e.target.value)}
            placeholder="e.g. Bangalore, India"
            style={styles.input}
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label} htmlFor="jobType">Job Type</label>
          <select
            id="jobType"
            value={settings.jobType}
            onChange={e => set('jobType', e.target.value)}
            style={styles.select}
          >
            <option value="internship">Internship</option>
            <option value="full_time">Full Time</option>
            <option value="both">Both</option>
          </select>
        </div>

        <div style={styles.row}>
          <div style={styles.field}>
            <label style={styles.label} htmlFor="maxApplications">Max Applications</label>
            <input
              id="maxApplications"
              type="number"
              value={settings.maxApplications}
              onChange={e => set('maxApplications', Number(e.target.value))}
              min={1}
              max={100}
              style={{ ...styles.input, width: '120px' }}
            />
          </div>

          <div style={styles.field}>
            <label style={styles.label} htmlFor="resultsPerPlatform">Results Per Platform</label>
            <input
              id="resultsPerPlatform"
              type="number"
              value={settings.resultsPerPlatform}
              onChange={e => set('resultsPerPlatform', Number(e.target.value))}
              min={1}
              max={50}
              style={{ ...styles.input, width: '120px' }}
            />
          </div>
        </div>

        <div style={styles.field}>
          <label style={styles.label} htmlFor="minRelevanceScore">
            Min Relevance Score — <strong>{settings.minRelevanceScore.toFixed(1)}</strong>
          </label>
          <input
            id="minRelevanceScore"
            type="range"
            value={settings.minRelevanceScore}
            onChange={e => set('minRelevanceScore', parseFloat(e.target.value))}
            min={0.0}
            max={1.0}
            step={0.1}
            style={styles.slider}
          />
          <div style={styles.sliderTicks}>
            {[0.0, 0.2, 0.4, 0.6, 0.8, 1.0].map(v => (
              <span key={v} style={styles.tick}>{v.toFixed(1)}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Platforms to Search ────────────────────────────────── */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Platforms to Search</h2>
        <div style={styles.toggleGrid}>
          {[
            ['useLinkedIn', 'LinkedIn'],
            ['useInternshala', 'Internshala'],
            ['useNaukri', 'Naukri'],
            ['useWellfound', 'Wellfound'],
          ].map(([key, label]) => (
            <label key={key} style={styles.toggleLabel}>
              <div
                style={{
                  ...styles.toggle,
                  background: settings[key] ? '#6366f1' : '#d1d5db',
                }}
                onClick={() => set(key, !settings[key])}
                role="switch"
                aria-checked={settings[key]}
                tabIndex={0}
                onKeyDown={e => (e.key === ' ' || e.key === 'Enter') && set(key, !settings[key])}
              >
                <div
                  style={{
                    ...styles.toggleKnob,
                    transform: settings[key] ? 'translateX(20px)' : 'translateX(2px)',
                  }}
                />
              </div>
              <span style={styles.toggleText}>{label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* ── Platform Credentials ───────────────────────────────── */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Platform Credentials</h2>
        <p style={styles.hint}>Credentials are stored in your browser only and never sent to any server except the agent backend.</p>

        {[
          { platform: 'linkedin',    label: 'LinkedIn',    emailKey: 'linkedinEmail',    passKey: 'linkedinPassword' },
          { platform: 'internshala', label: 'Internshala', emailKey: 'internshalaEmail', passKey: 'internshalaPassword' },
          { platform: 'naukri',      label: 'Naukri',      emailKey: 'naukriEmail',      passKey: 'naukriPassword' },
          { platform: 'wellfound',   label: 'Wellfound',   emailKey: 'wellfoundEmail',   passKey: 'wellfoundPassword' },
        ].map(({ platform, label, emailKey, passKey }) => (
          <div key={platform} style={styles.credBlock}>
            <div style={styles.credLabel}>{label}</div>
            <div style={styles.credRow}>
              <div style={{ ...styles.field, flex: 1 }}>
                <label style={styles.label} htmlFor={emailKey}>Email</label>
                <input
                  id={emailKey}
                  type="email"
                  value={settings[emailKey]}
                  onChange={e => set(emailKey, e.target.value)}
                  placeholder={`${label} email`}
                  style={styles.input}
                  autoComplete="off"
                />
              </div>
              <div style={{ ...styles.field, flex: 1 }}>
                <label style={styles.label} htmlFor={passKey}>Password</label>
                <div style={styles.passwordWrapper}>
                  <input
                    id={passKey}
                    type={showPasswords[platform] ? 'text' : 'password'}
                    value={settings[passKey]}
                    onChange={e => set(passKey, e.target.value)}
                    placeholder="••••••••"
                    style={{ ...styles.input, paddingRight: '44px' }}
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={() => togglePassword(platform)}
                    style={styles.eyeBtn}
                    aria-label={showPasswords[platform] ? 'Hide password' : 'Show password'}
                  >
                    {showPasswords[platform] ? '🙈' : '👁'}
                  </button>
                </div>
              </div>
            </div>
            
            {/* Session State Manager */}
            <SessionManager platform={platform} />
          </div>
        ))}
      </section>

      {/* ── Agent Behaviour ────────────────────────────────────── */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Agent Behaviour</h2>

        <label style={styles.toggleLabel}>
          <div
            style={{
              ...styles.toggle,
              background: settings.headless ? '#6366f1' : '#d1d5db',
            }}
            onClick={() => set('headless', !settings.headless)}
            role="switch"
            aria-checked={settings.headless}
            tabIndex={0}
            onKeyDown={e => (e.key === ' ' || e.key === 'Enter') && set('headless', !settings.headless)}
          >
            <div
              style={{
                ...styles.toggleKnob,
                transform: settings.headless ? 'translateX(20px)' : 'translateX(2px)',
              }}
            />
          </div>
          <span style={styles.toggleText}>Headless Browser (run browser invisibly)</span>
        </label>

        <div style={{ ...styles.field, marginTop: '16px' }}>
          <label style={styles.label} htmlFor="browserSlowMo">Browser Slow Mo (ms)</label>
          <input
            id="browserSlowMo"
            type="number"
            value={settings.browserSlowMo}
            onChange={e => set('browserSlowMo', Number(e.target.value))}
            min={0}
            style={{ ...styles.input, width: '140px' }}
          />
        </div>
      </section>

      {/* ── Actions ────────────────────────────────────────────── */}
      <div style={styles.actions}>
        <button onClick={handleSave} style={styles.saveBtn}>
          Save Settings
        </button>
        <button onClick={handleReset} style={styles.resetBtn}>
          Reset to Defaults
        </button>
      </div>
    </div>
  )
}

const styles = {
  page: {
    padding: '32px',
    fontFamily: 'system-ui, sans-serif',
    maxWidth: '680px',
    margin: '0 auto',
  },
  title: {
    margin: '0 0 24px',
    fontSize: '24px',
    fontWeight: 600,
    color: '#111827',
  },
  successBanner: {
    marginBottom: '20px',
    padding: '12px 16px',
    borderRadius: '6px',
    background: '#d1fae5',
    color: '#065f46',
    fontSize: '14px',
  },
  section: {
    marginBottom: '32px',
    padding: '24px',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    background: '#fafafa',
  },
  sectionTitle: {
    margin: '0 0 20px',
    fontSize: '15px',
    fontWeight: 600,
    color: '#374151',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    borderBottom: '1px solid #e5e7eb',
    paddingBottom: '10px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginBottom: '16px',
  },
  row: {
    display: 'flex',
    gap: '24px',
    flexWrap: 'wrap',
  },
  label: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
  },
  input: {
    padding: '8px 12px',
    fontSize: '14px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
    background: '#fff',
  },
  select: {
    padding: '8px 12px',
    fontSize: '14px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    outline: 'none',
    width: '200px',
    background: '#fff',
    cursor: 'pointer',
  },
  slider: {
    width: '100%',
    cursor: 'pointer',
    accentColor: '#6366f1',
  },
  sliderTicks: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '4px',
  },
  tick: {
    fontSize: '11px',
    color: '#9ca3af',
  },
  toggleGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
  },
  toggleLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    cursor: 'pointer',
    userSelect: 'none',
  },
  toggle: {
    position: 'relative',
    width: '44px',
    height: '24px',
    borderRadius: '12px',
    cursor: 'pointer',
    transition: 'background 0.2s',
    flexShrink: 0,
  },
  toggleKnob: {
    position: 'absolute',
    top: '2px',
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    background: '#fff',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
    transition: 'transform 0.2s',
  },
  toggleText: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
  },
  credBlock: {
    marginBottom: '20px',
    paddingBottom: '20px',
    borderBottom: '1px solid #e5e7eb',
  },
  credLabel: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#6366f1',
    marginBottom: '10px',
  },
  credRow: {
    display: 'flex',
    gap: '16px',
    flexWrap: 'wrap',
  },
  passwordWrapper: {
    position: 'relative',
  },
  eyeBtn: {
    position: 'absolute',
    right: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    padding: '0',
    lineHeight: 1,
  },
  hint: {
    fontSize: '12px',
    color: '#9ca3af',
    margin: '-10px 0 16px',
  },
  actions: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
  },
  saveBtn: {
    padding: '10px 24px',
    fontSize: '15px',
    fontWeight: 600,
    borderRadius: '6px',
    border: 'none',
    background: '#6366f1',
    color: '#fff',
    cursor: 'pointer',
  },
  resetBtn: {
    padding: '10px 24px',
    fontSize: '15px',
    fontWeight: 600,
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    background: '#fff',
    color: '#374151',
    cursor: 'pointer',
  },
  sessionBox: {
    marginTop: '16px',
    padding: '16px',
    background: '#f9fafb',
    borderRadius: '8px',
    border: '1px dashed #d1d5db',
  },
  sessionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  sessionTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#4b5563',
  },
  statusActive: {
    fontSize: '12px',
    color: '#059669',
    fontWeight: 600,
  },
  statusNone: {
    fontSize: '12px',
    color: '#9ca3af',
  },
  textarea: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '12px',
    fontFamily: 'monospace',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    outline: 'none',
    boxSizing: 'border-box',
    background: '#fff',
    resize: 'vertical',
  },
  smBtnPrimary: {
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '6px',
    border: 'none',
    background: '#6366f1',
    color: '#fff',
    cursor: 'pointer',
  },
  smBtnDanger: {
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '6px',
    border: '1px solid #fca5a5',
    background: '#fee2e2',
    color: '#991b1b',
    cursor: 'pointer',
  },
  smBtnGhost: {
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    background: '#fff',
    color: '#374151',
    cursor: 'pointer',
  },
}
