import type { Report } from '../../types/api'
import ResultsView from '../Results'
import { RotateCcw } from 'lucide-react'

interface Props {
  report: Report | null
  sessionId: string | null
  progressMessage: string
  onReset: () => void
}

const STAGES = ['selecting_test', 'executing_test', 'generating_report']
const STAGE_LABELS = ['Selecting test', 'Running test', 'Generating report']

export default function StepResults({ report, sessionId, progressMessage, onReset }: Props) {
  if (!report) {
    const stageIdx = STAGES.findIndex(s => progressMessage.toLowerCase().includes(s.replace('_', '')))
    const active = stageIdx >= 0 ? stageIdx : 0

    return (
      <div className="max-w-md mx-auto text-center py-20">
        <div className="w-16 h-16 border-4 border-brand border-t-transparent rounded-full animate-spin mx-auto mb-8" />
        <p className="text-lg font-semibold text-slate-800 mb-6">{progressMessage || 'Running analysis…'}</p>
        <div className="space-y-2">
          {STAGE_LABELS.map((label, i) => (
            <div key={i} className={`flex items-center gap-3 text-sm px-4 py-2 rounded-lg ${
              i < active ? 'text-green-700 bg-green-50' :
              i === active ? 'text-brand bg-indigo-50 font-medium' :
              'text-slate-400'
            }`}>
              <span>{i < active ? '✓' : i === active ? '→' : '○'}</span>
              {label}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Results</h2>
          <p className="text-slate-500 text-sm mt-1">Analysis complete</p>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
        >
          <RotateCcw size={14} /> New analysis
        </button>
      </div>
      <ResultsView report={report} sessionId={sessionId ?? ''} />
    </div>
  )
}
