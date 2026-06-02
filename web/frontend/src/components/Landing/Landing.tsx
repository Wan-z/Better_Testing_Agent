import { useNavigate } from 'react-router-dom'
import { Upload, MessageSquare, BarChart2, ArrowRight, CheckCircle } from 'lucide-react'

const STEPS = [
  { icon: Upload,        label: 'Upload your data',      desc: 'Drop a CSV file — HTA infers variable types automatically.' },
  { icon: MessageSquare, label: 'Describe your question', desc: 'A short guided conversation captures your study design and any confounders.' },
  { icon: BarChart2,     label: 'Get your results',       desc: 'The right test is selected, executed, and explained — with a ready-to-paste methods paragraph.' },
]

const TESTS = [
  "Welch's t-test", "Mann–Whitney U", "Paired t-test", "Wilcoxon signed-rank",
  "One-way ANOVA", "Kruskal–Wallis", "Chi-squared", "Fisher's exact",
  "Pearson correlation", "Spearman correlation", "MaxBET (nonlinear)", "McNemar",
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="border-b border-slate-100 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <span className="font-semibold text-lg text-brand">HTA</span>
        <div className="flex items-center gap-6 text-sm text-slate-600">
          <a href="/about" className="hover:text-slate-900">About</a>
          <button
            onClick={() => navigate('/analyse')}
            className="px-4 py-2 bg-brand text-white rounded-lg text-sm font-medium hover:bg-brand-dark transition-colors"
          >
            Start analysis
          </button>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-indigo-50 text-brand px-3 py-1 rounded-full text-sm font-medium mb-6">
          <CheckCircle size={14} />
          AI-powered statistical reasoning
        </div>
        <h1 className="text-5xl font-bold text-slate-900 leading-tight mb-6">
          Upload your data.<br />
          Get the <span className="text-brand">right test</span>, every time.
        </h1>
        <p className="text-xl text-slate-500 max-w-2xl mx-auto mb-10">
          HTA reasons about your study design and causal structure before selecting
          a statistical test — then checks every assumption and writes your methods section.
        </p>
        <button
          onClick={() => navigate('/analyse')}
          className="inline-flex items-center gap-2 px-8 py-4 bg-brand text-white rounded-xl text-lg font-semibold hover:bg-brand-dark transition-colors shadow-lg shadow-indigo-200"
        >
          Start analysis <ArrowRight size={20} />
        </button>
        <p className="mt-4 text-sm text-slate-400">No login required · Data stored 7 days · Free</p>
      </section>

      {/* How it works */}
      <section className="bg-slate-50 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-slate-900 text-center mb-4">How it works</h2>
          <p className="text-slate-500 text-center mb-14 max-w-xl mx-auto">
            Three steps from raw data to a publication-ready result.
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {STEPS.map((s, i) => (
              <div key={i} className="bg-white rounded-2xl p-8 shadow-sm border border-slate-100">
                <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center mb-5">
                  <s.icon size={22} className="text-brand" />
                </div>
                <div className="text-xs font-semibold text-brand uppercase tracking-wide mb-2">Step {i + 1}</div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">{s.label}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Supported tests */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-slate-900 text-center mb-4">Supported tests</h2>
        <p className="text-slate-500 text-center mb-10 max-w-xl mx-auto">
          HTA selects from 12 tests based on your data, design, and assumptions —
          including BET for detecting nonlinear dependence.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          {TESTS.map(t => (
            <span key={t} className="px-4 py-2 bg-slate-100 text-slate-700 rounded-full text-sm font-medium">
              {t}
            </span>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-100 py-8 text-center text-sm text-slate-400">
        HTA · Hypothesis Testing Agent · Built with FastAPI + React
      </footer>
    </div>
  )
}
