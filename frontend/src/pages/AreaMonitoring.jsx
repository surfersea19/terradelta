import { useState, useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import BaseMap from '../components/map/BaseMap.jsx'
import LoadingOverlay from '../components/shared/LoadingOverlay.jsx'
import { useMonitoringStore } from '../store/analysisStore.js'
import { submitMonitoring, getMonitoringStatus, getMonitoringResult, login, signup, logout, getCurrentUser, getSavedAreas, saveArea } from '../services/api.js'
import toast from 'react-hot-toast'
import { useEffect } from 'react'

const MAX_DATES = 6
const MIN_DATES = 2

function TimelineChart({ data }) {
  if (!data?.length) return null
  return (
    <div className="card">
      <div className="section-title mb-3">Change Over Time</div>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="changeGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#1a6e4a" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#1a6e4a" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#94a3b8', fontSize: 10 }}
            tickFormatter={d => d.slice(0, 7)}
            stroke="#334155"
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 10 }}
            stroke="#334155"
            tickFormatter={v => `${v}%`}
          />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
            labelStyle={{ color: '#f1f5f9', fontSize: 12 }}
            formatter={(v, n) => [`${v}%`, 'Changed Area']}
          />
          <Area
            type="monotone"
            dataKey="change_percent"
            stroke="#2d9e6d"
            strokeWidth={2}
            fill="url(#changeGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function AreaMonitoring() {
  const {
    bbox, dates, jobId, status, progress, result, activeDate,
    setBbox, setDates, setJobId, setStatus, setResult, setActiveDate,
    reset,
  } = useMonitoringStore()

  const [drawMode, setDrawMode] = useState(false)
  const [user, setUser] = useState(null)
  const [authMode, setAuthMode] = useState('login') // 'login' or 'signup'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [savedAreas, setSavedAreas] = useState([])
  const [newAreaName, setNewAreaName] = useState('')

  useEffect(() => {
      const init = async () => {
          try {
              const u = await getCurrentUser()
              setUser(u)
              const areas = await getSavedAreas()
              setSavedAreas(areas)
          } catch (e) {
              // Not logged in
          }
      }
      init()
  }, [])

  const handleAuth = async (e) => {
      e.preventDefault()
      try {
          if (authMode === 'login') {
              await login(username, password)
              toast.success('Logged in successfully')
          } else {
              await signup(username, password)
              await login(username, password)
              toast.success('Signed up successfully')
          }
          const u = await getCurrentUser()
          setUser(u)
          const areas = await getSavedAreas()
          setSavedAreas(areas)
      } catch (err) {
          toast.error(err.response?.data?.detail || 'Authentication failed')
      }
  }

  const handleLogout = () => {
      logout()
      setUser(null)
      setSavedAreas([])
      toast.success('Logged out')
  }

  const handleSaveArea = async () => {
      if (!newAreaName || !bbox) return
      try {
          const area = await saveArea(newAreaName, bbox)
          setSavedAreas([...savedAreas, area])
          setNewAreaName('')
          toast.success('Area saved!')
      } catch (e) {
          toast.error('Failed to save area')
      }
  }

  const handleBboxChange = useCallback((newBbox) => {
    setBbox(newBbox)
    setDrawMode(false)
  }, [setBbox])

  const addDate = () => {
    if (dates.length >= MAX_DATES) return toast.error(`Maximum ${MAX_DATES} dates`)
    setDates([...dates, ''])
  }

  const removeDate = (i) => {
    if (dates.length <= MIN_DATES) return
    setDates(dates.filter((_, idx) => idx !== i))
  }

  const updateDate = (i, val) => {
    const updated = [...dates]
    updated[i] = val
    setDates(updated)
  }

  const handleSubmit = async () => {
    if (!bbox)  return toast.error('Draw an area of interest first')
    const validDates = dates.filter(d => d)
    if (validDates.length < 2) return toast.error('Need at least 2 dates')

    reset()
    try {
      const { job_id } = await submitMonitoring({ bbox, dates: validDates })
      setJobId(job_id)
      setStatus('queued', 0)
      toast.success('Monitoring submitted!')

      const interval = setInterval(async () => {
        try {
          const s = await getMonitoringStatus(job_id)
          setStatus(s.status, s.progress)
          if (s.status === 'complete') {
            clearInterval(interval)
            const res = await getMonitoringResult(job_id)
            setResult(res)
            toast.success('Monitoring complete!')
          } else if (s.status === 'failed') {
            clearInterval(interval)
            toast.error('Monitoring failed')
          }
        } catch { clearInterval(interval) }
      }, 2500)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Submission failed')
    }
  }

  const isRunning = ['queued', 'processing'].includes(status)

  // Active image for map overlay
  const activeImg = result?.images?.[activeDate]
  const overlayBounds = bbox ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]] : null

  return (
    <div className="flex h-full">
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r border-border bg-card flex flex-col overflow-y-auto">
        <div className="p-4 border-b border-border">
          <h1 className="font-semibold text-slate-100">Area Monitoring</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Track development changes across multiple dates
          </p>
        </div>

        <div className="p-4 flex flex-col gap-4 flex-1">
          {/* Auth & Saved Areas */}
          {!user ? (
              <div className="card text-sm">
                  <div className="font-medium mb-2">{authMode === 'login' ? 'Login' : 'Sign Up'} to save areas</div>
                  <form onSubmit={handleAuth} className="flex flex-col gap-2">
                      <input type="text" placeholder="Username" className="input-field py-1 text-xs" value={username} onChange={e => setUsername(e.target.value)} required />
                      <input type="password" placeholder="Password" className="input-field py-1 text-xs" value={password} onChange={e => setPassword(e.target.value)} required />
                      <button type="submit" className="btn-primary py-1 text-xs">{authMode === 'login' ? 'Login' : 'Sign Up'}</button>
                  </form>
                  <button onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')} className="text-[10px] text-slate-400 mt-2 hover:text-white">
                      {authMode === 'login' ? 'Need an account? Sign up' : 'Already have an account? Login'}
                  </button>
              </div>
          ) : (
              <div className="card text-sm">
                  <div className="flex justify-between items-center mb-2">
                      <span className="font-medium text-primary-l">Hi, {user.username}</span>
                      <button onClick={handleLogout} className="text-xs text-slate-400 hover:text-white">Logout</button>
                  </div>
                  
                  {savedAreas.length > 0 && (
                      <div className="mb-3">
                          <div className="text-xs text-slate-500 mb-1">Your Saved Areas:</div>
                          <div className="flex flex-col gap-1 max-h-24 overflow-y-auto">
                              {savedAreas.map(a => (
                                  <button key={a.id} onClick={() => setBbox(a.bbox)} className="text-left text-xs bg-dark px-2 py-1 rounded hover:bg-slate-700">
                                      📍 {a.name}
                                  </button>
                              ))}
                          </div>
                      </div>
                  )}

                  {bbox && (
                      <div className="flex gap-1 mt-2">
                          <input type="text" placeholder="Area name" className="input-field py-1 text-xs flex-1" value={newAreaName} onChange={e => setNewAreaName(e.target.value)} />
                          <button onClick={handleSaveArea} disabled={!newAreaName} className="btn-secondary py-1 px-2 text-xs">Save</button>
                      </div>
                  )}
              </div>
          )}

          {/* AOI */}
          <div>
            <label className="section-title">Area of Interest</label>
            <button
              onClick={() => setDrawMode(d => !d)}
              className={`w-full py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                drawMode
                  ? 'border-accent text-accent bg-orange-900/20'
                  : 'border-border text-slate-300 bg-dark hover:border-primary-l'
              }`}
            >
              {drawMode ? '✏️ Drawing…' : '✏️ Draw AOI'}
            </button>
            {bbox && (
              <div className="mt-1 text-xs text-slate-500 font-mono px-1">
                {bbox.map(v => v.toFixed(3)).join(', ')}
              </div>
            )}
          </div>

          {/* Dates */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="section-title mb-0">Dates ({dates.length}/{MAX_DATES})</label>
              <button onClick={addDate} className="text-xs text-primary-l hover:text-white transition-colors">
                + Add Date
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {dates.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 w-4 shrink-0">{i === 0 ? 'T1' : `T${i+1}`}</span>
                  <input
                    type="date"
                    value={d}
                    onChange={e => updateDate(i, e.target.value)}
                    className="input-field flex-1 text-xs py-1.5"
                  />
                  {dates.length > MIN_DATES && (
                    <button
                      onClick={() => removeDate(i)}
                      className="text-slate-500 hover:text-red-400 text-xs transition-colors"
                    >✕</button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isRunning || !bbox}
            className="btn-primary w-full py-2.5"
          >
            {isRunning
              ? <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Processing...
                </span>
              : '📈 Run Monitoring'
            }
          </button>

          {isRunning && (
            <div className="card">
              <LoadingOverlay progress={progress} message="Processing dates..." />
            </div>
          )}

          {/* Timeline chart */}
          {result?.timeline && <TimelineChart data={result.timeline} />}

          {/* Date navigator */}
          {result?.images && (
            <div>
              <label className="section-title">Select Date</label>
              <div className="flex flex-col gap-1">
                {result.images.map((img, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveDate(i)}
                    className={`text-left px-3 py-2 rounded-lg text-xs transition-colors border ${
                      activeDate === i
                        ? 'border-primary bg-primary/20 text-primary-l'
                        : 'border-transparent text-slate-400 hover:border-border hover:text-slate-200'
                    }`}
                  >
                    <div className="font-medium">{i === 0 ? 'Baseline' : `Date ${i}`}</div>
                    <div className="text-slate-500">{img.date}</div>
                    {result.timeline?.[i - 1] && (
                      <div className="text-accent mt-0.5">
                        {result.timeline[i-1]?.change_percent}% changed
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Map ──────────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <BaseMap
          center={[20.5, 78.9]}
          zoom={5}
          // line deleted
          drawMode={drawMode}
          onBboxChange={handleBboxChange}
          bbox={bbox}
          afterUrl={activeImg?.url}
          changeMaskUrl={activeImg?.change_url}
          activeLayer={activeImg?.change_url ? 'change' : 'after'}
          overlayBounds={overlayBounds}
        />
      </div>
    </div>
  )
}
