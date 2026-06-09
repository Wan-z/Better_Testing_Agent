import { PlayCircle, ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { DataProfile, StudyDesign, VariablesPayload } from '../../types/api'
import PlotViewer from '../Results/PlotViewer'
import { previewTest } from '../../api/client'

const TEST_LABELS: Record<string, string> = {
  WELCH_T: "Welch's t-test", INDEPENDENT_T: "Student's t-test",
  PAIRED_T: 'Paired t-test', MANN_WHITNEY_U: 'Mann–Whitney U',
  WILCOXON_SIGNED_RANK: 'Wilcoxon signed-rank', ONE_WAY_ANOVA: 'One-way ANOVA',
  KRUSKAL_WALLIS: 'Kruskal–Wallis', CHI_SQUARED: 'Chi-squared',
  FISHER_EXACT: "Fisher's exact", MCNEMAR: 'McNemar',
  PEARSON_CORRELATION: 'Pearson correlation', SPEARMAN_CORRELATION: 'Spearman correlation',
  MAXBET: 'MaxBET (nonlinear independence)', WELCH_ANOVA: "Welch's ANOVA",
  POISSON_REGRESSION: 'Poisson regression', NEGATIVE_BINOMIAL_REGRESSION: 'Negative binomial regression',
  LOG_RANK: 'Log-rank test', COX_REGRESSION: 'Cox proportional hazards', ROC_AUC: 'ROC / AUC',
}

interface Props {
  sessionId: string | null
  profile: DataProfile | null
  variables: VariablesPayload
  studyDesign: StudyDesign
  onRun: () => Promise<void>
  onBack: () => void
}

export default function StepReview({ sessionId, profile, variables, studyDesign, onRun, onBack }: Props) {
  const [plannedTest, setPlannedTest] = useState<{
    test_name: string; rationale: string; caveats: string[]
  } | null>(null)

  useEffect(() => {
    if (!sessionId) return
    previewTest(sessionId)
      .then(setPlannedTest)
      .catch(() => { /* non-fatal — card just stays hidden */ })
  }, [sessionId])
  const eda = profile?.eda_summary ?? null
  const edaPlots = profile?.eda_plots ?? []
  const hasEda = !!eda && edaPlots.length > 0

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Review & run</h2>
      <p className="text-slate-500 mb-8">
        Here is what an exploratory BET screen found in your data. Review it, then choose how to proceed.
      </p>

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

        {/* ── Exploratory analysis: nonlinear relationships (BET) ──────────── */}
        {hasEda && (
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <h3 className="text-sm font-semibold text-slate-700">
                Exploratory analysis — nonlinear relationships (BET)
              </h3>
              {eda!.n_nonlinear_only > 0 && (
                <span className="px-2 py-0.5 bg-indigo-100 text-brand rounded-full text-[11px] font-medium">
                  {eda!.n_nonlinear_only} invisible to correlation
                </span>
              )}
              {eda!.subtype_suggestive && (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full text-[11px] font-medium">
                  possible latent subgroups
                </span>
              )}
            </div>
            <p className="text-sm text-slate-600 mb-3">{eda!.text}</p>

            <PlotViewer plots={edaPlots} />

            <p className="text-xs text-slate-400 mt-3 leading-relaxed">
              {(eda!.n_network_edges ?? 0) > 0 && (
                <>
                  The first tab is a <strong>dependence network</strong> (as in Xiang et al.): each
                  variable is a node and every edge is a significant nonlinear relationship, coloured by
                  its binary-interaction type.{' '}
                </>
              )}
              The pair tabs show each top pair on the empirical-copula (rank) unit square, with points
              coloured by the dominant <strong>binary interaction</strong> — the shaded checkerboard is
              that interaction's ± region on the BET grid — so a cluster of one colour reveals a latent
              subgroup (heterogeneity).
              {eda!.label_colored_by
                ? ` The last tab instead colours the top pair by the known label "${eda!.label_colored_by}".`
                : ''}
            </p>
          </div>
        )}

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
        {plannedTest && plannedTest.test_name !== '—' && (
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Planned test</h3>
            <p className="font-semibold text-slate-900 mb-1">
              {TEST_LABELS[plannedTest.test_name] ?? plannedTest.test_name}
            </p>
            <p className="text-sm text-slate-600">{plannedTest.rationale}</p>
            {plannedTest.caveats.length > 0 && (
              <div className="mt-2 space-y-1">
                {plannedTest.caveats.map((c, i) => (
                  <p key={i} className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded">⚠ {c}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Next steps: present the EDA result and ask how to proceed ──────── */}
      <div className="bg-indigo-50 rounded-xl border border-indigo-200 p-5">
        <h3 className="text-sm font-semibold text-brand mb-1">How would you like to proceed?</h3>
        <p className="text-sm text-slate-600 mb-4">
          {hasEda && eda!.n_significant > 0
            ? 'BET surfaced the nonlinear structure above. Run the planned test now, or go back to refocus the analysis — e.g. choose a flagged pair, or add the subgroup variable that explains the heterogeneity.'
            : 'HTA will pick the appropriate test from your data types, study design, and normality checks. Run it now, or go back to adjust your variable choices.'}
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={onRun}
            className="flex items-center gap-2 px-8 py-3.5 bg-brand text-white rounded-xl font-semibold hover:bg-brand-dark transition-colors shadow-lg shadow-indigo-200"
          >
            <PlayCircle size={20} /> Run analysis
          </button>
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-6 py-3.5 bg-white text-slate-700 border border-slate-200 rounded-xl font-medium hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft size={18} /> Adjust variables
          </button>
        </div>
      </div>
    </div>
  )
}
