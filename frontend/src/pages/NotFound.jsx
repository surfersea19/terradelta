import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <div className="text-6xl mb-4">🛰️</div>
        <h1 className="text-2xl font-bold text-slate-100 mb-2">404 — Signal Lost</h1>
        <p className="text-slate-400 mb-6">This orbital path doesn't exist.</p>
        <Link to="/analysis" className="btn-primary px-6 py-2.5">
          Return to Base
        </Link>
      </div>
    </div>
  )
}
