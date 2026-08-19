import { NavLink } from 'react-router-dom'

const NAV_LINKS = [
  { to: '/analysis',   label: 'Change Analysis' },
  { to: '/explorer',   label: 'Change Explorer' },
  { to: '/monitoring', label: 'Area Monitoring' },
  { to: '/advisor',    label: 'AI Land Advisor' },
]

export default function NavBar() {
  return (
    <header className="bg-card border-b border-border flex items-center px-5 h-14 shrink-0 z-50">
      {/* Logo */}
      <NavLink to="/analysis" className="flex items-center gap-2 mr-8 select-none">
        <span className="text-xl">🌍</span>
        <span className="font-bold text-lg tracking-tight text-slate-100">
          Terra<span className="text-primary-l">Delta</span>
        </span>
        <span className="hidden sm:inline text-xs text-slate-500 ml-1 font-normal">
          Satellite Change Detection
        </span>
      </NavLink>

      {/* Navigation */}
      <nav className="flex gap-1">
        {NAV_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Right side */}
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden md:flex items-center gap-1.5 text-xs text-slate-500">
          <span className="w-1.5 h-1.5 rounded-full bg-primary-l animate-pulse"></span>
          Sentinel-2 L2A
        </span>
        <a
          href="https://dataspace.copernicus.eu"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors hidden lg:block"
        >
          Powered by ESA Copernicus
        </a>
      </div>
    </header>
  )
}
