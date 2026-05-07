import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useState, useRef, useCallback } from 'react'
import Navbar from './components/Navbar'
import RunPage from './pages/RunPage'
import SettingsPage from './pages/SettingsPage'
import HistoryPage from './pages/HistoryPage'
import TrackingPage from './pages/TrackingPage'
import LoginPage from './pages/LoginPage'
import { getStoredToken, clearStoredToken } from './api'
import './App.css'

function App() {
  const [user, setUser] = useState(() => {
    const token = getStoredToken()
    return token ? { token } : null
  })

  function handleLogin(userData) {
    setUser(userData)
  }

  function handleLogout() {
    clearStoredToken()
    setUser(null)
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} />
  }

  return <AuthenticatedApp user={user} onLogout={handleLogout} />
}

function AuthenticatedApp({ user, onLogout }) {
  const [runEvents,  setRunEvents]  = useState([])
  const [runSummary, setRunSummary] = useState(null)
  const [isRunning,  setIsRunning]  = useState(false)
  const [runError,   setRunError]   = useState(null)
  const wsRef = useRef(null)

  const resetRun = useCallback(() => {
    setRunEvents([])
    setRunSummary(null)
    setRunError(null)
    setIsRunning(false)
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const runProps = {
    runEvents, setRunEvents,
    runSummary, setRunSummary,
    isRunning, setIsRunning,
    runError, setRunError,
    wsRef,
    resetRun,
  }

  return (
    <BrowserRouter>
      <Navbar isRunning={isRunning} user={user} onLogout={onLogout} />
      <Routes>
        <Route path="/"         element={<HistoryPage isRunning={isRunning} />} />
        <Route path="/run"      element={<RunPage {...runProps} />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/tracker"  element={<TrackingPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
