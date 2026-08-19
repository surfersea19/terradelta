import { useState, useCallback } from 'react'
import BaseMap from '../components/map/BaseMap.jsx'
import { analyzeLand } from '../services/api.js'
import toast from 'react-hot-toast'

const PURPOSES = [
  { id: 'agriculture', label: '🌾 Agriculture' },
  { id: 'residential', label: '🏠 Residential' },
  { id: 'commercial',  label: '🏢 Commercial' },
  { id: 'showroom',    label: '🚗 Showroom' },
  { id: 'warehouse',   label: '📦 Warehouse' },
  { id: 'school',      label: '🏫 School' },
  { id: 'hospital',    label: '🏥 Hospital' },
  { id: 'custom',      label: '✏️ Custom' },
]

function CompositionBar({ label, pct, color }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-20 text-slate-400 shrink-0">{label}</div>
      <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <div className="w-10 text-right text-slate-300 font-medium">{pct}%</div>
    </div>
  )
}

function ScoreBadge({ score }) {
  const color = score >= 65 ? 'text-green-400 border-green-700 bg-green-900/30'
    : score >= 40 ? 'text-yellow-400 border-yellow-700 bg-yellow-900/30'
    : 'text-red-400 border-red-700 bg-red-900/30'
  return (
    <span className={`px-2.5 py-1 rounded-lg text-sm font-bold border ${color}`}>
      {score}/100
    </span>
  )
}

export default function AILandAdvisor() {
  const [bbox, setBbox] = useState(null)
  const [drawMode, setDrawMode] = useState(true)
  const [budget, setBudget] = useState('')
  const [purpose, setPurpose] = useState('agriculture')
  const [customPurpose, setCustomPurpose] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)

  const handleBboxChange = useCallback((newBbox) => {
    setBbox(newBbox)
    setDrawMode(false)
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!bbox) {
      toast('Draw your land on the map first.', { icon: '🗺️' })
      return
    }
    if (purpose === 'custom' && !customPurpose.trim()) {
      toast('Enter a custom purpose.', { icon: '✏️' })
      return
    }
    setLoading(true)
    setData(null)
    try {
      const res = await analyzeLand({
        bbox,
        budget: Number(budget) || 0,
        purpose,
        custom_purpose: purpose === 'custom' ? customPurpose.trim() : null,
      })
      setData(res)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to analyze land')
    }
    setLoading(false)
  }

  const overlayBounds = bbox ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]] : null

  return (
    <div className="flex h-full">
      {/* ── Left sidebar ─────────────────────────────────────────── */}
      <aside className="w-80 shrink-0 border-r border-border bg-card flex flex-col overflow-y-auto">
        <div className="p-4 border-b border-border">
          <h1 className="font-semibold text-slate-100">AI Land Advisor</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Draw your land, tell us your budget and intended use — get an advisory
            recommendation with reasoning, not a guarantee.
          </p>
        </div>

        <div className="p-4 flex flex-col gap-4">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="section-title block mb-1">1. Select Your Land</label>
              <button
                type="button"
                onClick={() => setDrawMode(true)}
                className={`btn-secondary w-full py-2 text-sm ${drawMode ? 'ring-1 ring-primary' : ''}`}
              >
                {bbox ? '🔁 Redraw Area' : '✏️ Draw Area on Map'}
              </button>
              {bbox && (
                <div className="text-[11px] text-slate-500 mt-1">
                  {bbox.map(n => n.toFixed(4)).join(', ')}
                </div>
              )}
            </div>

            <div>
              <label className="section-title block mb-1">2. Budget (₹)</label>
              <input
                type="number"
                min="0"
                step="1000"
                placeholder="e.g. 2500000"
                value={budget}
                onChange={e => setBudget(e.target.value)}
                className="input-field"
              />
            </div>

            <div>
              <label className="section-title block mb-1">3. Intended Purpose</label>
              <div className="grid grid-cols-2 gap-1.5">
                {PURPOSES.map(p => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPurpose(p.id)}
                    className={`px-2 py-1.5 text-xs rounded-lg border text-left transition-colors ${
                      purpose === p.id
                        ? 'border-primary bg-primary/20 text-primary-l'
                        : 'border-border text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              {purpose === 'custom' && (
                <input
                  type="text"
                  placeholder="Describe your purpose"
                  value={customPurpose}
                  onChange={e => setCustomPurpose(e.target.value)}
                  className="input-field mt-2"
                />
              )}
            </div>

            <button type="submit" disabled={loading || !bbox} className="btn-primary w-full py-2.5">
              {loading ? 'Analyzing...' : '🧭 Get Recommendation'}
            </button>
          </form>

          {data && (
            <div className="flex flex-col gap-4 fade-in-up">
              <div className="card border border-primary/40">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-xs text-slate-400 uppercase tracking-wider">Recommendation</div>
                    <div className="text-lg font-bold text-slate-100 capitalize">
                      {data.recommendation.purpose}
                    </div>
                    <div className="text-xs text-slate-400">{data.recommendation.label}</div>
                  </div>
                  <ScoreBadge score={data.recommendation.score} />
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mb-1.5">Why</div>
                <ul className="list-disc list-inside text-xs text-slate-300 flex flex-col gap-1.5">
                  {data.recommendation.why.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>

              <div className="card">
                <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Land Cover — Your Area</div>
                <div className="flex flex-col gap-1.5">
                  <CompositionBar label="Built-up" pct={data.context.aoi.built_up_pct} color="#f97316" />
                  <CompositionBar label="Vegetation" pct={data.context.aoi.vegetation_pct} color="#22c55e" />
                  <CompositionBar label="Water" pct={data.context.aoi.water_pct} color="#3b82f6" />
                  <CompositionBar label="Bare/Other" pct={data.context.aoi.bare_soil_pct} color="#94a3b8" />
                </div>
                <div className="text-xs text-slate-400 uppercase tracking-wider mt-3 mb-2">Land Cover — Surrounding</div>
                <div className="flex flex-col gap-1.5">
                  <CompositionBar label="Built-up" pct={data.context.surrounding.built_up_pct} color="#f97316" />
                  <CompositionBar label="Vegetation" pct={data.context.surrounding.vegetation_pct} color="#22c55e" />
                  <CompositionBar label="Water" pct={data.context.surrounding.water_pct} color="#3b82f6" />
                  <CompositionBar label="Bare/Other" pct={data.context.surrounding.bare_soil_pct} color="#94a3b8" />
                </div>
              </div>

              {data.alternatives?.length > 0 && (
                <div className="card">
                  <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Other Options Considered</div>
                  <div className="flex flex-col gap-1.5">
                    {data.alternatives.map(a => (
                      <div key={a.purpose} className="flex items-center justify-between text-xs">
                        <span className="text-slate-300 capitalize">{a.purpose}</span>
                        <span className="text-slate-400">{a.score}/100</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="card border border-yellow-700/40 bg-yellow-900/10">
                <div className="text-xs text-yellow-400 uppercase tracking-wider mb-1.5">Data Limitations</div>
                <ul className="list-disc list-inside text-[11px] text-slate-400 flex flex-col gap-1">
                  {data.data_limitations.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
                <p className="text-[11px] text-slate-500 mt-2 italic">{data.disclaimer}</p>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Map area ──────────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <BaseMap
          center={[20.5, 78.9]}
          zoom={5}
          drawMode={drawMode}
          onBboxChange={handleBboxChange}
          bbox={bbox}
          overlayBounds={overlayBounds}
        />
      </div>
    </div>
  )
}
