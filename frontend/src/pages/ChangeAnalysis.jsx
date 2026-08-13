import { useState, useCallback } from 'react'
import BaseMap from '../components/map/BaseMap.jsx'
import AnalysisForm from '../components/panels/AnalysisForm.jsx'
import ResultsPanel from '../components/panels/ResultsPanel.jsx'
import LoadingOverlay from '../components/shared/LoadingOverlay.jsx'
import { useAnalysisStore } from '../store/analysisStore.js'

export default function ChangeAnalysis() {
  const {
    bbox, setBbox, result, activeLayer,
    jobStatus, jobProgress, jobMessage,
  } = useAnalysisStore()

  const [drawMode, setDrawMode] = useState(false)
  const [flyTo, setFlyTo]       = useState(null)
  const [geojson, setGeojson]   = useState(null)
  const [progress, setProgress] = useState({ pct: 0, msg: '' })

  const handleBboxChange = useCallback((newBbox) => {
    setBbox(newBbox)
    setDrawMode(false)
  }, [setBbox])

  const handleResult = useCallback((res) => {
    setGeojson(null)
    // Load GeoJSON from server
    if (res.change_geojson_url) {
      fetch(res.change_geojson_url)
        .then(r => r.json())
        .then(setGeojson)
        .catch(() => {})
    }
  }, [])

  const handleProgress = useCallback((pct, msg) => {
    setProgress({ pct, msg })
  }, [])

  const isRunning = ['queued', 'processing'].includes(jobStatus)

  // Compute overlay bounds from bbox
  const overlayBounds = bbox
    ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
    : null

  return (
    <div className="flex h-full">
      {/* ── Left sidebar ─────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r border-border bg-card flex flex-col overflow-y-auto">
        <div className="p-4 border-b border-border">
          <h1 className="font-semibold text-slate-100">Change Analysis</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Detect human-caused changes between two satellite images
          </p>
        </div>

        <div className="p-4 flex flex-col gap-5 flex-1">
          <AnalysisForm
            onFlyTo={setFlyTo}
            onResult={handleResult}
            onProgress={handleProgress}
            drawMode={drawMode}
            onDrawModeChange={setDrawMode}
          />

          {/* Loading state */}
          {isRunning && (
            <div className="card">
              <LoadingOverlay progress={progress.pct} message={progress.msg} />
            </div>
          )}

          {/* Results */}
          {result && !isRunning && <ResultsPanel />}
        </div>
      </aside>

      {/* ── Map area ──────────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <BaseMap
          center={[20.5, 78.9]}
          zoom={5}
          flyTo={flyTo}
          drawMode={drawMode}
          onBboxChange={handleBboxChange}
          bbox={bbox}
          beforeUrl={result?.before_image_url}
          afterUrl={result?.after_image_url}
          changeMaskUrl={result?.change_mask_url}
          changeGeojson={geojson}
          activeLayer={activeLayer}
          overlayBounds={overlayBounds}
        />

        {/* Result layer switcher overlay (top-left of map) */}
        {result && (
          <div className="absolute top-3 left-3 z-[1000] flex gap-1">
            {[
              { id: 'before', label: 'Before' },
              { id: 'after',  label: 'After' },
              { id: 'change', label: '⚡ Changes' },
            ].map(({ id, label }) => {
              const { activeLayer: al, setActiveLayer } = useAnalysisStore.getState()
              return (
                <button
                  key={id}
                  onClick={() => setActiveLayer(id)}
                  className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                    activeLayer === id
                      ? id === 'change'
                        ? 'bg-accent text-white'
                        : 'bg-primary text-white'
                      : 'bg-card/90 text-slate-300 hover:bg-card border border-border'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
