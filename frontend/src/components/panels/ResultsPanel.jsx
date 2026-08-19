import { useAnalysisStore } from '../../store/analysisStore.js'
import { downloadReport } from '../../services/api.js'

function StatItem({ label, value, unit = '', highlight = false }) {
  return (
    <div className="stat-item">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${highlight ? 'text-accent' : ''}`}>
        {value}{unit && <span className="text-xs text-slate-400 ml-1">{unit}</span>}
      </span>
    </div>
  )
}

function ConfidenceBadge({ confidence }) {
  const pct = Math.round(confidence * 100)
  const color = pct >= 75 ? 'text-green-400' : pct >= 55 ? 'text-yellow-400' : 'text-red-400'
  return (
    <span className={`text-xs font-medium ${color}`}>
      {pct}% confidence
    </span>
  )
}

export default function ResultsPanel() {
  const { result, activeLayer, setActiveLayer, jobId, activeStep } = useAnalysisStore()

  if (!result) return null

  const timelineStep = result.timeline?.[activeStep - 1] || {}
  const { stats, interpretation } = timelineStep
  const model_used = result.model_used
  const t1_actual_date = result.images?.[activeStep - 1]?.date
  const t2_actual_date = result.images?.[activeStep]?.date
  const cloud_cover_t1 = result.cloud_covers?.[activeStep - 1]
  const cloud_cover_t2 = result.cloud_covers?.[activeStep]

  const layers = [
    { id: 'before', label: '◀ Before', icon: '📅' },
    { id: 'after',  label: 'After ▶',  icon: '📅' },
    { id: 'change', label: '⚡ Changes', icon: '' },
  ]

  return (
    <div className="flex flex-col gap-4 fade-in-up">
      {/* Layer toggle */}
      <div>
        <label className="section-title">Map Layer</label>
        <div className="flex gap-1">
          {layers.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveLayer(id)}
              className={`flex-1 py-1.5 text-xs rounded-md font-medium border transition-colors ${
                activeLayer === id
                  ? id === 'change'
                    ? 'border-accent bg-orange-900/30 text-accent'
                    : 'border-primary bg-primary/20 text-primary-l'
                  : 'border-border text-slate-400 hover:border-slate-500'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Image dates */}
      <div className="card text-xs text-slate-400 grid grid-cols-2 gap-2">
        <div>
          <div className="text-slate-500 mb-0.5">Before</div>
          <div className="text-slate-200 font-medium">{t1_actual_date}</div>
          <div>Cloud: {cloud_cover_t1?.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-slate-500 mb-0.5">After</div>
          <div className="text-slate-200 font-medium">{t2_actual_date}</div>
          <div>Cloud: {cloud_cover_t2?.toFixed(1)}%</div>
        </div>
      </div>

      {/* Change statistics */}
      <div className="card">
        <div className="section-title mb-3">Change Statistics</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <StatItem
            label="Changed Area"
            value={stats?.changed_area_ha?.toFixed(1) ?? '—'}
            unit="ha"
            highlight
          />
          <StatItem
            label="Change %"
            value={stats?.change_percent?.toFixed(1) ?? '—'}
            unit="%"
            highlight
          />
          <StatItem label="Clusters"    value={stats?.num_clusters ?? '—'} />
          <StatItem
            label="Confidence"
            value={`${Math.round((stats?.mean_confidence ?? 0) * 100)}%`}
          />
          <StatItem
            label="High-conf Area"
            value={stats?.high_confidence_area_ha?.toFixed(1) ?? '—'}
            unit="ha"
          />
          <StatItem
            label="Model"
            value={model_used?.toUpperCase() ?? '—'}
          />
        </div>
      </div>

      {/* Interpretation */}
      {interpretation && (
        <div className="card border-l-2 border-primary">
          <div className="section-title mb-2">AI Interpretation</div>
          <p className="text-sm text-slate-300 leading-relaxed">{interpretation}</p>
          <div className="mt-2">
            <ConfidenceBadge confidence={stats?.mean_confidence ?? 0} />
          </div>
        </div>
      )}

      {/* No change case */}
      {stats?.changed_area_ha === 0 && (
        <div className="card border border-slate-600 text-center py-4">
          <div className="text-2xl mb-2">✅</div>
          <div className="text-sm text-slate-300">No significant human-caused changes detected</div>
          <div className="text-xs text-slate-500 mt-1">Try a wider date range or different location</div>
        </div>
      )}

      {/* Download PDF */}
      {jobId && (
        <a
          href={downloadReport(jobId)}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary w-full text-center text-sm py-2 flex items-center justify-center gap-2"
        >
          📄 Download PDF Report
        </a>
      )}

      {/* Limitation note */}
      <p className="text-[11px] text-slate-600 leading-relaxed">
        Resolution: 10 m/px. Objects &lt;30 m may not be reliably detected.
        Verify significant findings with high-resolution imagery.
      </p>
    </div>
  )
}
