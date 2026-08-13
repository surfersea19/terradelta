import { useState } from 'react'
import toast from 'react-hot-toast'
import { useAnalysisStore } from '../../store/analysisStore.js'
import { submitAnalysis, getAnalysisStatus, getAnalysisResult } from '../../services/api.js'

const PRESET_LOCATIONS = [
  { label: 'Hyderabad, India',    center: [17.38, 78.48],  zoom: 12 },
  { label: 'Navi Mumbai, India',  center: [19.04, 73.02],  zoom: 12 },
  { label: 'Surat, India',        center: [21.17, 72.83],  zoom: 12 },
  { label: 'Pune, India',         center: [18.52, 73.86],  zoom: 12 },
  { label: 'Dubai, UAE',          center: [25.20, 55.27],  zoom: 11 },
  { label: 'Custom…',             center: null },
]

export default function AnalysisForm({ onFlyTo, onResult, onProgress }) {
  const {
    bbox, date1, date2, model,
    setBbox, setDate1, setDate2, setModel,
    setJobId, setJobStatus, setResult, jobStatus, jobProgress, jobMessage,
  } = useAnalysisStore()

  const [drawMode, setDrawMode] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleLocationSelect = (e) => {
    const loc = PRESET_LOCATIONS.find(l => l.label === e.target.value)
    if (loc?.center) onFlyTo({ center: loc.center, zoom: loc.zoom })
  }

  const toggleDrawMode = () => {
    setDrawMode(d => !d)
    if (!drawMode) toast('Click and drag on the map to draw your AOI', { icon: '✏️' })
  }

  const handleSubmit = async () => {
    if (!bbox)  return toast.error('Draw an area of interest on the map first')
    if (!date1) return toast.error('Select a "before" date')
    if (!date2) return toast.error('Select an "after" date')
    if (date2 <= date1) return toast.error('"After" date must be later than "before" date')

    setSubmitting(true)
    setDrawMode(false)

    try {
      const { job_id } = await submitAnalysis({ bbox, date1, date2, model })
      setJobId(job_id)
      setJobStatus('queued', 0, 'Waiting to start...')
      toast.success('Analysis submitted!')

      // Poll for completion
      const interval = setInterval(async () => {
        try {
          const status = await getAnalysisStatus(job_id)
          setJobStatus(status.status, status.progress, status.message)
          onProgress(status.progress, status.message)

          if (status.status === 'complete') {
            clearInterval(interval)
            const result = await getAnalysisResult(job_id)
            setResult(result)
            onResult(result)
            toast.success('Analysis complete!')
            setSubmitting(false)
          } else if (status.status === 'failed') {
            clearInterval(interval)
            toast.error('Analysis failed. Check server logs.')
            setSubmitting(false)
          }
        } catch (err) {
          clearInterval(interval)
          toast.error('Connection error while polling status')
          setSubmitting(false)
        }
      }, 2000)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit analysis')
      setSubmitting(false)
    }
  }

  const isRunning = submitting || ['queued', 'processing'].includes(jobStatus)

  return (
    <div className="flex flex-col gap-4">
      {/* Location preset */}
      <div>
        <label className="section-title">Jump to Location</label>
        <select
          onChange={handleLocationSelect}
          defaultValue=""
          className="input-field"
        >
          <option value="" disabled>Select a preset location…</option>
          {PRESET_LOCATIONS.map(l => (
            <option key={l.label} value={l.label}>{l.label}</option>
          ))}
        </select>
      </div>

      {/* AOI drawing */}
      <div>
        <label className="section-title">Area of Interest</label>
        <button
          onClick={toggleDrawMode}
          className={`w-full py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
            drawMode
              ? 'border-accent text-accent bg-orange-900/20'
              : 'border-border text-slate-300 bg-card hover:border-primary-l hover:text-primary-l'
          }`}
        >
          {drawMode ? '✏️ Drawing… (click & drag on map)' : '✏️ Draw Rectangle AOI'}
        </button>
        {bbox && (
          <div className="mt-1.5 text-xs text-slate-400 font-mono bg-slate-900/50 rounded px-2 py-1.5">
            {bbox.map(v => v.toFixed(4)).join(', ')}
          </div>
        )}
      </div>

      {/* Dates */}
      <div>
        <label className="section-title">Before Date (T1)</label>
        <input
          type="date"
          value={date1}
          max={date2 || '2024-12-31'}
          onChange={e => setDate1(e.target.value)}
          className="input-field"
        />
      </div>
      <div>
        <label className="section-title">After Date (T2)</label>
        <input
          type="date"
          value={date2}
          min={date1 || '2015-01-01'}
          max="2025-06-30"
          onChange={e => setDate2(e.target.value)}
          className="input-field"
        />
      </div>

      {/* Model selection */}
      <div>
        <label className="section-title">Detection Model</label>
        <div className="flex gap-2">
          {[
            { id: 'rf',      label: 'Random Forest', badge: 'Recommended' },
            { id: 'siamese', label: 'Siamese CNN',   badge: 'DL' },
          ].map(m => (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border transition-colors ${
                model === m.id
                  ? 'border-primary bg-primary/20 text-primary-l'
                  : 'border-border text-slate-400 hover:border-slate-500'
              }`}
            >
              {m.label}
              {m.badge && (
                <span className="ml-1 text-[10px] text-slate-500">[{m.badge}]</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={isRunning || !bbox || !date1 || !date2}
        className="btn-primary w-full py-2.5 flex items-center justify-center gap-2"
      >
        {isRunning
          ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Analysing...</>
          : '🔍 Analyse Changes'
        }
      </button>

      {/* Notes */}
      <p className="text-xs text-slate-500 leading-relaxed">
        ⚠️ Sentinel-2 at 10 m resolution. Objects &lt;30 m may not be reliably detected.
        Analysis uses synthetic data in demo mode.
      </p>
    </div>
  )
}
