// Mock API layer — returns realistic fake data for every endpoint.
// Swap USE_MOCK=false when the real backend is ready.

import type {
  UploadResponse,
  VariablesPayload,
  StudyDesign,
  Report,
} from '../types/api'

const delay = (ms: number) => new Promise(r => setTimeout(r, ms))

// ── Shared mock data ──────────────────────────────────────────────────────────

const MOCK_REPORT: Report = {
  data_profile: {
    variables: [
      {
        name: 'blood_pressure',
        variable_type: 'CONTINUOUS',
        n_observations: 100,
        n_missing: 2,
        distribution_stats: {
          mean: 128.4, std: 14.2, median: 127.0, iqr: 18.5,
          skewness: 0.31, kurtosis: -0.12, min: 95.0, max: 172.0,
        },
        normality: { name: 'Shapiro-Wilk', statistic: 0.982, p_value: 0.21, is_normal: true },
      },
      {
        name: 'group',
        variable_type: 'CATEGORICAL',
        n_observations: 100,
        n_missing: 0,
        unique_values: ['control', 'treatment'],
      },
    ],
    n_groups: 2,
    group_variable: 'group',
    outcome_variable: 'blood_pressure',
    notes: ['2 missing values in blood_pressure (2.0%)'],
  },
  study_design: {
    design_type: 'EXPERIMENTAL',
    measurement_type: 'BETWEEN_SUBJECTS',
    is_randomized: true,
    confounders: [
      {
        name: 'age',
        role: 'CONFOUNDER',
        is_measured: true,
        adjustment_recommended: true,
        rationale: 'Age affects both treatment assignment and blood pressure.',
      },
    ],
    notes: ['Randomised controlled trial'],
  },
  test_result: {
    test_used: 'WELCH_T',
    statistic: 3.14,
    p_value: 0.002,
    degrees_of_freedom: 97.3,
    effect_size: {
      measure_name: "Cohen's d",
      value: 0.63,
      interpretation: 'medium',
      ci_lower: 0.22,
      ci_upper: 1.04,
    },
    assumption_checks: [
      {
        assumption_name: 'Normality (outcome)',
        status: 'MET',
        test_used: 'Shapiro-Wilk',
        statistic: 0.982,
        p_value: 0.21,
        note: 'Distribution does not significantly deviate from normality.',
      },
      {
        assumption_name: 'Minimum sample size',
        status: 'MET',
        note: 'Both groups have N ≥ 5.',
      },
      {
        assumption_name: 'Independence of observations',
        status: 'UNTESTABLE',
        note: 'Assumed based on study design (between-subjects RCT).',
      },
    ],
    confidence_interval: [2.8, 12.4],
    is_significant: true,
    notes: [
      "Sensitivity: minimum detectable Cohen's d = 0.28 at N=100, α=0.05, power=0.80",
    ],
  },
  plain_language_summary:
    'Participants in the treatment group had significantly lower blood pressure than those in ' +
    'the control group (p = 0.002). The effect was medium in size (Cohen\'s d = 0.63, 95% CI ' +
    '[0.22, 1.04]), suggesting a clinically meaningful reduction.',
  caveats: [
    {
      severity: 'WARNING',
      message: 'Marginal result: consider replication.',
      recommendation: 'The p-value (0.002) is robust, but the confidence interval is wide. ' +
        'Replicate with a larger sample to narrow the effect size estimate.',
    },
    {
      severity: 'INFO',
      message: 'Age was identified as a confounder but not adjusted for in this analysis.',
      recommendation: 'Consider ANCOVA with age as a covariate to improve precision.',
    },
  ],
  plots: [
    {
      plot_type: 'boxplot',
      title: 'Blood pressure by group',
      x_label: 'Group',
      y_label: 'Blood pressure (mmHg)',
      plotly_json: {
        data: [
          {
            type: 'box',
            name: 'Control',
            y: [120, 125, 130, 132, 118, 140, 135, 128, 122, 138,
                115, 142, 127, 133, 119, 136, 124, 131, 126, 141],
            marker: { color: '#94a3b8' },
          },
          {
            type: 'box',
            name: 'Treatment',
            y: [108, 112, 105, 118, 102, 115, 110, 107, 114, 109,
                103, 116, 111, 106, 113, 108, 104, 117, 110, 112],
            marker: { color: '#4f46e5' },
          },
        ],
        layout: {
          title: '',
          yaxis: { title: 'Blood pressure (mmHg)' },
          xaxis: { title: 'Group' },
          showlegend: true,
          plot_bgcolor: '#f8fafc',
          paper_bgcolor: '#ffffff',
        },
      },
    },
    {
      plot_type: 'qqplot',
      title: 'Q-Q plot — blood pressure (control)',
      x_label: 'Theoretical quantiles',
      y_label: 'Sample quantiles',
      plotly_json: {
        data: [
          {
            type: 'scatter',
            mode: 'markers',
            name: 'Observed',
            x: [-2.1, -1.5, -1.1, -0.8, -0.5, -0.3, 0, 0.3, 0.5, 0.8, 1.1, 1.5, 2.1],
            y: [115, 118, 120, 122, 124, 126, 128, 130, 132, 135, 138, 140, 142],
            marker: { color: '#4f46e5' },
          },
          {
            type: 'scatter',
            mode: 'lines',
            name: 'Normal',
            x: [-2.5, 2.5],
            y: [115, 142],
            line: { color: '#ef4444', dash: 'dash' },
          },
        ],
        layout: {
          title: '',
          xaxis: { title: 'Theoretical quantiles' },
          yaxis: { title: 'Sample quantiles' },
          showlegend: true,
          plot_bgcolor: '#f8fafc',
          paper_bgcolor: '#ffffff',
        },
      },
    },
  ],
  methods_text:
    'An independent-samples Welch\'s t-test was used to compare blood pressure between ' +
    'treatment and control groups, as this test does not assume equal variances. Normality ' +
    'was assessed using the Shapiro-Wilk test (W = 0.982, p = .21) and confirmed for both ' +
    'groups. The effect size was estimated as Cohen\'s d with 95% confidence intervals ' +
    'computed via bootstrapping (n = 1,000 resamples). Statistical significance was ' +
    'evaluated at α = .05.',
}

// ── Mock API functions ────────────────────────────────────────────────────────

let _sessionId = ''

export async function mockUpload(_file: File): Promise<UploadResponse> {
  await delay(800)
  _sessionId = crypto.randomUUID()
  return {
    session_id: _sessionId,
    status: 'PROFILED',
    columns: ['group', 'blood_pressure', 'age'],
    inferred_types: {
      group: 'CATEGORICAL',
      blood_pressure: 'CONTINUOUS',
      age: 'CONTINUOUS',
    },
    preview: [
      { group: 'control', blood_pressure: 128, age: 45 },
      { group: 'treatment', blood_pressure: 112, age: 52 },
      { group: 'control', blood_pressure: 135, age: 38 },
      { group: 'treatment', blood_pressure: 108, age: 61 },
      { group: 'control', blood_pressure: 122, age: 44 },
    ],
  }
}

export async function mockSetVariables(
  _sessionId: string,
  _payload: VariablesPayload,
): Promise<void> {
  await delay(300)
}

// Simulates a 3-turn dialogue with streamed tokens via an async generator
export async function* mockDialogueTurn(
  _sessionId: string,
  _userMessage: string,
  turnIndex: number,
): AsyncGenerator<{ type: string; content?: string; is_complete?: boolean; study_design?: StudyDesign }> {
  await delay(400)

  const responses = [
    'Thank you. A few quick questions to understand your study design:\n\n' +
      '1. Was this an experimental study (with random assignment to treatment/control) ' +
      'or an observational study?\n' +
      '2. Are the measurements independent between participants (i.e., no repeated measures ' +
      'or matched pairs)?\n' +
      '3. Are there any variables you think might confound the relationship between treatment ' +
      'and blood pressure (for example, age, sex, or baseline health status)?',

    'Understood — a randomised controlled trial with between-subjects measurements. ' +
      'You\'ve mentioned age as a potential confounder, which is a reasonable concern.\n\n' +
      'One final question: do you expect the relationship between treatment and blood ' +
      'pressure to be straightforward (linear), or do you suspect a more complex pattern?',
  ]

  const text = turnIndex < responses.length ? responses[turnIndex] : responses[1]
  const isLastTurn = turnIndex >= 1

  // Stream tokens word-by-word
  const words = text.split(' ')
  for (const word of words) {
    yield { type: 'token', content: word + ' ' }
    await delay(30)
  }

  if (isLastTurn) {
    yield {
      type: 'done',
      is_complete: true,
      study_design: MOCK_REPORT.study_design,
    }
  } else {
    yield { type: 'done', is_complete: false }
  }
}

export async function* mockRunAnalysis(
  _sessionId: string,
): AsyncGenerator<{ type: string; stage?: string; message?: string; report?: Report }> {
  const stages = [
    { stage: 'selecting_test', message: 'Selecting statistical test…' },
    { stage: 'executing_test', message: 'Running Welch\'s t-test…' },
    { stage: 'generating_report', message: 'Generating report…' },
  ]

  for (const s of stages) {
    await delay(700)
    yield { type: 'progress', ...s }
  }

  await delay(400)
  yield { type: 'result', report: MOCK_REPORT }
}
