import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

const TOKEN_KEY = 'auth_token'

export function getStoredToken() { return localStorage.getItem(TOKEN_KEY) || '' }
export function setStoredToken(t) { localStorage.setItem(TOKEN_KEY, t) }
export function clearStoredToken() { localStorage.removeItem(TOKEN_KEY) }

// Attach stored token to every request
client.interceptors.request.use(config => {
  const token = getStoredToken()
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// On 401, clear token and reload so App re-renders the login page
client.interceptors.response.use(
  res => res,
  err => {
    if (err?.response?.status === 401) {
      clearStoredToken()
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

export async function register(email, password) {
  try {
    const { data } = await client.post('/auth/register', { email, password })
    return data  // { token, email }
  } catch (error) {
    throw new Error(extractMessage(error))
  }
}

export async function loginUser(email, password) {
  try {
    const { data } = await client.post('/auth/login', { email, password })
    return data  // { token, email }
  } catch (error) {
    throw new Error(extractMessage(error))
  }
}

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

export async function startRun({ resumePath, settings }) {
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

export async function applyJob(packageDir) {
  try {
    const { data } = await client.post(`/apply/${packageDir}`)
    return data
  } catch (error) {
    throw new Error(`Failed to start apply: ${extractMessage(error)}`)
  }
}
