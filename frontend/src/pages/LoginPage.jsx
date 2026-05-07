import { useState } from 'react'
import { register, loginUser, setStoredToken } from '../api'

export default function LoginPage({ onLogin }) {
  const [tab, setTab]           = useState('login')  // 'login' | 'signup'
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  function switchTab(t) {
    setTab(t); setError(''); setEmail(''); setPassword(''); setConfirm('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (tab === 'signup') {
      if (password !== confirm) { setError('Passwords do not match'); return }
      if (password.length < 6)  { setError('Password must be at least 6 characters'); return }
    }

    setLoading(true)
    try {
      const fn = tab === 'signup' ? register : loginUser
      const { token, email: userEmail } = await fn(email, password)
      setStoredToken(token)
      onLogin({ token, email: userEmail })
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.overlay}>
      <form onSubmit={handleSubmit} style={s.card}>

        {/* Brand */}
        <div style={s.brand}>
          <span style={s.brandIcon}>⚡</span>
          <span style={s.brandText}>ResumeAgent</span>
        </div>

        {/* Tabs */}
        <div style={s.tabs}>
          <button type="button" style={{ ...s.tab, ...(tab === 'login'  ? s.activeTab : {}) }} onClick={() => switchTab('login')}>Sign In</button>
          <button type="button" style={{ ...s.tab, ...(tab === 'signup' ? s.activeTab : {}) }} onClick={() => switchTab('signup')}>Sign Up</button>
        </div>

        {/* Fields */}
        <div style={s.fields}>
          <input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={s.input}
            required
            autoFocus
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={s.input}
            required
          />
          {tab === 'signup' && (
            <input
              type="password"
              placeholder="Confirm password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              style={s.input}
              required
            />
          )}
        </div>

        {error && <p style={s.error}>{error}</p>}

        <button type="submit" disabled={loading || !email || !password} style={s.btn}>
          {loading ? '…' : tab === 'signup' ? 'Create account' : 'Sign in'}
        </button>

        <p style={s.hint}>
          {tab === 'login'
            ? <>No account? <span style={s.link} onClick={() => switchTab('signup')}>Sign up</span></>
            : <>Have an account? <span style={s.link} onClick={() => switchTab('login')}>Sign in</span></>
          }
        </p>
      </form>
    </div>
  )
}

const s = {
  overlay: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#0f1117',
  },
  card: {
    background: '#1a1d2e',
    border: '1px solid #2a2d3e',
    borderRadius: 16,
    padding: '40px 36px',
    width: 380,
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  brand: { display: 'flex', alignItems: 'center', gap: 10 },
  brandIcon: { fontSize: 28 },
  brandText: { fontSize: 22, fontWeight: 700, color: '#e2e8f0' },
  tabs: {
    display: 'flex',
    background: '#0f1117',
    borderRadius: 8,
    padding: 4,
    gap: 4,
  },
  tab: {
    flex: 1,
    padding: '8px 0',
    borderRadius: 6,
    border: 'none',
    background: 'transparent',
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
  },
  activeTab: {
    background: '#1e2235',
    color: '#e2e8f0',
  },
  fields: { display: 'flex', flexDirection: 'column', gap: 10 },
  input: {
    padding: '11px 14px',
    borderRadius: 8,
    border: '1px solid #2a2d3e',
    background: '#0f1117',
    color: '#e2e8f0',
    fontSize: 14,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  },
  error: { margin: 0, color: '#f87171', fontSize: 13 },
  btn: {
    padding: '12px',
    borderRadius: 8,
    border: 'none',
    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    color: '#fff',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
  },
  hint: { margin: 0, color: '#64748b', fontSize: 13, textAlign: 'center' },
  link: { color: '#818cf8', cursor: 'pointer' },
}
