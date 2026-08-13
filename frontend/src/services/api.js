import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

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

export default api
