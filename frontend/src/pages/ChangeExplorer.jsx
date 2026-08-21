import { useState, useEffect, useRef, useCallback } from 'react'
import { getExplorerLocations, getExplorerLocation } from '../services/api.js'
import toast from 'react-hot-toast'

// ─── Static data ─────────────────────────────────────────────────────────────

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

// Article content — each entry becomes one illustrated card
const ARTICLE_SECTIONS = [
  {
    id: 'natural',
    icon: '🌊',
    tag: 'Natural Forces',
    tagColor: '#3b82f6',
    bgClass: 'from-blue-950/60 to-blue-950/10 border-blue-800/40',
    headline: 'The Earth Reshapes Itself',
    body: `Rivers meander and shift their courses over decades. Coastlines erode or accrete
metre by metre each year. Glaciers that took millennia to form retreat visibly within a single
generation. Volcanoes raise new land from the sea overnight. These processes are quiet,
relentless, and enormous in scale — yet they are invisible to a person standing on the ground.
From 700 km up, a satellite captures them all in a single frame.`,
    stat: { value: '24 m', label: 'avg. coastline shift per year globally', cite: 'IPCC, 2021' },
    visual: 'natural',
  },
  {
    id: 'urban',
    icon: '🏙️',
    tag: 'Urbanisation',
    tagColor: '#f97316',
    bgClass: 'from-orange-950/60 to-orange-950/10 border-orange-800/40',
    headline: 'Villages Become Cities in a Decade',
    body: `More than half of humanity lives in cities — up from 30% in 1950. The pace is
staggering. Satellite imagery over South Asian, East African, and Chinese cities shows
agricultural land giving way to roads, apartments, and commerce in just a few years.
The spectral signature is unmistakable: dense NDVI green replaced by the high reflectance
of concrete and metal roofing.`,
    stat: { value: '2.5 B', label: 'more urban residents projected by 2050', cite: 'UN World Urbanization Prospects' },
    visual: 'urban',
  },
  {
    id: 'infra',
    icon: '🛣️',
    tag: 'Infrastructure',
    tagColor: '#2d9e6d',
    bgClass: 'from-green-950/60 to-green-950/10 border-green-800/40',
    headline: 'Roads, Bridges & Dams as Landscape Surgery',
    body: `A highway cuts through a mountain range. A dam floods a valley the size of a small
country. A bridge stretches across open sea. Infrastructure leaves the most geometric change
signatures in satellite data — perfectly straight lines, symmetrical earthworks, and the
crisp shoreline that appears where land used to be. These are deliberate incisions in the
landscape, traded for connectivity, power, and economic reach.`,
    stat: { value: '64,000 km²', label: 'flooded by large dams worldwide', cite: 'World Commission on Dams' },
    visual: 'infra',
  },
  {
    id: 'agri',
    icon: '🌾',
    tag: 'Agriculture & Deforestation',
    tagColor: '#eab308',
    bgClass: 'from-yellow-950/60 to-yellow-950/10 border-yellow-800/40',
    headline: 'The Hunger for Productive Land',
    body: `Agriculture is the single largest driver of land-use change on Earth. Forests are
cleared for soy in Brazil, for palm oil in Borneo, for cotton in Central Asia. Seasonal
rhythms create a pulsing NDVI signal — fields green, golden, bare. But when permanent forest
becomes permanent farmland, the change is irreversible: a new, lower vegetation baseline
that persists in every subsequent image.`,
    stat: { value: '10 M ha', label: 'of forest lost per year (net)', cite: 'FAO Forest Resources Assessment' },
    visual: 'agri',
  },
  {
    id: 'consequences',
    icon: '⚖️',
    tag: 'Consequences',
    tagColor: '#a855f7',
    bgClass: 'from-purple-950/60 to-purple-950/10 border-purple-800/40',
    headline: 'Every Change Has a Ripple',
    body: `A new highway raises land values along its corridor, catalysing towns where there
were fields. A dam generates electricity but displaces communities and alters downstream
ecology. Urbanisation concentrates economic activity but amplifies heat-island effects and
stormwater runoff. Second-order consequences are rarely visible in one image — but comparing
data over time reveals the full cascade: the road, then the houses, then the shopping
centre, then the final stand of old trees gone.`,
    stat: { value: '55%', label: 'of Earth\'s ice-free land now altered by humans', cite: 'Nature, 2018' },
    visual: 'consequences',
  },
]

// ─── Inline SVG illustrations (before/after diagrams) ─────────────────────────

function IllustNatural() {
  return (
    <svg viewBox="0 0 300 150" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arN" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
          <polygon points="0,0 7,3.5 0,7" fill="#3b82f6" />
        </marker>
      </defs>
      {/* Background */}
      <rect width="300" height="150" fill="#0c1628" />
      {/* Stars */}
      {[[22, 14], [58, 9], [105, 19], [175, 11], [240, 16], [270, 28], [35, 38]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 2 ? 0.8 : 1.2} fill="#e2e8f0" opacity="0.4" />
      ))}
      {/* Sea */}
      <path d="M0 95 Q75 83 150 95 Q225 107 300 95 L300 150 L0 150Z" fill="#1e3a5f" />
      <path d="M0 100 Q37 95 75 100 Q112 105 150 100 Q187 95 225 100 Q262 105 300 100"
        fill="none" stroke="#60a5fa" strokeWidth="1" opacity="0.35" />

      {/* ── BEFORE panel (left) ── */}
      <text x="75" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">BEFORE · ~2012</text>
      {/* Cliff — intact */}
      <rect x="30" y="52" width="90" height="43" rx="3" fill="#374151" />
      <rect x="30" y="52" width="90" height="8" rx="3" fill="#4b5563" />
      {/* Glacier remnant */}
      <path d="M32 62 L55 52 L72 60 L68 95 L34 95Z" fill="#bfdbfe" opacity="0.22" />
      <text x="75" y="127" textAnchor="middle" fontSize="6.5" fill="#60a5fa">Intact cliff &amp; glacier</text>

      {/* Arrow */}
      <line x1="132" y1="73" x2="168" y2="73"
        stroke="#3b82f6" strokeWidth="1.8" markerEnd="url(#arN)" opacity="0.8" />
      <text x="150" y="67" textAnchor="middle" fontSize="6" fill="#3b82f6">erosion</text>

      {/* ── AFTER panel (right) ── */}
      <text x="225" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">AFTER · ~2024</text>
      {/* Cliff — eroded */}
      <path d="M180 52 L270 52 L270 95 L205 95 L182 78Z" fill="#374151" />
      <path d="M180 52 L270 52 L270 60 L205 60 L183 63Z" fill="#4b5563" />
      {/* Glacier — smaller */}
      <path d="M183 65 L198 55 L210 62 L207 95 L185 95Z" fill="#bfdbfe" opacity="0.14" />
      <text x="225" y="127" textAnchor="middle" fontSize="6.5" fill="#60a5fa">Eroded cliff, shrunk glacier</text>

      {/* Land labels */}
      <text x="75" y="140" textAnchor="middle" fontSize="5.5" fill="#475569">natural process</text>
      <text x="225" y="140" textAnchor="middle" fontSize="5.5" fill="#475569">~12 yrs later</text>
    </svg>
  )
}

function IllustUrban() {
  return (
    <svg viewBox="0 0 300 150" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arU" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
          <polygon points="0,0 7,3.5 0,7" fill="#f97316" />
        </marker>
      </defs>
      <rect width="300" height="150" fill="#0c1628" />

      {/* BEFORE — farmland */}
      <text x="72" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">BEFORE · 2008</text>
      <rect x="8" y="22" width="128" height="120" rx="3" fill="#14532d" opacity="0.55" />
      {/* Field grid */}
      {[[10, 24, 60, 44], [73, 24, 60, 44], [10, 72, 60, 44], [73, 72, 55, 44]].map(([x, y, w, h], i) => (
        <rect key={i} x={x} y={y} width={w} height={h} rx="2"
          fill={i % 2 === 0 ? '#166534' : '#15803d'} stroke="#0c1628" strokeWidth="1.2" />
      ))}
      <text x="72" y="152" textAnchor="middle" fontSize="6.5" fill="#86efac">Farmland</text>

      {/* Arrow */}
      <g transform="translate(150,80)">
        <line x1="-6" y1="0" x2="4" y2="0" stroke="#f97316" strokeWidth="2" markerEnd="url(#arU)" />
        <text x="-1" y="-5" textAnchor="middle" fontSize="6" fill="#f97316">urbanise</text>
      </g>

      {/* AFTER — city */}
      <text x="228" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">AFTER · 2024</text>
      <rect x="164" y="22" width="128" height="120" rx="3" fill="#334155" opacity="0.55" />
      {/* Buildings */}
      {[
        [167, 75, 22, 67, '#475569'], [193, 58, 16, 84, '#334155'], [213, 78, 22, 64, '#3f4f6b'],
        [239, 62, 18, 80, '#4a5568'], [261, 80, 16, 62, '#374151'],
        [167, 32, 28, 40, '#1e40af'], [198, 36, 20, 20, '#1e3a8a'],
      ].map(([x, y, w, h, c], i) => <rect key={i} x={x} y={y} width={w} height={h} rx="1" fill={c} />)}
      {/* Roads */}
      <rect x="164" y="104" width="128" height="5" fill="#1e293b" />
      <rect x="232" y="22" width="5" height="120" fill="#1e293b" />
      {/* Windows */}
      {[[170, 80], [170, 92], [196, 64], [196, 76], [216, 84], [242, 68], [264, 86]].map(([x, y], i) => (
        <rect key={i} x={x} y={y} width="4" height="3" fill="#fbbf24" opacity="0.75" />
      ))}
      <text x="228" y="152" textAnchor="middle" fontSize="6.5" fill="#fb923c">Dense built-up</text>
    </svg>
  )
}

function IllustInfra() {
  return (
    <svg viewBox="0 0 300 150" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arI" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
          <polygon points="0,0 7,3.5 0,7" fill="#2d9e6d" />
        </marker>
      </defs>
      <rect width="300" height="150" fill="#0c1628" />
      {/* Water channel */}
      <rect x="0" y="58" width="300" height="34" fill="#1e3a5f" />
      <path d="M0 62 Q75 57 150 62 Q225 67 300 62" fill="none" stroke="#3b82f6" strokeWidth="1" opacity="0.3" />
      {/* Land */}
      <rect x="0" y="0" width="300" height="58" fill="#1a2e1e" />
      <rect x="0" y="92" width="300" height="58" fill="#1a2e1e" />

      {/* BEFORE */}
      <text x="65" y="11" textAnchor="middle" fontSize="7.5" fill="#94a3b8">BEFORE · 2015</text>
      <rect x="8" y="14" width="114" height="44" rx="2" fill="#14532d" opacity="0.4" />
      <rect x="8" y="92" width="114" height="44" rx="2" fill="#14532d" opacity="0.4" />
      <text x="65" y="148" textAnchor="middle" fontSize="6.5" fill="#64748b">No crossing</text>

      {/* Arrow */}
      <line x1="130" y1="75" x2="166" y2="75"
        stroke="#2d9e6d" strokeWidth="2" markerEnd="url(#arI)" />
      <text x="148" y="68" textAnchor="middle" fontSize="6" fill="#2d9e6d">build</text>

      {/* AFTER — bridge */}
      <text x="235" y="11" textAnchor="middle" fontSize="7.5" fill="#94a3b8">AFTER · 2024</text>
      <rect x="178" y="14" width="114" height="44" rx="2" fill="#14532d" opacity="0.4" />
      <rect x="178" y="92" width="114" height="44" rx="2" fill="#14532d" opacity="0.4" />
      {/* Bridge deck */}
      <rect x="178" y="70" width="114" height="7" rx="1" fill="#64748b" />
      {/* Pillars */}
      {[205, 233, 261].map(x => (
        <rect key={x} x={x} y="60" width="5" height="28" fill="#475569" />
      ))}
      {/* Approach roads */}
      <rect x="178" y="72" width="18" height="3" fill="#374151" />
      <rect x="274" y="72" width="18" height="3" fill="#374151" />
      <text x="235" y="148" textAnchor="middle" fontSize="6.5" fill="#4ade80">Bridge built</text>
    </svg>
  )
}

function IllustAgri() {
  return (
    <svg viewBox="0 0 300 150" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arA" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
          <polygon points="0,0 7,3.5 0,7" fill="#eab308" />
        </marker>
      </defs>
      <rect width="300" height="150" fill="#0c1628" />

      {/* BEFORE — forest */}
      <text x="72" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">BEFORE · Forest</text>
      <rect x="8" y="20" width="128" height="118" rx="3" fill="#14532d" opacity="0.75" />
      {/* Canopy circles */}
      {[[22, 34], [44, 27], [66, 38], [90, 28], [108, 40],
      [20, 58], [42, 50], [65, 60], [88, 52], [110, 62],
      [25, 80], [50, 74], [72, 84], [96, 72], [112, 82],
      [28, 102], [55, 96], [78, 106], [100, 98], [115, 108]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={4.5 + Math.cos(i) * 1}
          fill={i % 3 === 0 ? '#166534' : i % 3 === 1 ? '#15803d' : '#16a34a'} />
      ))}
      <text x="72" y="148" textAnchor="middle" fontSize="6.5" fill="#86efac">Dense canopy</text>

      {/* Arrow */}
      <g transform="translate(150,80)">
        <line x1="-7" y1="0" x2="3" y2="0" stroke="#eab308" strokeWidth="2" markerEnd="url(#arA)" />
        <text x="-2" y="-5" textAnchor="middle" fontSize="6" fill="#eab308">clear-cut</text>
      </g>

      {/* AFTER — farmland */}
      <text x="228" y="14" textAnchor="middle" fontSize="7.5" fill="#94a3b8">AFTER · Cropland</text>
      <rect x="164" y="20" width="128" height="118" rx="3" fill="#713f12" opacity="0.45" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map(row => (
        <rect key={row} x="166" y={22 + row * 14} width="124" height="10" rx="1"
          fill={row % 2 === 0 ? '#a16207' : '#ca8a04'} opacity="0.65" />
      ))}
      {/* Deforestation edge */}
      <rect x="164" y="20" width="128" height="118" rx="3"
        fill="none" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="5,3" opacity="0.7" />
      <text x="228" y="148" textAnchor="middle" fontSize="6.5" fill="#facc15">Agricultural conversion</text>
    </svg>
  )
}

function IllustConsequences() {
  const nodes = [
    { x: 30, y: 28, label: 'Land values', sub: 'rise', color: '#f97316' },
    { x: 270, y: 28, label: 'Heat island', sub: 'effect', color: '#ef4444' },
    { x: 270, y: 122, label: 'Flood risk', sub: 'increases', color: '#3b82f6' },
    { x: 30, y: 122, label: 'Habitat', sub: 'lost', color: '#22c55e' },
    { x: 150, y: 12, label: 'Economic', sub: 'growth', color: '#eab308' },
    { x: 150, y: 138, label: 'Displaced', sub: 'communities', color: '#94a3b8' },
  ]
  return (
    <svg viewBox="0 0 300 150" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <rect width="300" height="150" fill="#0c1628" />
      {/* Spokes */}
      {nodes.map(({ x, y, color }, i) => (
        <line key={i} x1="150" y1="75" x2={x} y2={y}
          stroke={color} strokeWidth="1" opacity="0.4" strokeDasharray="4,3" />
      ))}
      {/* Centre */}
      <circle cx="150" cy="75" r="26" fill="#3b0764" stroke="#a855f7" strokeWidth="2" />
      <text x="150" y="71" textAnchor="middle" fontSize="7.5" fill="#e9d5ff" fontWeight="bold">Land</text>
      <text x="150" y="81" textAnchor="middle" fontSize="7.5" fill="#e9d5ff" fontWeight="bold">Change</text>
      {/* Consequence nodes */}
      {nodes.map(({ x, y, label, sub, color }, i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="18" fill={color} opacity="0.12" stroke={color} strokeWidth="1" opacity2="0.5" />
          <text x={x} y={y - 4} textAnchor="middle" fontSize="6" fill={color} fontWeight="600">{label}</text>
          <text x={x} y={y + 5} textAnchor="middle" fontSize="6" fill={color}>{sub}</text>
        </g>
      ))}
    </svg>
  )
}

const ILLUSTRATIONS = {
  natural: IllustNatural,
  urban: IllustUrban,
  infra: IllustInfra,
  agri: IllustAgri,
  consequences: IllustConsequences,
}

// ─── Utility: intersection-observer fade-in ───────────────────────────────────

function useFadeIn(threshold = 0.15) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return [ref, visible]
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function ArticleHero() {
  const [ref, vis] = useFadeIn(0.05)
  return (
    <div
      ref={ref}
      className={`relative rounded-2xl overflow-hidden border border-slate-700/50 mb-5
                  transition-all duration-700 ${vis ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}
    >
      {/* Illustrated background */}
      <div className="absolute inset-0 pointer-events-none select-none overflow-hidden">
        <svg viewBox="0 0 900 210" preserveAspectRatio="xMidYMid slice"
          className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="hSky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id="hEarth" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1a2e1e" />
              <stop offset="100%" stopColor="#0f1a10" />
            </linearGradient>
          </defs>
          <rect width="900" height="210" fill="url(#hSky)" />
          {/* Stars */}
          {[[48, 18], [118, 10], [198, 28], [308, 7], [448, 20], [568, 12], [676, 23], [796, 16], [876, 30],
          [28, 44], [158, 36], [288, 48], [408, 33], [528, 40], [656, 33], [788, 43]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.2 : 0.7} fill="white"
              opacity={0.25 + Math.sin(i) * 0.15} />
          ))}
          {/* Satellite orbit arc */}
          <ellipse cx="450" cy="0" rx="340" ry="170" fill="none"
            stroke="#2d9e6d" strokeWidth="1" strokeDasharray="8,6" opacity="0.18" />
          {/* Satellite */}
          <g transform="translate(745,36) rotate(-28)">
            <rect x="-6" y="-3.5" width="12" height="7" rx="1.5" fill="#64748b" />
            <rect x="-15" y="-1.5" width="8" height="3" fill="#3b82f6" opacity="0.85" />
            <rect x="7" y="-1.5" width="8" height="3" fill="#3b82f6" opacity="0.85" />
          </g>
          {/* Ground */}
          <path d="M0 155 Q150 138 300 152 Q450 166 600 144 Q750 126 900 148 L900 210 L0 210Z"
            fill="url(#hEarth)" />
          {/* City skyline (right) */}
          {[[676, 138, 20, 62], [700, 122, 15, 78], [718, 136, 22, 64], [742, 128, 17, 72],
          [762, 143, 15, 57], [780, 126, 19, 74], [802, 140, 13, 60]].map(([x, y, w, h], i) => (
            <rect key={i} x={x} y={y} width={w} height={h} rx="1"
              fill={['#1e3a5f', '#1e293b', '#1e3a5f', '#0f2644', '#1e293b', '#1e3a5f', '#0f2644'][i]}
              opacity="0.9" />
          ))}
          {/* Farm patches (left) */}
          {[[28, 158, 82, 52], [118, 154, 72, 56], [198, 161, 62, 49]].map(([x, y, w, h], i) => (
            <rect key={i} x={x} y={y} width={w} height={h}
              fill={i === 0 ? '#14532d' : i === 1 ? '#166534' : '#15803d'} opacity="0.55" />
          ))}
          {/* Road */}
          <path d="M278 210 L418 160 L900 150" fill="none" stroke="#334155" strokeWidth="5.5" opacity="0.8" />
          <path d="M278 210 L418 160 L900 150" fill="none" stroke="#475569" strokeWidth="1.5"
            strokeDasharray="14,9" opacity="0.4" />
          {/* Scan lines */}
          <rect width="900" height="210" fill="none"
            stroke="rgba(45,158,109,0.04)" strokeWidth="1" strokeDasharray="1,4" />
        </svg>
      </div>

      {/* Overlay gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-slate-950/85 via-slate-950/55 to-transparent" />

      {/* Text */}
      <div className="relative px-7 py-8 max-w-lg">
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary-l mb-2">
          TerraDelta · Change Explorer
        </div>
        <h2 className="text-2xl md:text-3xl font-black text-slate-100 leading-tight mb-3">
          Change Is The<br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-l to-green-300">
            Only Constant
          </span>
        </h2>
        <p className="text-sm text-slate-400 leading-relaxed mb-4 max-w-sm">
          Every satellite image is a moment frozen in time. Lay two moments side by side and
          you begin to see the forces — geological, climatic, human — that are continuously
          redrawing our world.
        </p>
        {/* Thematic key */}
        <div className="flex flex-wrap gap-3">
          {[
            ['#3b82f6', 'Natural'], ['#f97316', 'Urban'], ['#2d9e6d', 'Infrastructure'],
            ['#eab308', 'Agriculture'], ['#a855f7', 'Consequences'],
          ].map(([c, l]) => (
            <div key={l} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: c }} />
              <span className="text-[11px] text-slate-400">{l}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scroll cue */}
      <div className="absolute bottom-3 right-4 text-[10px] text-slate-600 flex items-center gap-1">
        scroll <span className="animate-bounce">↓</span>
      </div>
    </div>
  )
}

// ─── Article card ──────────────────────────────────────────────────────────────

function ArticleCard({ section, index }) {
  const [ref, vis] = useFadeIn(0.12)
  const [expanded, setExpanded] = useState(false)
  const Illustration = ILLUSTRATIONS[section.visual]
  const isEven = index % 2 === 0

  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ${vis ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
      style={{ transitionDelay: `${index * 55}ms` }}
    >
      <div className={`rounded-2xl border bg-gradient-to-br overflow-hidden ${section.bgClass}`}>
        <div className={`flex flex-col ${isEven ? 'md:flex-row' : 'md:flex-row-reverse'}`}>

          {/* Illustration pane */}
          <div className={`md:w-[42%] shrink-0 bg-slate-950/50
                           border-b md:border-b-0
                           ${isEven ? 'md:border-r' : 'md:border-l'}
                           border-white/5 p-3 flex items-center min-h-[148px]`}>
            <Illustration />
          </div>

          {/* Text pane */}
          <div className="flex-1 p-4 flex flex-col gap-3 justify-between">
            <div>
              {/* Tag */}
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{section.icon}</span>
                <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border"
                  style={{
                    color: section.tagColor,
                    borderColor: section.tagColor + '55',
                    background: section.tagColor + '18',
                  }}>
                  {section.tag}
                </span>
              </div>

              {/* Headline */}
              <h3 className="text-[15px] font-bold text-slate-100 leading-snug mb-2">
                {section.headline}
              </h3>

              {/* Body — clamp with expand */}
              <p className={`text-[12px] text-slate-400 leading-relaxed
                             ${expanded ? '' : 'line-clamp-4'}`}>
                {section.body}
              </p>
              <button
                onClick={() => setExpanded(e => !e)}
                className="text-[11px] mt-1 font-semibold transition-colors hover:opacity-80"
                style={{ color: section.tagColor }}
              >
                {expanded ? '↑ less' : '↓ more'}
              </button>
            </div>

            {/* Stat chip */}
            <div className="flex items-center gap-3 rounded-xl px-3 py-2
                            bg-slate-950/50 border border-white/5">
              <div className="text-xl font-black tabular-nums leading-none"
                style={{ color: section.tagColor }}>
                {section.stat.value}
              </div>
              <div>
                <div className="text-[11px] text-slate-300 leading-tight">{section.stat.label}</div>
                <div className="text-[10px] text-slate-600 mt-0.5">{section.stat.cite}</div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

// ─── Bridge to game ───────────────────────────────────────────────────────────

function GameBridge() {
  const [ref, vis] = useFadeIn(0.15)
  return (
    <div
      ref={ref}
      className={`my-6 rounded-2xl border border-primary/30 bg-primary/5
                  px-5 py-4 flex flex-col md:flex-row items-center gap-4
                  transition-all duration-700 ${vis ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'}`}
    >
      <span className="text-4xl shrink-0 select-none">🛰️</span>
      <div className="flex-1">
        <div className="text-[10px] font-bold uppercase tracking-widest text-primary-l mb-1">
          Now it's your turn
        </div>
        <h3 className="text-base font-bold text-slate-100 mb-1">
          Can you spot the change from space?
        </h3>
        <p className="text-sm text-slate-400 leading-snug">
          Below are real locations where significant changes happened. Study the before &amp; after
          satellite images, guess the change type and place name — then reveal the verified answer.
        </p>
      </div>
      <div className="shrink-0 flex items-center gap-1.5 bg-primary/20 border border-primary/40
                      rounded-xl px-4 py-2 text-sm font-semibold text-primary-l whitespace-nowrap">
        Play below <span className="animate-bounce inline-block">↓</span>
      </div>
    </div>
  )
}

// ─── Game: image panel ────────────────────────────────────────────────────────

function ImagePanel({ url, label, year }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    setFailed(false)
  }, [url])
  const imageUrl = url?.startsWith('/explorer-static/')
    ? `${(import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/api$/, '')}${url}`
    : url
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">
        {label} · {year}
      </div>
      <div className="relative rounded-xl overflow-hidden bg-slate-800 aspect-video
                      border border-border flex items-center justify-center">
        {url && !failed ? (
          <img
            src={imageUrl}
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

// ─── Game: explorer card ──────────────────────────────────────────────────────

function ExplorerCard({ location, onNext, onPrev, index, total }) {
  const [revealed, setRevealed] = useState(false)
  const [guessType, setGuessType] = useState('')
  const [guessName, setGuessName] = useState('')
  const [score, setScore] = useState(null)

  // Reset state whenever the location changes
  useEffect(() => {
    setRevealed(false)
    setGuessType('')
    setGuessName('')
    setScore(null)
  }, [location?.id])

  if (!location) return null

  const {
    title, hint, category,
    before_year, after_year,
    before_url, after_url,
    change_url,   // preserved from original destructuring
    reveal,
  } = location

  const handleReveal = () => {
    if (!guessType && !guessName) {
      toast('Make a guess before revealing!', { icon: '🤔' })
      return
    }
    setScore(guessType === category ? 1 : 0)
    setRevealed(true)
  }

  return (
    <div className="max-w-4xl mx-auto">

      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
            Location {index + 1} of {total}
          </div>
          <h2 className="text-xl font-semibold text-slate-100 leading-snug">{title}</h2>
        </div>
        <div className="flex gap-2 shrink-0">
          <button onClick={onPrev} className="btn-secondary px-3 py-1.5 text-sm">← Prev</button>
          <button onClick={onNext} className="btn-secondary px-3 py-1.5 text-sm">Next →</button>
        </div>
      </div>

      {/* ── Hint ── */}
      <div className="card mb-4 border-l-2 border-primary-l">
        <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Hint</div>
        <p className="text-sm text-slate-200 leading-relaxed">{hint}</p>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          <span>📍 {location.region}</span>
          <span>·</span>
          <span>📅 {before_year} → {after_year}</span>
        </div>
      </div>

      {/* ── Before / After images ── */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <ImagePanel url={before_url} label="Before" year={before_year} />
        <ImagePanel url={after_url} label="After" year={after_year} />
      </div>

      {/* ── Guess form ── */}
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
                {CHANGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <button onClick={handleReveal} className="btn-primary mt-4 w-full">
            🔍 Reveal Answer
          </button>
        </div>
      )}

      {/* ── Reveal panel ── */}
      {revealed && reveal && (
        <div className="card fade-in-up border border-primary/40">
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-xs text-primary-l uppercase tracking-wider mb-1">
                Answer Revealed
              </div>
              <h3 className="text-lg font-bold text-slate-100">📍 {reveal.name}</h3>
              <div className="text-sm text-accent font-medium">🏗️ {reveal.change_type}</div>
            </div>
            {score !== null && (
              <div className={`px-3 py-1.5 rounded-lg text-sm font-bold ${score > 0
                ? 'bg-green-900/50 text-green-400 border border-green-700'
                : 'bg-slate-800 text-slate-400'
                }`}>
                {score > 0 ? '✓ Correct type!' : 'Keep exploring!'}
              </div>
            )}
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            {[
              { label: 'Changed Area', value: `${reveal.stats?.changed_area_ha} ha` },
              { label: 'Change %', value: `${reveal.stats?.change_percent}%` },
              { label: 'Confidence', value: `${Math.round((reveal.stats?.mean_confidence ?? 0) * 100)}%` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/50 rounded-lg p-2.5 text-center">
                <div className="text-xs text-slate-400 mb-1">{label}</div>
                <div className="text-sm font-semibold text-accent">{value}</div>
              </div>
            ))}
          </div>

          <p className="text-sm text-slate-300 leading-relaxed">{reveal.description}</p>

          <div className="flex gap-2 mt-4">
            <button onClick={onNext} className="btn-primary flex-1">
              Next Location →
            </button>
          </div>
        </div>
      )}

    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ChangeExplorer() {
  const [locations, setLocations] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [fullLocation, setFullLocation] = useState(null)

  // Load location list
  useEffect(() => {
    getExplorerLocations()
      .then(data => { setLocations(data.locations || []); setLoading(false) })
      .catch(() => { toast.error('Failed to load Explorer locations'); setLoading(false) })
  }, [])

  // Load full detail for current location
  useEffect(() => {
    if (!locations.length) return
    const loc = locations[currentIndex]
    if (!loc) return
    getExplorerLocation(loc.id)
      .then(setFullLocation)
      .catch(() => setFullLocation(locations[currentIndex]))
  }, [currentIndex, locations])

  const goNext = useCallback(
    () => setCurrentIndex(i => (i + 1) % locations.length),
    [locations.length]
  )
  const goPrev = useCallback(
    () => setCurrentIndex(i => (i - 1 + locations.length) % locations.length),
    [locations.length]
  )

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading Explorer…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto bg-dark">

      {/* ── Sticky page header ── */}
      <div className="border-b border-border bg-card px-6 py-3 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-slate-100">Change Explorer</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Explore real satellite imagery of major landscape-change events. Can you guess where?
            </p>
          </div>
          {/* Navigation dots */}
          <div className="flex gap-1.5 shrink-0">
            {locations.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentIndex(i)}
                className={`w-2 h-2 rounded-full transition-colors ${i === currentIndex ? 'bg-primary-l' : 'bg-slate-600 hover:bg-slate-500'
                  }`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="p-6 max-w-4xl mx-auto">

        {/* ── Article ── */}
        <ArticleHero />

        <div className="flex flex-col gap-4 mb-2">
          {ARTICLE_SECTIONS.map((section, i) => (
            <ArticleCard key={section.id} section={section} index={i} />
          ))}
        </div>

        {/* ── Bridge ── */}
        <GameBridge />

        {/* ── Game divider ── */}
        <div className="flex items-center gap-3 mb-6">
          <div className="h-px flex-1 bg-border" />
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 px-2 select-none">
            🌍 Change Explorer Game
          </div>
          <div className="h-px flex-1 bg-border" />
        </div>

        {/* ── Game ── */}
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
