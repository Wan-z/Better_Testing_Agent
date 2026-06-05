// TypeScript types mirroring the Pydantic models and API response schemas.

export type VariableType =
  | 'CONTINUOUS'
  | 'ORDINAL'
  | 'CATEGORICAL'
  | 'BINARY'
  | 'COUNT'
  | 'TIME_TO_EVENT'
  | 'DATETIME'
  | 'GEOSPATIAL'
  | 'IDENTIFIER'

export type SessionStatus =
  | 'CREATED'
  | 'PROFILED'
  | 'DESIGNED'
  | 'READY'
  | 'RUNNING'
  | 'COMPLETE'
  | 'FAILED'

export type AssumptionStatus = 'MET' | 'VIOLATED' | 'UNTESTABLE' | 'MARGINAL'
export type CaveatSeverity = 'INFO' | 'WARNING' | 'CRITICAL'
export type StudyDesignType = 'EXPERIMENTAL' | 'OBSERVATIONAL' | 'QUASI_EXPERIMENTAL'
export type MeasurementType = 'BETWEEN_SUBJECTS' | 'WITHIN_SUBJECTS' | 'MIXED'

// ── Data profile ─────────────────────────────────────────────────────────────

export interface DistributionStats {
  mean: number
  std: number
  median: number
  iqr: number
  skewness: number
  kurtosis: number
  min: number
  max: number
}

export interface NormalityTest {
  name: string
  statistic: number
  p_value: number | null
  is_normal: boolean
}

export interface Variable {
  name: string
  variable_type: VariableType
  n_observations: number
  n_missing: number
  distribution_stats?: DistributionStats
  normality?: NormalityTest
  unique_values?: string[]
}

export interface DataProfile {
  variables: Variable[]
  n_groups?: number
  group_variable?: string
  outcome_variable?: string
  notes: string[]
}

// ── Study design ──────────────────────────────────────────────────────────────

export interface Confounder {
  name: string
  role: string
  is_measured: boolean
  adjustment_recommended: boolean
  rationale: string
}

export interface StudyDesign {
  design_type: StudyDesignType
  measurement_type: MeasurementType
  is_randomized: boolean
  confounders: Confounder[]
  notes: string[]
}

// ── Test result ───────────────────────────────────────────────────────────────

export interface AssumptionCheck {
  assumption_name: string
  status: AssumptionStatus
  test_used?: string
  statistic?: number
  p_value?: number
  note: string
}

export interface EffectSize {
  measure_name: string
  value: number
  interpretation: string
  ci_lower: number
  ci_upper: number
}

export interface TestResult {
  test_used: string
  statistic: number
  p_value: number
  degrees_of_freedom?: number
  effect_size: EffectSize
  assumption_checks: AssumptionCheck[]
  confidence_interval: [number, number]
  is_significant: boolean
  power?: number
  notes: string[]
}

// ── Report ────────────────────────────────────────────────────────────────────

export interface Caveat {
  severity: CaveatSeverity
  message: string
  recommendation: string
}

export interface PlotSpec {
  plot_type: string
  // plotly_json is added by the backend export layer
  plotly_json: PlotlySpec
  title: string
  x_label: string
  y_label: string
}

export interface PlotlySpec {
  data: object[]
  layout: object
}

export interface Report {
  data_profile: DataProfile
  study_design: StudyDesign
  test_result: TestResult
  plain_language_summary: string
  caveats: Caveat[]
  plots: PlotSpec[]
  methods_text: string
}

// ── API response shapes ───────────────────────────────────────────────────────

export interface UploadResponse {
  session_id: string
  status: SessionStatus
  columns: string[]
  inferred_types: Record<string, VariableType>
  preview: Record<string, unknown>[]
}

export interface SessionResponse {
  session_id: string
  status: SessionStatus
  profile?: DataProfile
  design?: StudyDesign
  report?: Report
}

export interface VariablesPayload {
  outcome_variable: string
  group_variable?: string
  hypothesis: string
}

export interface DialogueMessage {
  role: 'user' | 'assistant'
  content: string
}

// SSE event types
export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'done'; is_complete: boolean; study_design?: StudyDesign }
  | { type: 'progress'; stage: string; message: string }
  | { type: 'result'; report: Report }
  | { type: 'error'; error: string; message: string }
