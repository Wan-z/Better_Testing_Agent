import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import type { VariableType, VariablesPayload } from '../../types/api'

interface Props {
  columns: string[]
  inferredTypes: Record<string, VariableType>
  preview: Record<string, unknown>[]
  onNext: (payload: VariablesPayload) => Promise<void>
}

const EXAMPLES = [
  'Counties with more OUD treatment clinics have lower nonfatal overdose ED visit rates',
  'Treatment group has lower blood pressure than control',
  'Association between clinic density and overdose ED rate',
]

const TYPE_COLOURS: Record<VariableType, string> = {
  CONTINUOUS:    'bg-blue-100 text-blue-700',
  CATEGORICAL:   'bg-purple-100 text-purple-700',
  BINARY:        'bg-orange-100 text-orange-700',
  ORDINAL:       'bg-teal-100 text-teal-700',
  COUNT:         'bg-amber-100 text-amber-700',
  TIME_TO_EVENT: 'bg-rose-100 text-rose-700',
  DATETIME:      'bg-sky-100 text-sky-700',
  GEOSPATIAL:    'bg-emerald-100 text-emerald-700',
  IDENTIFIER:    'bg-slate-100 text-slate-600',
}

export default function StepVariables({ columns, inferredTypes, preview, onNext }: Props) {
  const [outcome, setOutcome] = useState('')
  const [group, setGroup] = useState('__none__')
  const [hypothesis, setHypothesis] = useState('')
  const [loading, setLoading] = useState(false)

  const valid = outcome !== '' && hypothesis.trim().length > 0

  const handleNext = async () => {
    if (!valid) return
    setLoading(true)
    await onNext({
      outcome_variable: outcome,
      group_variable: group === '__none__' ? undefined : group,
      hypothesis: hypothesis.trim(),
    })
    setLoading(false)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Set your variables</h2>
      <p className="text-slate-500 mb-8">Tell HTA which column is your outcome and describe your research question.</p>

      {/* Data preview */}
      <div className="mb-8 bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Data preview (first 5 rows)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                {columns.map(col => (
                  <th key={col} className="text-left px-4 py-2 font-medium text-slate-700">
                    <div>{col}</div>
                    <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${TYPE_COLOURS[inferredTypes[col] ?? 'CONTINUOUS']}`}>
                      {inferredTypes[col] ?? 'CONTINUOUS'}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                  {columns.map(col => (
                    <td key={col} className="px-4 py-2 text-slate-600 font-mono text-xs">
                      {String(row[col] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Variable pickers */}
      <div className="grid sm:grid-cols-2 gap-5 mb-2">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">
            Outcome variable <span className="text-red-500">*</span>
          </label>
          <select
            value={outcome}
            onChange={e => setOutcome(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand"
          >
            <option value="">Select column…</option>
            {columns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">
            Group variable
            <span className="ml-1 text-xs font-normal text-slate-400">(categorical only)</span>
          </label>
          <select
            value={group}
            onChange={e => setGroup(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand"
          >
            <option value="__none__">None — run a correlation / regression</option>
            {columns.filter(c => c !== outcome).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* Group-variable validation warning */}
      {group !== '__none__' && inferredTypes[group] === 'CONTINUOUS' && (
        <div className="mb-5 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <strong>Heads up:</strong> <em>{group}</em> is detected as <strong>CONTINUOUS</strong>.
          Using a continuous variable as the group creates one group per unique value (potentially
          thousands), which is almost never what you want. To test the <em>association</em> between
          this variable and your outcome, leave Group as "None" — HTA will automatically run a
          correlation or regression instead.
        </div>
      )}
      {group !== '__none__' && inferredTypes[group] === 'COUNT' && (
        <div className="mb-5 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <strong>Heads up:</strong> <em>{group}</em> is detected as <strong>COUNT</strong>.
          If it takes many unique values (e.g. a raw count column) you will get one group per
          unique count. Consider leaving Group as "None" to run a correlation/regression,
          unless this is a small discrete count (0–5 levels).
        </div>
      )}

      <div className="mb-6" />

      {/* Hypothesis */}
      <div className="mb-3">
        <label className="block text-sm font-medium text-slate-700 mb-1.5">
          Research hypothesis <span className="text-red-500">*</span>
        </label>
        <textarea
          value={hypothesis}
          onChange={e => setHypothesis(e.target.value)}
          rows={3}
          placeholder="Describe your hypothesis in plain language…"
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand resize-none"
        />
      </div>
      <div className="flex flex-wrap gap-2 mb-8">
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            onClick={() => setHypothesis(ex)}
            className="px-3 py-1 text-xs bg-indigo-50 text-brand rounded-full hover:bg-indigo-100 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      <button
        onClick={handleNext}
        disabled={!valid || loading}
        className="flex items-center gap-2 px-6 py-3 bg-brand text-white rounded-xl font-medium hover:bg-brand-dark transition-colors disabled:opacity-40"
      >
        {loading ? 'Saving…' : 'Next — Study design'} <ArrowRight size={16} />
      </button>
    </div>
  )
}
