import { PlayCircle } from 'lucide-react'
import type { DataProfile, StudyDesign, VariablesPayload } from '../../types/api'

interface Props {
  profile: DataProfile | null
  variables: VariablesPayload
  studyDesign: StudyDesign
  onRun: () => Promise<void>
}

export default function StepReview({ profile, variables, studyDesign, onRun }: Props) {
  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Review & run</h2>
      <p className="text-slate-500 mb-8">Confirm your setup before running the analysis.</p>

      <div className="space-y-4 mb-8">
        {/* Data summary */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Data</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-slate-500 text-xs">Outcome</p>
              <p className="font-medium text-slate-800">{variables.outcome_variable}</p>
            </div>
            {variables.group_variable && (
              <div>
                <p className="text-slate-500 text-xs">Group variable</p>
                <p className="font-medium text-slate-800">{variables.group_variable}</p>
              </div>
            )}
            {profile && (
              <div>
                <p className="text-slate-500 text-xs">Observations</p>
                <p className="font-medium text-slate-800">{profile.variables[0]?.n_observations ?? '—'}</p>
              </div>
            )}
          </div>
          {profile?.notes && profile.notes.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100">
              {profile.notes.map((n, i) => (
                <p key={i} className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded mt-1">⚠ {n}</p>
              ))}
            </div>
          )}
        </div>

        {/* Hypothesis */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Hypothesis</h3>
          <p className="text-slate-700 text-sm italic">"{variables.hypothesis}"</p>
        </div>

        {/* Study design */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Study design</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-slate-500 text-xs">Design type</p>
              <p className="font-medium text-slate-800">{studyDesign.design_type.replace('_', ' ')}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">Measurement</p>
              <p className="font-medium text-slate-800">{studyDesign.measurement_type.replace('_', ' ')}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">Randomised</p>
              <p className="font-medium text-slate-800">{studyDesign.is_randomized ? 'Yes' : 'No'}</p>
            </div>
          </div>
          {studyDesign.confounders.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100">
              <p className="text-xs text-slate-500">Confounders: {studyDesign.confounders.map(c => c.name).join(', ')}</p>
            </div>
          )}
        </div>

        {/* Planned test */}
        <div className="bg-indigo-50 rounded-xl border border-indigo-200 p-5">
          <h3 className="text-sm font-semibold text-brand mb-1">Planned test</h3>
          <p className="text-lg font-bold text-slate-900">Welch's t-test</p>
          <p className="text-sm text-slate-600 mt-1">
            Between-subjects comparison of a continuous outcome across 2 groups. Welch's variant
            is used as the default — it does not assume equal variances.
          </p>
        </div>
      </div>

      <button
        onClick={onRun}
        className="flex items-center gap-2 px-8 py-3.5 bg-brand text-white rounded-xl font-semibold hover:bg-brand-dark transition-colors shadow-lg shadow-indigo-200"
      >
        <PlayCircle size={20} /> Run analysis
      </button>
    </div>
  )
}
