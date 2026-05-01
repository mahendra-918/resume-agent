import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useState, useRef, useCallback } from 'react'
import Navbar from './components/Navbar'
import RunPage from './pages/RunPage'
import SettingsPage from './pages/SettingsPage'
import HistoryPage from './pages/HistoryPage'
import TrackingPage from './pages/TrackingPage'
import './App.css'

// ── Shared run state lives here so it survives page navigation ────────────────
// RunPage reads/writes this. StatusPage reads `isRunning` to enable auto-refresh.
export function useRunState() {
  // This is exported so pages import it from App — but actually we pass it as
  // props to avoid context boilerplate. See below.
}

function App() {
  // ── Live run state (persists across navigation) ──────────────────────────
  const [runEvents,  setRunEvents]  = useState([])    // activity feed events
  const [runSummary, setRunSummary] = useState(null)  // final summary when done
  const [isRunning,  setIsRunning]  = useState(false) // is pipeline active?
  const [runError,   setRunError]   = useState(null)  // error if pipeline crashed
  const wsRef = useRef(null)                           // live WebSocket

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
      <Navbar isRunning={isRunning} />
      <Routes>
        <Route path="/"        element={<HistoryPage isRunning={isRunning} />} />
        <Route path="/run"     element={<RunPage {...runProps} />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/tracker" element={<TrackingPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
