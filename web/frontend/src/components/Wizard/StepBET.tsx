import { useState } from 'react'
import { ArrowRight, SkipForward, Network } from 'lucide-react'
import type { BetScreenResponse, EdaSummary, PlotSpec, VariableType } from '../../types/api'
import { runBetScreen } from '../../api/client'
import PlotViewer from '../Results/PlotViewer'

interface Props {
  columns: string[]
  inferredTypes: Record<string, VariableType>
  sessionId: string
  onNext: () => void
}

const NUMERIC_TYPES: VariableType[] = ['CONTINUOUS', 'ORDINAL', 'COUNT']

const TYPE_COLOURS: Record<string, string> = {
  CONTINUOUS:    'bg-blue-100 text-blue-700',
  ORDINAL:       'bg-teal-100 text-teal-700',
  COUNT:         'bg-amber-100 text-amber-700',
  CATEGORICAL:   'bg-purple-100 text-purple-700',
  BINARY:        'bg-orange-100 text-orange-700',
  TIME_TO_EVENT: 'bg-rose-100 text-rose-700',
  DATETIME:      'bg-sky-100 text-sky-700',
  GEOSPATIAL:    'bg-emerald-100 text-emerald-700',
  IDENTIFIER:    'bg-slate-100 text-slate-600',
}

interface BetResult {
  eda_plots: PlotSpec[]
  eda_summary: EdaSummary | null
}

export default function StepBET({ columns, inferredTypes, sessionId, onNext }: Props) {
  const numericCols = columns.filter(c => NUMERIC_TYPES.includes(inferredTypes[c]))
  const [selected, setSelected] = useState<Set<string>>(new Set(numericCols))
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BetResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const toggle = (col: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(col)) next.delete(col)
      else next.add(col)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(numericCols))
  const clearAll  = () => setSelected(new Set())

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const selectedList = [...selected]
      // Pass null (= all numeric) when everything is selected — avoids
      // sending a long column list when it's the same as the default.
      const cols = selectedList.length === numericCols.length ? null : selectedList
      const res: BetScreenResponse = await runBetScreen(sessionId, cols)
      setResult({ eda_plots: res.eda_plots, eda_summary: res.eda_summary })
    } catch (e) {
      setError(String(e))
    }
    setLoading(false)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Explore nonlinear dependencies</h2>
      <p className="text-slate-500 mb-6">
        BET screens selected numeric columns for pairwise nonlinear dependence — including
        patterns invisible to Pearson/Spearman correlation. This is purely exploratory and
        does not affect which statistical test is chosen.
      </p>

      {/* Column selector */}
      {!result && (
        <>
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-slate-700">
                Columns to screen
                <span className="ml-2 text-slate-400 font-normal">
                  ({selected.size} of {numericCols.length} numeric selected)
                </span>
              </p>
              <div className="flex gap-2 text-xs">
                <button onClick={selectAll} className="text-brand hover:underline">All</button>
                <span className="text-slate-300">|</span>
                <button onClick={clearAll} className="text-slate-500 hover:underline">None</button>
              </div>
            </div>

            {numericCols.length === 0 ? (
              <p className="text-sm text-slate-500 italic">
                No numeric columns detected — BET requires at least 2 continuous, ordinal,
                or count variables.
              </p>
            ) : (
              <div className="grid sm:grid-cols-2 gap-2">
                {columns.map(col => {
                  const isNumeric = NUMERIC_TYPES.includes(inferredTypes[col])
                  const checked = selected.has(col)
                  return (
                    <label
                      key={col}
                      className={`flex items-center gap-3 p-2.5 rounded-lg border transition-colors
                        ${!isNumeric
                          ? 'opacity-40 cursor-not-allowed bg-slate-50 border-slate-100'
                          : checked
                            ? 'bg-indigo-50 border-indigo-200 cursor-pointer'
                            : 'bg-white border-slate-200 hover:border-indigo-200 cursor-pointer'
                        }`}
                    >
                      <input
                        type="checkbox"
                        checked={isNumeric && checked}
                        disabled={!isNumeric}
                        onChange={() => isNumeric && toggle(col)}
                        className="accent-brand"
                      />
                      <span className="text-sm font-medium text-slate-700 flex-1 min-w-0 truncate">
                        {col}
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${TYPE_COLOURS[inferredTypes[col]] ?? 'bg-slate-100 text-slate-600'}`}>
                        {inferredTypes[col]}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex flex-wrap gap-3 items-center">
            <button
              onClick={handleRun}
              disabled={loading || selected.size < 2}
              className="flex items-center gap-2 px-6 py-3 bg-brand text-white rounded-xl font-medium hover:bg-brand-dark transition-colors disabled:opacity-40"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Running BET screen…
                </>
              ) : (
                <><Network size={16} /> Run BET screen</>
              )}
            </button>
            <button
              onClick={onNext}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-3 bg-white text-slate-600 border border-slate-200 rounded-xl font-medium hover:bg-slate-50 transition-colors disabled:opacity-40"
            >
              <SkipForward size={16} /> Skip
            </button>
            {selected.size < 2 && !loading && numericCols.length >= 2 && (
              <p className="text-xs text-amber-600">Select at least 2 columns to run.</p>
            )}
          </div>
        </>
      )}

      {/* Results */}
      {result && (
        <>
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <h3 className="text-sm font-semibold text-slate-700">BET results</h3>
              {(result.eda_summary?.n_nonlinear_only ?? 0) > 0 && (
                <span className="px-2 py-0.5 bg-indigo-100 text-brand rounded-full text-[11px] font-medium">
                  {result.eda_summary!.n_nonlinear_only} invisible to correlation
                </span>
              )}
              {result.eda_summary?.subtype_suggestive && (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full text-[11px] font-medium">
                  possible latent subgroups
                </span>
              )}
            </div>

            {result.eda_summary ? (
              <>
                <p className="text-sm text-slate-600 mb-4">{result.eda_summary.text}</p>
                {result.eda_plots.length > 0 && <PlotViewer plots={result.eda_plots} />}
                <p className="text-xs text-slate-400 mt-3 leading-relaxed">
                  {(result.eda_summary.n_network_edges ?? 0) > 0 && (
                    <>
                      The first tab is a <strong>dependence network</strong>: each variable is
                      a node and every edge is a significant nonlinear relationship, coloured by
                      its binary-interaction type.{' '}
                    </>
                  )}
                  The pair tabs show each top pair on the empirical-copula (rank) unit square,
                  with points coloured by the dominant <strong>binary interaction</strong>. A
                  cluster of one colour reveals a latent subgroup (heterogeneity).
                  {result.eda_summary.label_colored_by
                    ? ` The last tab colours the top pair by "${result.eda_summary.label_colored_by}".`
                    : ''}
                </p>
              </>
            ) : (
              <p className="text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-lg">
                No significant nonlinear dependencies found among the selected columns.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={onNext}
              className="flex items-center gap-2 px-6 py-3 bg-brand text-white rounded-xl font-medium hover:bg-brand-dark transition-colors"
            >
              Continue — Set variables <ArrowRight size={16} />
            </button>
            <button
              onClick={() => setResult(null)}
              className="px-6 py-3 bg-white text-slate-600 border border-slate-200 rounded-xl font-medium hover:bg-slate-50 transition-colors"
            >
              Re-run with different columns
            </button>
          </div>
        </>
      )}
    </div>
  )
}
