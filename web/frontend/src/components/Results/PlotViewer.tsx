import { useState } from 'react'
import Plot from 'react-plotly.js'
import type { PlotSpec } from '../../types/api'

interface Props { plots: PlotSpec[] }

export default function PlotViewer({ plots }: Props) {
  const [active, setActive] = useState(0)
  const plot = plots[active]

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
