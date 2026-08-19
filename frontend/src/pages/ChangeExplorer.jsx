import { useState, useEffect } from 'react'
import { getExplorerLocations, getExplorerLocation } from '../services/api.js'
import toast from 'react-hot-toast'

const CHANGE_TYPES = [
  'Bridge / Infrastructure',
  'Urban Development',
  'Airport Infrastructure',
  'Land Reclamation',
  'Smart City Development',
  'Industrial / Port',
  'Megaproject',
  'Urban Sprawl',
  'Other',
]

const CHANGE_DIMENSIONS = [
  {
    icon: '💰',
    title: 'Economic Change',
    text: 'Rising incomes and investment drive demand for housing, retail, and industry — visible as new construction and expanding built-up footprints.',
  },
  {
    icon: '🌍',
    title: 'Geographical Change',
    text: 'Coastlines, riverbanks, and land reclamation reshape the physical map itself, sometimes over just a few years.',
  },
  {
    icon: '🏙️',
    title: 'Urbanisation',
    text: 'Villages become towns and towns become cities as populations concentrate, replacing farmland with roads, housing, and commerce.',
  },
  {
    icon: '🌉',
    title: 'Infrastructure Development',
    text: 'Bridges, airports, highways, and power corridors leave distinctive linear and clustered signatures in satellite change maps.',
  },
  {
    icon: '🌾',
    title: 'Land-Use Change',
    text: 'Agricultural, forest, or barren land is repurposed for industry, housing, or conservation — often the earliest visible signal of change.',
  },
  {
    icon: '🌦️',
    title: 'Environmental & Climatic Change',
    text: 'Flooding, drought, deforestation, and glacial retreat alter land cover independent of direct human construction.',
  },
  {
    icon: '🏗️',
    title: 'Human-Made Change',
    text: 'From single buildings to entire planned cities, deliberate human activity is the dominant driver of change visible from space today.',
  },
]

function ChangeIntro() {
  return (
    <div className="max-w-4xl mx-auto mb-8">
      <div className="text-center mb-5">
        <h2 className="text-2xl font-bold text-slate-100 mb-1">Change Is The Only Constant</h2>
        <p className="text-sm text-slate-400 max-w-2xl mx-auto">
          Every satellite image is a snapshot of a moment. Compare two moments and you see
          the forces reshaping our planet — most of them driven by us.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {CHANGE_DIMENSIONS.map(d => (
          <div key={d.title} className="card py-3 px-3">
            <div className="text-xl mb-1">{d.icon}</div>
            <div className="text-xs font-semibold text-slate-200 mb-1">{d.title}</div>
            <div className="text-[11px] text-slate-400 leading-snug">{d.text}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ImagePanel({ url, label, year }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">{label} · {year}</div>
      <div className="relative rounded-xl overflow-hidden bg-slate-800 aspect-video border border-border flex items-center justify-center">
        {url && !failed ? (
          <img
            src={url}
            alt={label}
            className="w-full h-full object-cover"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <span className="text-3xl">🛰️</span>
            <span className="text-xs">Satellite image not available</span>
            <span className="text-[10px] text-slate-600">Add images to backend/explorer_data/</span>
          </div>
        )}
      </div>
    </div>
  )
}

function ExplorerCard({ location, onNext, onPrev, index, total }) {
  const [revealed, setRevealed] = useState(false)
  const [guessType, setGuessType] = useState('')
  const [guessName, setGuessName] = useState('')
  const [score, setScore] = useState(null)

  useEffect(() => {
    setRevealed(false)
    setGuessType('')
    setGuessName('')
    setScore(null)
  }, [location?.id])

  if (!location) return null

  const { title, hint, category, before_year, after_year,
          before_url, after_url, change_url, reveal } = location

  const handleReveal = async () => {
    if (!guessType && !guessName) {
      toast('Make a guess before revealing!', { icon: '🤔' })
      return
    }
    // Score: simple check
    const typeMatch = guessType === category
    const s = typeMatch ? 1 : 0
    setScore(s)
    setRevealed(true)
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
            Location {index + 1} of {total}
          </div>
          <h2 className="text-xl font-semibold text-slate-100">{title}</h2>
        </div>
        <div className="flex gap-2">
          <button onClick={onPrev} className="btn-secondary px-3 py-1.5 text-sm">← Prev</button>
          <button onClick={onNext} className="btn-secondary px-3 py-1.5 text-sm">Next →</button>
        </div>
      </div>

      {/* Hint */}
      <div className="card mb-6 border-l-2 border-primary-l">
        <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Hint</div>
        <p className="text-sm text-slate-200 leading-relaxed">{hint}</p>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          <span>📍 {location.region}</span>
          <span>·</span>
          <span>📅 {before_year} → {after_year}</span>
        </div>
      </div>

      {/* Images */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <ImagePanel url={before_url} label="Before" year={before_year} blur={false} />
        <ImagePanel url={after_url}  label="After"  year={after_year}  blur={revealed ? false : false} />
      </div>

      {/* Guess form */}
      {!revealed && (
        <div className="card mb-4">
          <div className="section-title mb-3">Your Guess</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Place name (optional)</label>
              <input
                type="text"
                value={guessName}
                onChange={e => setGuessName(e.target.value)}
                placeholder="e.g. Mumbai, India"
                className="input-field"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Type of change</label>
              <select
                value={guessType}
                onChange={e => setGuessType(e.target.value)}
                className="input-field"
              >
                <option value="" disabled>Select change type…</option>
                {CHANGE_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
          <button
            onClick={handleReveal}
            className="btn-primary mt-4 w-full"
          >
            🔍 Reveal Answer
          </button>
        </div>
      )}

      {/* Reveal panel */}
      {revealed && reveal && (
        <div className="card fade-in-up border border-primary/40">
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-xs text-primary-l uppercase tracking-wider mb-1">Answer Revealed</div>
              <h3 className="text-lg font-bold text-slate-100">📍 {reveal.name}</h3>
              <div className="text-sm text-accent font-medium">🏗️ {reveal.change_type}</div>
            </div>
            {score !== null && (
              <div className={`px-3 py-1.5 rounded-lg text-sm font-bold ${
                score > 0 ? 'bg-green-900/50 text-green-400 border border-green-700' : 'bg-slate-800 text-slate-400'
              }`}>
                {score > 0 ? '✓ Correct type!' : 'Keep exploring!'}
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            {[
              { label: 'Changed Area', value: `${reveal.stats?.changed_area_ha} ha` },
              { label: 'Change %',     value: `${reveal.stats?.change_percent}%` },
              { label: 'Confidence',   value: `${Math.round(reveal.stats?.mean_confidence * 100)}%` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/50 rounded-lg p-2.5 text-center">
                <div className="text-xs text-slate-400 mb-1">{label}</div>
                <div className="text-sm font-semibold text-accent">{value}</div>
              </div>
            ))}
          </div>

          <p className="text-sm text-slate-300 leading-relaxed">{reveal.description}</p>

          <div className="flex gap-2 mt-4">
            <button
              onClick={onNext}
              className="btn-primary flex-1"
            >
              Next Location →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChangeExplorer() {
  const [locations, setLocations] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [fullLocation, setFullLocation] = useState(null)

  useEffect(() => {
    getExplorerLocations()
      .then(data => {
        setLocations(data.locations || [])
        setLoading(false)
      })
      .catch(() => {
        toast.error('Failed to load Explorer locations')
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!locations.length) return
    const loc = locations[currentIndex]
    if (!loc) return
    getExplorerLocation(loc.id)
      .then(setFullLocation)
      .catch(() => setFullLocation(locations[currentIndex]))
  }, [currentIndex, locations])

  const goNext = () => setCurrentIndex(i => (i + 1) % locations.length)
  const goPrev = () => setCurrentIndex(i => (i - 1 + locations.length) % locations.length)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading Explorer...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto bg-dark">
      {/* Page header */}
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Change Explorer</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Explore real satellite imagery of major human development events. Can you guess where?
            </p>
          </div>
          <div className="flex gap-1">
            {locations.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentIndex(i)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === currentIndex ? 'bg-primary-l' : 'bg-slate-600 hover:bg-slate-500'
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="p-6">
        <ChangeIntro />
        <ExplorerCard
          location={fullLocation}
          index={currentIndex}
          total={locations.length}
          onNext={goNext}
          onPrev={goPrev}
        />
      </div>
    </div>
  )
}
