import { useEffect, useRef, useState, useCallback } from 'react'
import { MapContainer, TileLayer, ImageOverlay, GeoJSON, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet default icon issue with bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const TILE_LAYERS = {
  satellite: {
    url:         'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom:     19,
  },
  osm: {
    url:         'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom:     19,
  },
}

// Sub-component: draws rectangle AOI on drag
function AOIDrawer({ onBboxChange, enabled }) {
  const map = useMap()
  const rectRef = useRef(null)
  const startRef = useRef(null)
  const [drawing, setDrawing] = useState(false)

  useEffect(() => {
    if (!enabled) return
    map.dragging.disable()
    map.getContainer().style.cursor = 'crosshair'
    return () => {
      map.dragging.enable()
      map.getContainer().style.cursor = ''
    }
  }, [enabled, map])

  useMapEvents({
    mousedown(e) {
      if (!enabled) return
      startRef.current = e.latlng
      setDrawing(true)
      if (rectRef.current) { map.removeLayer(rectRef.current); rectRef.current = null }
    },
    mousemove(e) {
      if (!enabled || !drawing || !startRef.current) return
      const bounds = L.latLngBounds(startRef.current, e.latlng)
      if (rectRef.current) map.removeLayer(rectRef.current)
      rectRef.current = L.rectangle(bounds, {
        color: '#f97316', weight: 2, dashArray: '6,4',
        fillColor: '#f97316', fillOpacity: 0.08,
      }).addTo(map)
    },
    mouseup(e) {
      if (!enabled || !drawing || !startRef.current) return
      setDrawing(false)
      const sw = startRef.current
      const ne = e.latlng
      if (Math.abs(sw.lat - ne.lat) < 0.001 || Math.abs(sw.lng - ne.lng) < 0.001) return
      const bbox = [
        Math.min(sw.lng, ne.lng),
        Math.min(sw.lat, ne.lat),
        Math.max(sw.lng, ne.lng),
        Math.max(sw.lat, ne.lat),
      ]
      onBboxChange(bbox)
    },
  })
  return null
}

// Sub-component: fly to location
function MapFlyTo({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center, zoom || 12, { duration: 1.5 })
  }, [center, zoom, map])
  return null
}

// GeoJSON style for change polygons
const changeStyle = {
  color:       '#f97316',
  weight:      1.5,
  fillColor:   '#ef4444',
  fillOpacity: 0.3,
}

function onEachFeature(feature, layer) {
  const { area_ha, confidence, cluster_id } = feature.properties || {}
  layer.bindPopup(`
    <div style="min-width:140px">
      <div style="font-weight:600;margin-bottom:6px;color:#f97316">Cluster #${cluster_id}</div>
      <div style="font-size:12px;color:#94a3b8">Area</div>
      <div style="font-size:14px;font-weight:600">${area_ha} ha</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:4px">Confidence</div>
      <div style="font-size:14px;font-weight:600">${(confidence * 100).toFixed(0)}%</div>
    </div>
  `)
  layer.on('mouseover', () => layer.setStyle({ fillOpacity: 0.55 }))
  layer.on('mouseout',  () => layer.setStyle({ fillOpacity: 0.3 }))
}

export default function BaseMap({
  center = [20.5, 78.9],
  zoom = 5,
  flyTo = null,
  tileType = 'satellite',
  drawMode = false,
  onBboxChange,
  bbox = null,
  // Overlay props
  beforeUrl = null,
  afterUrl = null,
  changeMaskUrl = null,
  changeGeojson = null,
  activeLayer = 'after',  // before | after | change
  overlayBounds = null,   // [[lat_min, lon_min], [lat_max, lon_max]]
}) {
  const [tile, setTile] = useState(tileType)

  // Convert bbox [lon_min, lat_min, lon_max, lat_max] → Leaflet bounds
  const leafletBounds = overlayBounds || (bbox ? [
    [bbox[1], bbox[0]],
    [bbox[3], bbox[2]],
  ] : null)

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={center}
        zoom={zoom}
        className="w-full h-full"
        zoomControl={true}
      >
        {/* Base tile */}
        <TileLayer
          key={tile}
          url={TILE_LAYERS[tile].url}
          attribution={TILE_LAYERS[tile].attribution}
          maxZoom={TILE_LAYERS[tile].maxZoom}
        />

        {/* AOI rectangle drawing */}
        {drawMode && <AOIDrawer onBboxChange={onBboxChange} enabled={drawMode} />}

        {/* Fly to */}
        {flyTo && <MapFlyTo center={flyTo.center} zoom={flyTo.zoom} />}

        {/* Before image overlay */}
        {beforeUrl && leafletBounds && activeLayer === 'before' && (
          <ImageOverlay
            url={beforeUrl}
            bounds={leafletBounds}
            opacity={1}
            zIndex={10}
          />
        )}

        {/* After image overlay */}
        {afterUrl && leafletBounds && activeLayer === 'after' && (
          <ImageOverlay
            url={afterUrl}
            bounds={leafletBounds}
            opacity={1}
            zIndex={10}
          />
        )}

        {/* Change mask overlay */}
        {changeMaskUrl && leafletBounds && activeLayer === 'change' && (
          <>
            {afterUrl && (
              <ImageOverlay url={afterUrl} bounds={leafletBounds} opacity={1} zIndex={10} />
            )}
            <ImageOverlay
              url={changeMaskUrl}
              bounds={leafletBounds}
              opacity={0.85}
              zIndex={11}
            />
          </>
        )}

        {/* GeoJSON change polygons (always visible when results exist) */}
        {changeGeojson && changeGeojson.features?.length > 0 && (
          <GeoJSON
            key={JSON.stringify(changeGeojson)}
            data={changeGeojson}
            style={changeStyle}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>

      {/* Tile switcher */}
      <div className="absolute top-3 right-3 z-[1000] flex gap-1">
        {Object.keys(TILE_LAYERS).map(t => (
          <button
            key={t}
            onClick={() => setTile(t)}
            className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
              tile === t
                ? 'bg-primary text-white'
                : 'bg-card text-slate-400 hover:text-slate-200 border border-border'
            }`}
          >
            {t === 'satellite' ? '🛰 Satellite' : '🗺 Map'}
          </button>
        ))}
      </div>

      {/* Draw mode hint */}
      {drawMode && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-[1000]
                        bg-slate-900/90 text-orange-400 text-xs px-3 py-1.5 rounded-full
                        border border-orange-500/40 pointer-events-none">
          Click and drag to draw your Area of Interest
        </div>
      )}
    </div>
  )
}
