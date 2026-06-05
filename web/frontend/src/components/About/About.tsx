import { useNavigate } from 'react-router-dom'

const TESTS = [
  { name: "Welch's t-test", when: '2 groups, continuous outcome (default between-subjects)' },
  { name: "Student's t-test", when: '2 groups, continuous outcome, equal variances (explicit override only)' },
  { name: 'Paired t-test', when: '2 conditions, within-subjects, continuous outcome, normal differences' },
  { name: 'Mann–Whitney U', when: '2 groups, continuous outcome, non-normal distribution' },
  { name: 'Wilcoxon signed-rank', when: '2 conditions, within-subjects, non-normal differences' },
  { name: 'One-way ANOVA', when: '3+ groups, continuous outcome, normal distributions' },
  { name: 'Kruskal–Wallis + Dunn', when: '3+ groups, continuous outcome, non-normal' },
  { name: 'Chi-squared', when: 'Two categorical variables (R×C table or 2×2 with expected counts ≥ 5)' },
  { name: "Fisher's exact", when: '2×2 categorical table with small expected counts' },
  { name: 'McNemar', when: 'Paired binary outcome' },
  { name: 'Pearson correlation', when: '2 continuous variables, linear relationship, both normal' },
  { name: 'Spearman correlation', when: '2 continuous variables, monotone relationship' },
  { name: 'MaxBET', when: '2 continuous variables, nonlinear or complex dependence expected' },
]

export default function About() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-slate-100 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <button onClick={() => navigate('/')} className="font-semibold text-lg text-brand">HTA</button>
        <button onClick={() => navigate('/analyse')} className="px-4 py-2 bg-brand text-white rounded-lg text-sm font-medium hover:bg-brand-dark transition-colors">
          Start analysis
        </button>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold text-slate-900 mb-4">About HTA</h1>
        <p className="text-xl text-slate-500 mb-12 leading-relaxed">
          The Hypothesis Testing Agent is an AI-powered statistical reasoning system that acts
          as a rigorous methodological collaborator for researchers.
        </p>

        <section className="mb-12">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">How it works</h2>
          <div className="space-y-4 text-slate-600 leading-relaxed">
            <p>HTA reasons about your <strong>study design and causal structure first</strong>, before
            selecting or executing any statistical test. This prevents the most common
            misapplications — running a t-test on non-normal data, or ignoring confounders in
            an observational study.</p>
            <p>The test selection decision tree is entirely deterministic — no LLM inference is
            involved in choosing the test. Statisticians can read, audit, and revise it as plain
            Python logic. The LLM (GPT-5.4 via Azure OpenAI) is used only for the study design
            dialogue and to generate the plain-language summary and methods text.</p>
            <p>Effect sizes are computed with 95% confidence intervals. Assumption checks are run
            before the main test and flagged clearly. Sensitivity power analysis (minimum
            detectable effect at the observed N) is reported instead of post-hoc observed power.</p>
          </div>
        </section>

        <section className="mb-12">
          <h2 className="text-2xl font-bold text-slate-900 mb-6">Supported tests</h2>
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Test</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Selected when</th>
                </tr>
              </thead>
              <tbody>
                {TESTS.map((t, i) => (
                  <tr key={i} className={`border-t border-slate-100 ${i % 2 === 0 ? '' : 'bg-slate-50'}`}>
                    <td className="px-4 py-3 font-medium text-slate-800">{t.name}</td>
                    <td className="px-4 py-3 text-slate-600">{t.when}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-12">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">Limitations (v0.1.0)</h2>
          <ul className="space-y-2 text-slate-600 list-disc list-inside leading-relaxed">
            <li>Designed for continuous, binary, and categorical outcomes. Survival, count, and
              compositional outcomes are not yet supported.</li>
            <li>MaxBET (nonlinear independence testing) requires R and the BET package to be
              installed on the server.</li>
            <li>Linear regression and logistic regression are planned for v0.2.0.</li>
            <li>No multiple-outcome correction is applied automatically; a caveat is flagged.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-bold text-slate-900 mb-4">References</h2>
          <ul className="space-y-2 text-slate-600 text-sm">
            <li>Zhang, K. (2019). BET on Independence. <em>Journal of the American Statistical Association</em>, 114(528), 1620–1637.</li>
            <li>Xiang, S., Zhang, W., Liu, S., Hoadley, K. A., Perou, C. M., Zhang, K., &amp; Marron, J. S. (2023). Pairwise Nonlinear Dependence Analysis of Genomic Data. <em>The Annals of Applied Statistics</em>, 17(4). DOI: 10.1214/23-AOAS1745.</li>
            <li>Vallat, R. (2018). Pingouin: statistics in Python. <em>Journal of Open Source Software</em>, 3(31), 1026.</li>
            <li>Virtanen, P. et al. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. <em>Nature Methods</em>, 17, 261–272.</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
