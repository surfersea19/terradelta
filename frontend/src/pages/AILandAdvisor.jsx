import { useState, useCallback, useRef } from 'react'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import BaseMap from '../components/map/BaseMap.jsx'
import { analyzeLand } from '../services/api.js'
import toast from 'react-hot-toast'

// ─── Constants ────────────────────────────────────────────────────────────────

const PURPOSES = [
  { id: 'agriculture', label: 'Agriculture',  icon: '🌾', desc: 'Farming, crops, agri-processing' },
  { id: 'residential', label: 'Residential',  icon: '🏠', desc: 'Housing, apartments, colonies' },
  { id: 'commercial',  label: 'Commercial',   icon: '🏢', desc: 'Office, retail, mixed-use' },
  { id: 'showroom',    label: 'Showroom',     icon: '🚗', desc: 'Auto / product showroom' },
  { id: 'warehouse',   label: 'Warehouse',    icon: '📦', desc: 'Logistics, cold storage' },
  { id: 'school',      label: 'School',       icon: '🏫', desc: 'K-12, college campus' },
  { id: 'hospital',    label: 'Hospital',     icon: '🏥', desc: 'Medical centre, clinic' },
  { id: 'custom',      label: 'Custom',       icon: '✏️', desc: 'Describe your own use case' },
]

const BUDGET_PRESETS = [
  { label: '< ₹10L',   value: 500_000 },
  { label: '₹50L',     value: 5_000_000 },
  { label: '₹1 Cr',    value: 10_000_000 },
  { label: '₹5 Cr',    value: 50_000_000 },
  { label: '₹10 Cr+',  value: 100_000_000 },
]

const SCORE_COLOR = (s) =>
  s >= 75 ? '#22c55e' : s >= 60 ? '#86efac' : s >= 40 ? '#fbbf24' : '#f87171'

const SCORE_BG = (s) =>
  s >= 75 ? 'bg-green-900/30 border-green-700/50' :
  s >= 60 ? 'bg-green-900/20 border-green-800/40' :
  s >= 40 ? 'bg-yellow-900/30 border-yellow-700/50' :
  'bg-red-900/20 border-red-800/40'

// ─── Sub-components ───────────────────────────────────────────────────────────

function StepBadge({ n, active, done }) {
  return (
    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border shrink-0
      ${done ? 'bg-primary border-primary text-white'
             : active ? 'border-primary-l text-primary-l bg-primary/10'
                      : 'border-border text-slate-500 bg-transparent'}`}>
      {done ? '✓' : n}
    </div>
  )
}

function CompositionBar({ label, pct, color }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-20 text-slate-400 shrink-0">{label}</div>
      <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="w-9 text-right text-slate-300 font-medium tabular-nums">{pct}%</div>
    </div>
  )
}

function ScoreRing({ score, size = 80 }) {
  const r = (size - 10) / 2
  const circ = 2 * Math.PI * r
  const dash = (score / 100) * circ
  const color = SCORE_COLOR(score)
  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e293b" strokeWidth={7} />
      <circle
        cx={size/2} cy={size/2} r={r} fill="none"
        stroke={color} strokeWidth={7}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 1s ease' }}
      />
      <text
        x={size/2} y={size/2 + 1}
        textAnchor="middle" dominantBaseline="middle"
        fill={color} fontSize={size > 70 ? 18 : 13} fontWeight="700"
        transform={`rotate(90, ${size/2}, ${size/2})`}
      >
        {score}
      </text>
    </svg>
  )
}

function PurposeCard({ p, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick(p.id)}
      className={`p-2.5 rounded-xl border text-left transition-all duration-150 group
        ${selected
          ? 'border-primary bg-primary/15 shadow-[0_0_0_1px_rgba(26,110,74,0.4)]'
          : 'border-border hover:border-slate-500 hover:bg-slate-800/60'}`}
    >
      <div className="text-lg mb-0.5">{p.icon}</div>
      <div className={`text-xs font-semibold ${selected ? 'text-primary-l' : 'text-slate-200'}`}>{p.label}</div>
      <div className="text-[10px] text-slate-500 leading-snug mt-0.5">{p.desc}</div>
    </button>
  )
}

function ProximityFacts({ proximity }) {
  if (!proximity) return null
  const isLive = proximity.source === 'osm_live'

  return (
    <div className="card mt-2">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-xs text-slate-400 uppercase tracking-wider">Nearby Context</div>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium
          ${isLive ? 'bg-green-900/40 text-green-400 border border-green-800/50'
                   : 'bg-yellow-900/30 text-yellow-500 border border-yellow-800/40'}`}>
          {isLive ? '● OSM Live' : '● Inferred'}
        </span>
      </div>

      {isLive && (
        <>
          {proximity.road_types?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {proximity.road_types.map(r => (
                <span key={r} className="text-[10px] bg-blue-900/30 border border-blue-800/40 text-blue-300 px-1.5 py-0.5 rounded-full">
                  🛣 {r}
                </span>
              ))}
            </div>
          )}
          {proximity.has_major_road && (
            <div className="text-xs text-green-400 mb-1.5">✓ Major arterial road within 5 km</div>
          )}
          <div className="grid grid-cols-2 gap-1.5 mb-2">
            {Object.entries(proximity.amenity_counts || {}).map(([cat, n]) => (
              <div key={cat} className="flex items-center justify-between text-xs bg-slate-800/50 rounded-lg px-2 py-1">
                <span className="text-slate-400 capitalize">{cat}</span>
                <span className="text-slate-200 font-medium tabular-nums">{n}</span>
              </div>
            ))}
          </div>
          {proximity.named_nearby?.length > 0 && (
            <div className="flex flex-col gap-1">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Named Facilities</div>
              {proximity.named_nearby.map((f, i) => (
                <div key={i} className="flex justify-between text-[11px]">
                  <span className="text-slate-300 truncate">{f.name}</span>
                  <span className="text-slate-500 ml-2 shrink-0">{f.dist_km} km</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!isLive && (
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Connectivity</span>
            <span className={`font-medium capitalize
              ${proximity.connectivity_proxy === 'high' ? 'text-green-400'
              : proximity.connectivity_proxy === 'medium' ? 'text-yellow-400'
              : 'text-red-400'}`}>
              {proximity.connectivity_proxy}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Urbanisation</span>
            <span className="text-slate-300 font-medium capitalize">{proximity.urbanisation_proxy}</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-1 italic">
            Based on land-cover density — OSM data was unavailable.
          </div>
        </div>
      )}
    </div>
  )
}

function AlternativesRadar({ allScores, requestedPurpose }) {
  if (!allScores?.length) return null
  const data = allScores.slice(0, 7).map(s => ({
    subject: s.icon ? `${s.icon} ${s.purpose}` : s.purpose,
    score:   s.score,
    fullMark: 100,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-slate-900 border border-border rounded-lg px-3 py-2 text-xs">
        <div className="text-slate-300 font-medium">{payload[0]?.payload?.subject}</div>
        <div className="text-primary-l font-bold">{payload[0]?.value}/100</div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">All-Purpose Suitability</div>
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="#334155" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9, fill: '#94a3b8' }} />
          <Radar name="Score" dataKey="score" stroke="#2d9e6d" fill="#2d9e6d" fillOpacity={0.25} dot={false} />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

function AlternativesList({ alternatives }) {
  if (!alternatives?.length) return null
  return (
    <div className="card">
      <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Other Options Ranked</div>
      <div className="flex flex-col gap-1.5">
        {alternatives.map(a => (
          <div key={a.purpose} className="flex items-center gap-2">
            <span className="text-base w-5 shrink-0 text-center">{a.icon}</span>
            <span className="text-xs text-slate-300 capitalize flex-1">{a.purpose}</span>
            <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${a.score}%`, backgroundColor: SCORE_COLOR(a.score) }}
              />
            </div>
            <span className="text-xs text-slate-400 tabular-nums w-8 text-right">{a.score}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MapContextOverlay({ bbox }) {
  if (!bbox) return null
  const [lon_min, lat_min, lon_max, lat_max] = bbox
  const cx = ((lon_min + lon_max) / 2).toFixed(5)
  const cy = ((lat_min + lat_max) / 2).toFixed(5)
  return (
    <div className="absolute top-3 left-3 z-[1000] bg-slate-900/90 border border-border
                    rounded-xl px-3 py-2 text-xs text-slate-300 pointer-events-none">
      <div className="text-[10px] text-slate-500 mb-0.5">Selected Area</div>
      <div className="font-mono tabular-nums">
        {cy}°N, {cx}°E
      </div>
    </div>
  )
}

function LoadingPulse() {
  const steps = [
    'Fetching satellite land-cover data…',
    'Querying OSM nearby facilities…',
    'Scoring all purpose categories…',
    'Building advisory recommendation…',
  ]
  const [step, setStep] = useState(0)
  useState(() => {
    const t = setInterval(() => setStep(s => (s + 1) % steps.length), 900)
    return () => clearInterval(t)
  })
  return (
    <div className="card border-primary/30 bg-primary/5 flex flex-col items-center gap-3 py-6">
      <div className="flex gap-1">
        {[0,1,2].map(i => (
          <div key={i} className="w-2 h-2 rounded-full bg-primary-l animate-bounce"
               style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
      <div className="text-xs text-slate-400 text-center">{steps[step]}</div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AILandAdvisor() {
  const [bbox, setBbox]               = useState(null)
  const [drawMode, setDrawMode]       = useState(true)
  const [budget, setBudget]           = useState('')
  const [budgetRaw, setBudgetRaw]     = useState('')
  const [purpose, setPurpose]         = useState('agriculture')
  const [customPurpose, setCustomPurpose] = useState('')
  const [loading, setLoading]         = useState(false)
  const [data, setData]               = useState(null)
  const resultRef                     = useRef(null)

  const handleBboxChange = useCallback((newBbox) => {
    setBbox(newBbox)
    setDrawMode(false)
    setData(null)
  }, [])

  const handleBudgetPreset = (val) => {
    setBudget(val)
    setBudgetRaw(val.toLocaleString('en-IN'))
  }

  const handleBudgetInput = (e) => {
    const raw = e.target.value.replace(/[^0-9]/g, '')
    setBudgetRaw(raw ? Number(raw).toLocaleString('en-IN') : '')
    setBudget(Number(raw) || 0)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!bbox) {
      toast('Draw your land on the map first.', { icon: '🗺️' })
      return
    }
    if (!budget || budget <= 0) {
      toast('Enter your budget.', { icon: '💰' })
      return
    }
    if (purpose === 'custom' && !customPurpose.trim()) {
      toast('Describe your custom purpose.', { icon: '✏️' })
      return
    }
    setLoading(true)
    setData(null)
    try {
      const res = await analyzeLand({
        bbox,
        budget: Number(budget),
        purpose,
        custom_purpose: purpose === 'custom' ? customPurpose.trim() : null,
      })
      setData(res)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Analysis failed — is the backend running?')
    }
    setLoading(false)
  }

  const purposeInfo = PURPOSES.find(p => p.id === purpose)
  const overlayBounds = bbox ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]] : null

  const hasBbox   = !!bbox
  const hasBudget = budget > 0
  const canSubmit = hasBbox && hasBudget && !loading

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-[340px] shrink-0 border-r border-border bg-card flex flex-col overflow-y-auto">

        {/* Header */}
        <div className="px-5 py-4 border-b border-border bg-gradient-to-r from-primary/10 to-transparent">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">🧭</span>
            <h1 className="font-bold text-slate-100 text-lg tracking-tight">AI Land Advisor</h1>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Select your land on the map, enter your budget and intended use — get a data-driven
            recommendation with transparent reasoning.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 p-5 flex-1">

          {/* Step 1 — Select Land */}
          <div>
            <div className="flex items-center gap-2 mb-2.5">
              <StepBadge n={1} active={!hasBbox} done={hasBbox} />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Select Your Land</span>
            </div>
            <button
              type="button"
              onClick={() => { setDrawMode(true); setData(null) }}
              className={`w-full py-2.5 rounded-xl border text-sm font-medium transition-all duration-150
                ${drawMode
                  ? 'border-accent bg-accent/10 text-accent shadow-[0_0_0_1px_rgba(249,115,22,0.3)]'
                  : hasBbox
                    ? 'border-primary-l/40 bg-primary/10 text-primary-l hover:bg-primary/20'
                    : 'border-border bg-slate-800 text-slate-300 hover:border-slate-500'}`}
            >
              {drawMode
                ? '✏️ Drawing mode — click & drag on map'
                : hasBbox
                  ? '🔁 Redraw area'
                  : '✏️ Draw area on map'}
            </button>
            {hasBbox && (
              <div className="mt-1.5 text-[10px] text-slate-500 font-mono leading-relaxed">
                {bbox.map(n => n.toFixed(4)).join(' · ')}
                {data?.area_ha && (
                  <span className="ml-2 text-slate-400 not-italic">≈ {data.area_ha} ha</span>
                )}
              </div>
            )}
          </div>

          {/* Step 2 — Budget */}
          <div>
            <div className="flex items-center gap-2 mb-2.5">
              <StepBadge n={2} active={hasBbox && !hasBudget} done={hasBudget} />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Budget (₹)</span>
            </div>
            <div className="flex gap-1 flex-wrap mb-2">
              {BUDGET_PRESETS.map(bp => (
                <button
                  key={bp.value}
                  type="button"
                  onClick={() => handleBudgetPreset(bp.value)}
                  className={`px-2 py-1 text-[11px] rounded-lg border font-medium transition-colors
                    ${budget === bp.value
                      ? 'border-primary-l bg-primary/20 text-primary-l'
                      : 'border-border text-slate-500 hover:text-slate-300 hover:border-slate-500'}`}
                >
                  {bp.label}
                </button>
              ))}
            </div>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm font-medium">₹</span>
              <input
                type="text"
                inputMode="numeric"
                placeholder="e.g. 25,00,000"
                value={budgetRaw}
                onChange={handleBudgetInput}
                className="input-field pl-7"
              />
            </div>
          </div>

          {/* Step 3 — Purpose */}
          <div>
            <div className="flex items-center gap-2 mb-2.5">
              <StepBadge n={3} active={hasBbox && hasBudget} done={false} />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Intended Purpose</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {PURPOSES.map(p => (
                <PurposeCard key={p.id} p={p} selected={purpose === p.id} onClick={setPurpose} />
              ))}
            </div>
            {purpose === 'custom' && (
              <input
                type="text"
                placeholder="e.g. Solar farm, resort, cold storage…"
                value={customPurpose}
                onChange={e => setCustomPurpose(e.target.value)}
                className="input-field mt-2"
              />
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!canSubmit}
            className="btn-primary w-full py-3 text-sm font-semibold rounded-xl mt-auto
                       disabled:opacity-40 disabled:cursor-not-allowed
                       shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-shadow"
          >
            {loading
              ? '⏳ Analyzing…'
              : !hasBbox
                ? '⬅ Draw area on map first'
                : !hasBudget
                  ? '⬅ Enter your budget'
                  : `🧭 Analyze for ${purposeInfo?.label}`}
          </button>
        </form>

        {/* Results */}
        {loading && (
          <div className="px-5 pb-5">
            <LoadingPulse />
          </div>
        )}

        {data && !loading && (
          <div ref={resultRef} className="flex flex-col gap-4 px-5 pb-6 fade-in-up">

            {/* Divider */}
            <div className="border-t border-border pt-1">
              <div className="text-[10px] text-slate-500 uppercase tracking-widest">Advisory Result</div>
            </div>

            {/* Primary recommendation card */}
            <div className={`rounded-2xl border p-4 ${SCORE_BG(data.recommendation.score)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex-1">
                  <div className="text-2xl mb-1">{data.recommendation.icon}</div>
                  <div className="text-lg font-bold text-slate-100 capitalize leading-tight">
                    {data.recommendation.purpose}
                  </div>
                  <div className="text-xs font-medium mt-0.5"
                       style={{ color: SCORE_COLOR(data.recommendation.score) }}>
                    {data.recommendation.label}
                  </div>
                </div>
                <ScoreRing score={data.recommendation.score} size={72} />
              </div>

              {/* Area */}
              {data.area_ha && (
                <div className="text-xs text-slate-400 mb-2.5">
                  Estimated area: <span className="text-slate-200 font-semibold">{data.area_ha} ha</span>
                </div>
              )}

              {/* Why */}
              <div className="text-[11px] text-slate-400 uppercase tracking-wider mb-1.5">Why this recommendation</div>
              <ul className="flex flex-col gap-2">
                {data.recommendation.why.map((w, i) => (
                  <li key={i} className="flex gap-2 text-xs text-slate-300 leading-snug">
                    <span className="text-primary-l mt-0.5 shrink-0">▸</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>

            {/* Land cover composition */}
            <div className="card">
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-2.5">Land Cover</div>
              <div className="text-[10px] text-slate-500 mb-1.5">Your selected area</div>
              <div className="flex flex-col gap-1.5 mb-3">
                <CompositionBar label="Built-up"   pct={data.context.aoi.built_up_pct}   color="#f97316" />
                <CompositionBar label="Vegetation" pct={data.context.aoi.vegetation_pct} color="#22c55e" />
                <CompositionBar label="Water"      pct={data.context.aoi.water_pct}      color="#3b82f6" />
                <CompositionBar label="Bare/Other" pct={data.context.aoi.bare_soil_pct}  color="#94a3b8" />
              </div>
              <div className="text-[10px] text-slate-500 mb-1.5">5 km surrounding buffer</div>
              <div className="flex flex-col gap-1.5">
                <CompositionBar label="Built-up"   pct={data.context.surrounding.built_up_pct}   color="#f97316" />
                <CompositionBar label="Vegetation" pct={data.context.surrounding.vegetation_pct} color="#22c55e" />
                <CompositionBar label="Water"      pct={data.context.surrounding.water_pct}      color="#3b82f6" />
                <CompositionBar label="Bare/Other" pct={data.context.surrounding.bare_soil_pct}  color="#94a3b8" />
              </div>
            </div>

            {/* Proximity / OSM context */}
            <ProximityFacts proximity={data.proximity} />

            {/* Radar chart */}
            {data.all_scores?.length > 0 && (
              <AlternativesRadar allScores={data.all_scores} requestedPurpose={data.recommendation.purpose} />
            )}

            {/* Ranked alternatives */}
            {data.alternatives?.length > 0 && (
              <AlternativesList alternatives={data.alternatives} />
            )}

            {/* Limitations + disclaimer */}
            <div className="card border-yellow-800/40 bg-yellow-900/10">
              <div className="text-xs text-yellow-400 uppercase tracking-wider mb-1.5">Data Limitations</div>
              <ul className="flex flex-col gap-1.5 mb-2">
                {data.data_limitations.map((d, i) => (
                  <li key={i} className="flex gap-1.5 text-[11px] text-slate-400 leading-snug">
                    <span className="text-yellow-600 shrink-0 mt-0.5">⚠</span> {d}
                  </li>
                ))}
              </ul>
              <p className="text-[10px] text-slate-500 italic border-t border-yellow-800/20 pt-2 mt-1">
                {data.disclaimer}
              </p>
            </div>

          </div>
        )}
      </aside>

      {/* ── Map ── */}
      <div className="flex-1 relative">
        <BaseMap
          center={[20.5, 78.9]}
          zoom={5}
          drawMode={drawMode}
          onBboxChange={handleBboxChange}
          bbox={bbox}
          overlayBounds={overlayBounds}
        />
        <MapContextOverlay bbox={bbox} />

        {/* Draw mode hint */}
        {!bbox && !drawMode && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-slate-900/80 text-slate-400 text-sm px-5 py-3 rounded-xl border border-border">
              ← Click "Draw area on map" in the sidebar to begin
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
