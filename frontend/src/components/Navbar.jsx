import { NavLink } from 'react-router-dom'

export default function Navbar() {
  return (
    <nav style={styles.nav}>
      <span style={styles.brand}>Resume Agent</span>
      <div style={styles.links}>
        <NavLink
          to="/"
          end
          style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
        >
          Dashboard
        </NavLink>
        <NavLink
          to="/run"
          style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
        >
          New Run
        </NavLink>
        <NavLink
          to="/settings"
          style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
        >
          Settings
        </NavLink>
      </div>
    </nav>
  )
}

const styles = {
  nav: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    height: '56px',
    borderBottom: '1px solid #e5e7eb',
    background: '#fff',
    fontFamily: 'system-ui, sans-serif',
  },
  brand: {
    fontSize: '16px',
    fontWeight: 700,
    color: '#111827',
    letterSpacing: '-0.3px',
  },
  links: {
    display: 'flex',
    gap: '4px',
  },
  link: {
    padding: '6px 14px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: 500,
    color: '#6b7280',
    textDecoration: 'none',
    transition: 'color 0.15s, background 0.15s',
  },
  activeLink: {
    color: '#6366f1',
    background: '#eef2ff',
  },
}
