import { Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/shared/NavBar.jsx'
import ChangeAnalysis from './pages/ChangeAnalysis.jsx'
import ChangeExplorer from './pages/ChangeExplorer.jsx'
import AreaMonitoring from './pages/AreaMonitoring.jsx'
import NotFound from './pages/NotFound.jsx'

export default function App() {
  return (
    <div className="flex flex-col h-full">
      <NavBar />
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/analysis" replace />} />
          <Route path="/analysis"   element={<ChangeAnalysis />} />
          <Route path="/explorer"   element={<ChangeExplorer />} />
          <Route path="/monitoring" element={<AreaMonitoring />} />
          <Route path="*"           element={<NotFound />} />
        </Routes>
      </main>
    </div>
  )
}
