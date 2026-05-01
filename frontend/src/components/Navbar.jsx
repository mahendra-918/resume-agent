import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

function usePackageCount() {
  const [count, setCount] = useState(null)

  useEffect(() => {
    function fetchCount() {
      fetch('/api/status')
        .then(r => r.json())
        .then(data => setCount(Array.isArray(data) ? data.length : 0))
        .catch(() => setCount(null))
    }
    fetchCount()
    const id = setInterval(fetchCount, 10000)
    return () => clearInterval(id)
  }, [])

  return count
}

const NAV_LINKS = [
  { to: '/',         label: 'Dashboard', end: true  },
  { to: '/tracker',  label: 'Tracker',   end: false },
  { to: '/run',      label: 'New Run',   end: false },
  { to: '/settings', label: 'Settings',  end: false },
]

export default function Navbar({ isRunning }) {
  const packageCount = usePackageCount()

  return (
    <nav style={styles.nav}>
      {/* Brand */}
      <div style={styles.brand}>
        <div style={styles.brandIcon}>⚡</div>
        <span style={styles.brandText}>ResumeAgent</span>
      </div>

      {/* Links */}
      <div style={styles.links}>
        {NAV_LINKS.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            style={({ isActive }) => ({
              ...styles.link,
              ...(isActive ? styles.activeLink : {}),
            })}
          >
            {label === 'New Run' ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                {isRunning && <span style={styles.liveDot} />}
                {isRunning ? 'Running…' : 'New Run'}
              </span>
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                {label}
                {label === 'Dashboard' && packageCount > 0 && (
                  <span style={styles.badge}>{packageCount}</span>
                )}
              </span>
            )}
          </NavLink>
        ))}
      </div>

      {isRunning && (
        <div style={styles.runningPill}>
          <span style={styles.liveDot} />
          Live
        </div>
      )}
    </nav>
  )
}

const styles = {
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '0 24px',
    height: '52px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginRight: '12px',
  },
  brandIcon: {
    width: '28px',
    height: '28px',
    borderRadius: '8px',
    background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    flexShrink: 0,
    boxShadow: '0 0 12px rgba(124,58,237,0.35)',
  },
  brandText: {
    fontSize: '14px',
    fontWeight: 700,
    color: 'var(--text)',
    letterSpacing: '-0.3px',
  },
  links: {
    display: 'flex',
    gap: '2px',
    flex: 1,
  },
  link: {
    padding: '5px 12px',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-muted)',
    textDecoration: 'none',
    transition: 'color 0.15s, background 0.15s',
    display: 'inline-flex',
    alignItems: 'center',
    whiteSpace: 'nowrap',
  },
  activeLink: {
    color: 'var(--text)',
    background: 'var(--surface-2)',
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '18px',
    height: '18px',
    padding: '0 5px',
    borderRadius: '999px',
    background: 'var(--accent)',
    color: '#fff',
    fontSize: '10px',
    fontWeight: 700,
  },
  liveDot: {
    display: 'inline-block',
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#22c55e',
    flexShrink: 0,
    boxShadow: '0 0 6px #22c55e',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  runningPill: {
    marginLeft: 'auto',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    borderRadius: '999px',
    background: 'rgba(34,197,94,0.1)',
    border: '1px solid rgba(34,197,94,0.2)',
    color: '#22c55e',
    fontSize: '12px',
    fontWeight: 600,
  },
}
