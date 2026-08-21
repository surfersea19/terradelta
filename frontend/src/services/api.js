import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
})

// Add auth token to requests if available
api.interceptors.request.use(config => {
  const token = localStorage.getItem('terradelta_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Auth ──────────────────────────────────────────────────────────────

export const login = async (username, password) => {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  const { data } = await api.post('/auth/token', formData)
  localStorage.setItem('terradelta_token', data.access_token)
  return data
}

export const signup = async (username, password) => {
  const { data } = await api.post('/auth/signup', { username, password })
  return data
}

export const logout = () => {
  localStorage.removeItem('terradelta_token')
}

export const getCurrentUser = async () => {
  const { data } = await api.get('/auth/me')
  return data
}

// ── Saved Areas ───────────────────────────────────────────────────────

export const getSavedAreas = async () => {
  const { data } = await api.get('/monitoring/areas')
  return data
}

export const saveArea = async (name, bbox) => {
  const { data } = await api.post('/monitoring/areas', { name, bbox })
  return data
}

// ── Analysis (F1) ────────────────────────────────────────────────────────────

export const submitAnalysis = (payload) =>
  api.post('/analysis/submit', payload).then(r => r.data)

export const getAnalysisStatus = (jobId) =>
  api.get(`/analysis/status/${jobId}`).then(r => r.data)

export const getAnalysisResult = (jobId) =>
  api.get(`/analysis/result/${jobId}`).then(r => r.data)

export const downloadReport = (jobId) =>
  `${window.location.origin}/api/analysis/download/report/${jobId}`

// ── Explorer (F2) ────────────────────────────────────────────────────────────

export const getExplorerLocations = () =>
  api.get('/explorer/locations').then(r => r.data)

export const getExplorerLocation = (id) =>
  api.get(`/explorer/location/${id}`).then(r => r.data)

// ── Monitoring (F3) ──────────────────────────────────────────────────────────

export const submitMonitoring = (payload) =>
  api.post('/monitoring/submit', payload).then(r => r.data)

export const getMonitoringStatus = (jobId) =>
  api.get(`/monitoring/status/${jobId}`).then(r => r.data)

export const getMonitoringResult = (jobId) =>
  api.get(`/monitoring/result/${jobId}`).then(r => r.data)

export const downloadMonitoringReport = (jobId) =>
  `${window.location.origin}/api/monitoring/download/report/${jobId}`

// ── Advisor (F4) ─────────────────────────────────────────────────────────────

export const getAdvisorRecommendations = async (stats) => {
  const { data } = await api.post('/advisor/recommendations', stats)
  return data
}

export const analyzeLand = async ({ bbox, budget, purpose, custom_purpose }) => {
  const { data } = await api.post('/advisor/analyze', { bbox, budget, purpose, custom_purpose })
  return data
}

export default api
