export default function LoadingOverlay({ progress = 0, message = 'Processing...' }) {
  return (
    <div className="flex flex-col gap-3 py-4 px-1 fade-in-up">
      {/* Progress bar */}
      <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full progress-shimmer rounded-full transition-all duration-500"
          style={{ width: `${Math.max(4, progress)}%` }}
        />
      </div>

      {/* Percent + message */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">{message}</span>
        <span className="text-primary-l font-mono font-medium">{progress}%</span>
      </div>

      {/* Stage indicators */}
      <div className="grid grid-cols-4 gap-1 mt-1">
        {[
          { label: 'Imagery',    threshold: 20  },
          { label: 'Features',   threshold: 50  },
          { label: 'AI Model',   threshold: 75  },
          { label: 'Results',    threshold: 95  },
        ].map(({ label, threshold }) => (
          <div key={label} className="flex flex-col items-center gap-1">
            <div className={`w-full h-1 rounded-full transition-colors duration-700 ${
              progress >= threshold ? 'bg-primary-l' : 'bg-slate-700'
            }`} />
            <span className={`text-[10px] ${
              progress >= threshold ? 'text-primary-l' : 'text-slate-600'
            }`}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
