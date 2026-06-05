import { useState } from 'react'
import PlotImport from 'react-plotly.js'
import type { PlotSpec } from '../../types/api'

// react-plotly.js is published as CommonJS with no ESM `exports` map, so under Vite's
// dependency optimizer the default import can come back wrapped (the module/namespace
// object) instead of the component itself. Rendering that object makes React throw
// "Element type is invalid" and blanks the whole page. Unwrap nested `.default` until we
// reach the real component (a class/function, or a forwardRef/memo object via $$typeof).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function resolveComponent(mod: any): any {
  let c = mod
  while (c && typeof c === 'object' && !('$$typeof' in c) && 'default' in c) c = c.default
  return c
}
const Plot = resolveComponent(PlotImport) as typeof PlotImport

interface Props { plots: PlotSpec[] }

export default function PlotViewer({ plots }: Props) {
  const [active, setActive] = useState(0)
  const plot = plots[active] ?? plots[0]
  if (!plot || !plot.plotly_json) return null

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Plots</p>
      <div className="flex gap-2 mb-4">
        {plots.map((p, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              active === i ? 'bg-brand text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {p.title}
          </button>
        ))}
      </div>
      <Plot
        data={plot.plotly_json.data as Plotly.Data[]}
        layout={{
          ...(plot.plotly_json.layout as Partial<Plotly.Layout>),
          autosize: true,
          margin: { t: 20, r: 20, b: 50, l: 55 },
          height: 340,
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
      />
    </div>
  )
}
