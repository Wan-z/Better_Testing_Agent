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

const TRUNCATE_LEN = 80

export default function StepVariables({ columns, inferredTypes, preview, onNext }: Props) {
  // Multi-variable selection state
  const [selectedVars, setSelectedVars] = useState<string[]>([])
  const [primaryVar, setPrimaryVar] = useState<string>('')

  // Group and hypothesis
  const [group, setGroup] = useState('__none__')
  const [hypothesis, setHypothesis] = useState('')
  const [loading, setLoading] = useState(false)

  // Preview row count selector
  const [previewRows, setPreviewRows] = useState(5)

  // Cell truncation state: Set of "rowIdx-colName" keys
  const [expandedCells, setExpandedCells] = useState<Set<string>>(new Set())

  const toggleCell = (key: string) =>
    setExpandedCells(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })

  const toggleVar = (col: string) => {
    if (selectedVars.includes(col)) {
      const next = selectedVars.filter(v => v !== col)
      setSelectedVars(next)
      if (col === primaryVar) setPrimaryVar(next[0] ?? '')
    } else {
      setSelectedVars(prev => [...prev, col])
      if (!primaryVar) setPrimaryVar(col)
    }
  }

  const valid = selectedVars.length > 0 && primaryVar !== '' && hypothesis.trim().length > 0

  const handleNext = async () => {
    if (!valid) return
    setLoading(true)
    const predictor = selectedVars.find(v => v !== primaryVar)
    await onNext({
      outcome_variable: primaryVar,
      predictor_variable: predictor,
      group_variable: group === '__none__' ? undefined : group,
      hypothesis: hypothesis.trim(),
      selected_variables: selectedVars,
    })
    setLoading(false)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Set your variables</h2>
      <p className="text-slate-500 mb-8">Select the variables to analyse and describe your research question.</p>

      {/* ── Data preview ─────────────────────────────────────────────────── */}
      <div className="mb-8 bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between gap-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Data preview
            <span className="ml-2 font-normal normal-case text-slate-400">
              showing {Math.min(previewRows, preview.length)} of {preview.length} loaded rows
            </span>
          </p>
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span>Show:</span>
            {[5, 10, 20, 50].map(n => {
              const unavailable = n > preview.length
              return (
                <button
                  key={n}
                  onClick={() => !unavailable && setPreviewRows(n)}
                  disabled={unavailable}
                  title={unavailable ? `Only ${preview.length} rows available` : undefined}
                  className={`px-2 py-0.5 rounded transition-colors ${
                    previewRows === n && !unavailable
                      ? 'bg-brand text-white font-medium'
                      : unavailable
                        ? 'bg-slate-100 text-slate-300 cursor-not-allowed'
                        : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                  }`}
                >
                  {n}
                </button>
              )
            })}
          </div>
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
              {preview.slice(0, previewRows).map((row, i) => (
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                  {columns.map(col => {
                    const raw = String(row[col] ?? '')
                    const key = `${i}-${col}`
                    const isLong = raw.length > TRUNCATE_LEN
                    const expanded = expandedCells.has(key)
                    return (
                      <td key={col} className="px-4 py-2 text-slate-600 font-mono text-xs align-top">
                        {isLong && !expanded ? (
                          <>
                            {raw.slice(0, TRUNCATE_LEN)}…{' '}
                            <button
                              onClick={() => toggleCell(key)}
                              className="text-brand hover:underline text-[10px] font-sans whitespace-nowrap"
                            >
                              show more
                            </button>
                          </>
                        ) : isLong && expanded ? (
                          <>
                            {raw}{' '}
                            <button
                              onClick={() => toggleCell(key)}
                              className="text-brand hover:underline text-[10px] font-sans whitespace-nowrap"
                            >
                              show less
                            </button>
                          </>
                        ) : (
                          raw
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Variables of interest (multi-select) ─────────────────────────── */}
      <div className="mb-5">
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Variables of interest <span className="text-red-500">*</span>
        </label>
        <p className="text-xs text-slate-400 mb-2">
          Check one or more columns. The first you select (marked <span className="font-semibold text-brand">Y</span>) is the primary variable.
          Selecting a second pins it as the explicit predictor; selecting more lets HTA pick the strongest.
        </p>
        <div className="grid sm:grid-cols-2 gap-1.5 max-h-56 overflow-y-auto pr-1">
          {columns.map(col => {
            const isSelected = selectedVars.includes(col)
            const isPrimary = col === primaryVar
            return (
              <div
                key={col}
                onClick={() => toggleVar(col)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer select-none transition-colors ${
                  isSelected
                    ? 'bg-indigo-50 border-indigo-300'
                    : 'bg-white border-slate-200 hover:border-indigo-200'
                }`}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  readOnly
                  className="accent-brand shrink-0"
                />
                <span className="text-sm font-medium text-slate-700 flex-1 min-w-0 truncate">{col}</span>
                {isPrimary && isSelected && (
                  <span
                    title="Primary (Y) variable"
                    className="shrink-0 px-1.5 py-0.5 bg-brand text-white rounded text-[10px] font-bold"
                  >
                    Y
                  </span>
                )}
                {isSelected && !isPrimary && (
                  <button
                    title="Set as primary (Y) variable"
                    onClick={e => { e.stopPropagation(); setPrimaryVar(col) }}
                    className="shrink-0 px-1.5 py-0.5 border border-brand text-brand rounded text-[10px] hover:bg-indigo-50"
                  >
                    set Y
                  </button>
                )}
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${TYPE_COLOURS[inferredTypes[col] ?? 'CONTINUOUS']}`}>
                  {inferredTypes[col]}
                </span>
              </div>
            )
          })}
        </div>

        {/* Selection summary */}
        {selectedVars.length > 0 && (
          <p className="mt-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">Primary (Y):</span> {primaryVar}
            {selectedVars.length >= 2 && (
              <>
                {' · '}
                <span className="font-medium text-slate-700">
                  {selectedVars.length === 2 ? 'Explicit predictor:' : 'Additional variables:'}
                </span>{' '}
                {selectedVars.filter(v => v !== primaryVar).join(', ')}
              </>
            )}
          </p>
        )}
      </div>

      {/* ── Group variable ────────────────────────────────────────────────── */}
      <div className="mb-2">
        <label className="block text-sm font-medium text-slate-700 mb-1.5">
          Group variable
          <span className="ml-1 text-xs font-normal text-slate-400">(categorical only — for group comparisons)</span>
        </label>
        <select
          value={group}
          onChange={e => setGroup(e.target.value)}
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand"
        >
          <option value="__none__">None — run a correlation / regression</option>
          {columns.filter(c => !selectedVars.includes(c)).map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Group-variable validation warnings */}
      {group !== '__none__' && inferredTypes[group] === 'CONTINUOUS' && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <strong>Heads up:</strong> <em>{group}</em> is <strong>CONTINUOUS</strong> — using it as a group
          creates one group per unique value (potentially thousands of groups). Set Group to "None" to
          run a correlation/regression instead.
        </div>
      )}
      {group !== '__none__' && inferredTypes[group] === 'COUNT' && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <strong>Heads up:</strong> <em>{group}</em> is <strong>COUNT</strong>. If it has many unique values
          this will produce one group per unique count. Consider "None" unless it's a small discrete count
          (e.g., 0–5 levels).
        </div>
      )}

      <div className="mb-6" />

      {/* ── Research hypothesis ───────────────────────────────────────────── */}
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
