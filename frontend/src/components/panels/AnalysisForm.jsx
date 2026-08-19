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

export default function AnalysisForm({ onFlyTo, onResult, onProgress, drawMode, onDrawModeChange }) {
  const {
    bbox, dates,
    setBbox, setDates,
    setJobId, setJobStatus, setResult, jobStatus, jobProgress, jobMessage,
  } = useAnalysisStore()

  
  const [submitting, setSubmitting] = useState(false)

  const handleLocationSelect = (e) => {
    const loc = PRESET_LOCATIONS.find(l => l.label === e.target.value)
    if (loc?.center) onFlyTo({ center: loc.center, zoom: loc.zoom })
  }

  const toggleDrawMode = () => {
  onDrawModeChange(!drawMode)
  if (!drawMode) toast('Click and drag on the map to draw your AOI', { icon: '✏️' })
  }

  const handleSubmit = async () => {
    if (!bbox)  return toast.error('Draw an area of interest on the map first')
    if (dates.some(d => !d)) return toast.error('Please fill in all dates')
    
    // Validate chronological order
    for (let i = 0; i < dates.length - 1; i++) {
        if (dates[i] >= dates[i+1]) {
            return toast.error(`Date ${i+2} must be later than Date ${i+1}`)
        }
    }

    setSubmitting(true)
    onDrawModeChange(false)

    try {
      const { job_id } = await submitAnalysis({ bbox, dates })
      setJobId(job_id)
      setJobStatus('queued', 0, 'Waiting to start...')
      toast.success('Analysis submitted!')

      // Poll for completion
      let retries=0
      const interval = setInterval(async () => {
        try {
          const status = await getAnalysisStatus(job_id)
          retries = 0
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
          retries++
          if (retries >= 3) {
           clearInterval(interval)
           toast.error('Lost connection to server. Please refresh and try again.')
           setSubmitting(false)
          }
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

      {/* Dates Selection */}
      <div>
        <div className="flex items-center justify-between mb-2">
            <label className="section-title !mb-0">Selected Dates</label>
            {dates.length < 4 && (
                <button
                    onClick={() => setDates([...dates, ''])}
                    className="text-xs text-primary hover:text-primary-l font-medium"
                >
                    + Add Date
                </button>
            )}
        </div>
        
        <div className="flex flex-col gap-2">
            {dates.map((date, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                    <span className="text-xs font-medium text-slate-400 w-12">Date {idx + 1}</span>
                    <input
                        type="date"
                        value={date}
                        min={idx > 0 ? dates[idx-1] : '2015-01-01'}
                        max="2025-06-30"
                        onChange={e => {
                            const newDates = [...dates]
                            newDates[idx] = e.target.value
                            setDates(newDates)
                        }}
                        className="input-field flex-1"
                    />
                    {dates.length > 2 && idx === dates.length - 1 && (
                        <button
                            onClick={() => {
                                const newDates = [...dates]
                                newDates.pop()
                                setDates(newDates)
                            }}
                            className="text-slate-500 hover:text-red-400 p-1"
                        >
                            ✕
                        </button>
                    )}
                </div>
            ))}
        </div>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={isRunning || !bbox || dates.some(d => !d)}
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
