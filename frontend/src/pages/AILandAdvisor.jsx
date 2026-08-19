import { useState } from 'react'
import { getAdvisorRecommendations } from '../services/api.js'
import toast from 'react-hot-toast'

export default function AILandAdvisor() {
    const [stats, setStats] = useState({
        changed_area_ha: 0,
        change_percent: 0,
        num_clusters: 0,
        mean_confidence: 0,
        land_type_guess: "mixed"
    })
    
    const [recommendations, setRecommendations] = useState(null)
    const [loading, setLoading] = useState(false)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        try {
            const data = await getAdvisorRecommendations(stats)
            setRecommendations(data)
        } catch (err) {
            toast.error("Failed to fetch recommendations")
        }
        setLoading(false)
    }

    const handleChange = (e) => {
        const { name, value } = e.target
        setStats(prev => ({
            ...prev,
            [name]: name === 'land_type_guess' ? value : Number(value)
        }))
    }

    return (
        <div className="h-full overflow-y-auto bg-dark p-6">
            <div className="max-w-3xl mx-auto flex flex-col gap-6">
                <div>
                    <h1 className="text-2xl font-semibold text-slate-100 mb-1">AI Land Advisor</h1>
                    <p className="text-sm text-slate-400">
                        Input change statistics to receive objective, rule-based environmental and urban planning recommendations.
                    </p>
                </div>

                <div className="card">
                    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="section-title block mb-1">Changed Area (ha)</label>
                                <input type="number" step="0.1" name="changed_area_ha" value={stats.changed_area_ha} onChange={handleChange} className="input-field" required />
                            </div>
                            <div>
                                <label className="section-title block mb-1">Change Percentage (%)</label>
                                <input type="number" step="0.1" name="change_percent" value={stats.change_percent} onChange={handleChange} className="input-field" required />
                            </div>
                            <div>
                                <label className="section-title block mb-1">Number of Clusters</label>
                                <input type="number" name="num_clusters" value={stats.num_clusters} onChange={handleChange} className="input-field" required />
                            </div>
                            <div>
                                <label className="section-title block mb-1">Mean Confidence (0-1)</label>
                                <input type="number" step="0.01" name="mean_confidence" value={stats.mean_confidence} onChange={handleChange} className="input-field" required />
                            </div>
                        </div>
                        <button type="submit" disabled={loading} className="btn-primary w-full py-2.5">
                            {loading ? 'Analyzing...' : 'Get Recommendations'}
                        </button>
                    </form>
                </div>

                {recommendations && (
                    <div className="card border border-primary/40 fade-in-up">
                        <h2 className="section-title text-primary-l mb-2">Analysis Summary</h2>
                        <p className="text-sm text-slate-300 mb-4">{recommendations.summary}</p>
                        
                        <h2 className="section-title text-accent mb-2">Recommendations</h2>
                        <ul className="list-disc list-inside text-sm text-slate-300 flex flex-col gap-2">
                            {recommendations.recommendations.map((r, i) => (
                                <li key={i}>{r}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    )
}
