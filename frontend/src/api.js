import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

function extractMessage(error) {
  return error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || 'An unexpected error occurred'
}

export async function getHealth() {
  try {
    const { data } = await client.get('/health')
    return data
  } catch (error) {
    throw new Error(`Health check failed: ${extractMessage(error)}`)
  }
}

export async function startRun({ resumePath, settings, applyEnabled = false }) {
  const s = settings || {}
  try {
    const { data } = await client.post('/run', {
      resume_path: resumePath,
      max_applications: s.maxApplications,
      min_relevance_score: s.minRelevanceScore,
      results_per_platform: s.resultsPerPlatform,
      job_location: s.jobLocation,
      job_type: s.jobType,
      use_linkedin: s.useLinkedIn,
      use_internshala: s.useInternshala,
      use_naukri: s.useNaukri,
      use_wellfound: s.useWellfound,
      apply_enabled: applyEnabled,
    })
    // data = { run_id: "abc-123", status: "started", message: "..." }
    // run_id is what the caller needs to open the WebSocket
    return data
  } catch (error) {
    throw new Error(`Failed to start run: ${extractMessage(error)}`)
  }
}


/**
 * Open a WebSocket connection for a specific pipeline run.
 *
 * The backend pushes JSON events as each node completes:
 *   { type: "node_done", node: "parse_resume", message: "...", ts: "..." }
 *   { type: "applied",   job: "ML Intern", company: "Google", status: "applied", ts: "..." }
 *   { type: "done",      summary: { applied, skipped, failed, total }, ts: "..." }
 *   { type: "error",     message: "...", ts: "..." }
 *
 * @param {string}   runId     - The run_id returned by startRun()
 * @param {function} onEvent   - Called with each parsed event object
 * @param {function} onClose   - Called when the connection closes (optional)
 * @returns {WebSocket}        - The raw WebSocket — call .close() to disconnect
 */
export function openRunSocket(runId, onEvent, onClose) {
  // Build the WebSocket URL from the current page's host so it works both
  // in local dev (Vite proxy → localhost:8000) and in production.
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host                 // e.g. "localhost:5173"
  const url  = `${protocol}//${host}/ws/${runId}`   // e.g. "ws://localhost:5173/ws/abc-123"

  const ws = new WebSocket(url)

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data)  // backend sends JSON strings
      onEvent(event)
    } catch {
      // ignore malformed frames — shouldn't happen but be defensive
    }
  }

  ws.onerror = () => {
    onEvent({ type: 'error', message: 'WebSocket connection error', ts: new Date().toISOString() })
  }

  ws.onclose = () => {
    if (onClose) onClose()
  }

  return ws  // caller can call ws.close() to disconnect early
}

export async function getApplications() {
  try {
    const { data } = await client.get('/status')
    return data
  } catch (error) {
    throw new Error(`Failed to fetch applications: ${extractMessage(error)}`)
  }
}

export async function clearApplications() {
  try {
    const { data } = await client.delete('/applications')
    return data
  } catch (error) {
    throw new Error(`Failed to clear applications: ${extractMessage(error)}`)
  }
}

export async function getApplicationsByPlatform(platform) {
  try {
    const { data } = await client.get(`/status/${platform}`)
    return data
  } catch (error) {
    throw new Error(`Failed to fetch applications for platform "${platform}": ${extractMessage(error)}`)
  }
}

export async function uploadResume(file) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await client.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    // data = { path: "output/resumes/MyResume.pdf", filename: "MyResume.pdf" }
    return data
  } catch (error) {
    throw new Error(`Upload failed: ${extractMessage(error)}`)
  }
}

export async function saveSession(platform, payload) {
  try {
    const { data } = await client.post(`/sessions/${platform}`, payload)
    return data
  } catch (error) {
    throw new Error(`Failed to save session for ${platform}: ${extractMessage(error)}`)
  }
}

export async function deleteSession(platform) {
  try {
    const { data } = await client.delete(`/sessions/${platform}`)
    return data
  } catch (error) {
    throw new Error(`Failed to delete session for ${platform}: ${extractMessage(error)}`)
  }
}

export async function getSessionStatus(platform) {
  try {
    const { data } = await client.get(`/sessions/${platform}`)
    return data // { platform: "linkedin", exists: true }
  } catch (error) {
    throw new Error(`Failed to check session for ${platform}: ${extractMessage(error)}`)
  }
}

export async function startInteractiveLogin(platform) {
  try {
    const { data } = await client.post(`/sessions/${platform}/login_start`)
    return data
  } catch (error) {
    throw new Error(`Failed to start interactive login for ${platform}: ${extractMessage(error)}`)
  }
}

export async function finishInteractiveLogin(platform) {
  try {
    const { data } = await client.post(`/sessions/${platform}/login_finish`)
    return data
  } catch (error) {
    throw new Error(`Failed to finish interactive login for ${platform}: ${extractMessage(error)}`)
  }
}

export async function cancelInteractiveLogin(platform) {
  try {
    const { data } = await client.post(`/sessions/${platform}/login_cancel`)
    return data
  } catch (error) {
    throw new Error(`Failed to cancel interactive login for ${platform}: ${extractMessage(error)}`)
  }
}
