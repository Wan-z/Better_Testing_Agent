import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ArrowRight, X, Plus, Send, CheckCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type {
  StudyDesign, StudyDesignType, MeasurementType, Confounder,
  DialogueMessage, EdaSummary, VariablesPayload,
} from '../../types/api'
import { previewTest } from '../../api/client'

interface Props {
  sessionId: string | null
  messages: DialogueMessage[]
  studyDesign: StudyDesign | null
  edaSummary?: EdaSummary | null
  variables?: VariablesPayload | null
  columns?: string[]
  onSend: (msg: string) => Promise<{ tokens: number; isComplete: boolean }>
  onConfirm: (design: StudyDesign) => void | Promise<void>
}

const DESIGN_TYPE_OPTIONS: [StudyDesignType, string][] = [
  ['EXPERIMENTAL', 'Experimental'],
  ['OBSERVATIONAL', 'Observational'],
  ['QUASI_EXPERIMENTAL', 'Quasi-experimental'],
]

const MEASUREMENT_OPTIONS: [MeasurementType, string][] = [
  ['BETWEEN_SUBJECTS', 'Independent (between subjects)'],
  ['WITHIN_SUBJECTS', 'Repeated / paired (within subjects)'],
  ['MIXED', 'Mixed / clustered'],
]

// The '__init__' prefix marks the dialogue opener: useSession hides it from the
// visible chat and strips the prefix before sending, so only the framing + BET
// context below is stored as the first user turn.
function buildInitMessage(eda?: EdaSummary | null, vars?: VariablesPayload | null): string {
  const lines = ['__init__', 'I have uploaded my dataset and selected my variables.']
  if (vars) {
    lines.push(`My primary outcome variable is: ${vars.outcome_variable}.`)
    if (vars.predictor_variable) lines.push(`My predictor variable is: ${vars.predictor_variable}.`)
    if (vars.hypothesis) lines.push(`My research hypothesis is: ${vars.hypothesis}.`)
    lines.push('Do not ask me which variables I am studying — I have already specified them above.')
  }
  lines.push('Please interview me about the study design.')
  if (eda) {
    lines.push('', `Context from the automated BET dependence screen: ${eda.text}`)
    if (eda.top_pairs.length > 0) {
      lines.push('Top dependent pairs: ' + eda.top_pairs.map(p =>
        `${p.x} × ${p.y} (${p.form.toLowerCase()}, z = ${p.bet_z.toFixed(1)}${p.significant ? '' : ', n.s.'})`,
      ).join('; ') + '.')
    }
    lines.push(`Pairs with significant dependence: ${eda.n_significant}.`)
    if (eda.subtype_suggestive) {
      lines.push(
        'The screen flagged mixture-type shapes that often arise from a latent subgroup — '
        + 'please ask me whether a subgroup or subtype could drive the pattern, and use the '
        + 'detected forms to pre-fill the expected relationship form.',
      )
    }
  }
  return lines.join('\n')
}

// ── Quick-reply options — shown below the last assistant bubble ────────────────
// Each group maps a pattern in the assistant's text to the relevant answer choices.
// ALL matching groups are returned so multi-question messages show options for each.

interface OptionGroup { label: string; options: string[] }

const QUICK_REPLY_GROUPS: Array<OptionGroup & { pattern: RegExp }> = [
  {
    label: 'Study type',
    pattern: /type of study|how.+conduct|experimental|observational|quasi/i,
    options: ['Experimental', 'Observational', 'Quasi-experimental'],
  },
  {
    label: 'Randomization',
    pattern: /randomiz|randomly.?assign/i,
    options: ['Yes, randomized', 'No, not randomized', "Don't know"],
  },
  {
    label: 'Measurement structure',
    pattern: /independent.*across|independence.*obs|same participant|independent obs|within.?subject|between.?subject|repeated.?measure|measured.*multiple|multiple.*time|longitudinal|temporal.*autocorrelation|autocorrelation|spatial.*correlation|panel.*data/i,
    options: ['Independent (each row is a unique unit)', 'Repeated measures / panel data (same unit over time)', 'Mixed / clustered'],
  },
  {
    label: 'Relationship form',
    pattern: /relationship.+form|form of.+relationship|what.*form.*relationship|linear.*monotone|linear.*nonlinear|monotone.*nonlinear/i,
    options: ['Linear', 'Monotone (nonlinear)', 'Nonlinear / complex', "Don't know"],
  },
  {
    label: 'Latent subgroups',
    pattern: /latent.?subgroup|hidden.?subtype|subgroup.?structure|subtype.*drive|suspect.*subgroup|subgroup.*suspect|fall into/i,
    options: ['Yes, likely subgroups present', 'Possibly', 'No / unlikely', "Don't know"],
  },
  {
    label: 'Confounders',
    pattern: /confounder|confounding|control.?variable|covariate/i,
    options: ['No known confounders', 'Age', 'Sex / gender', 'Socioeconomic status', "Don't know"],
  },
]

function detectQuickReplies(text: string, extraGroups: OptionGroup[] = []): OptionGroup[] {
  const base = QUICK_REPLY_GROUPS
    .filter(g => g.pattern.test(text))
    .map(({ label, options }) => ({ label, options }))
  // Append any dynamic groups (e.g. variable pairs) that also match
  const extras = extraGroups.filter(() =>
    /variable pair|main focus|primary research|outcome.*predictor|predictor.*outcome|which.*variable|research question/i.test(text)
  )
  return [...base, ...extras]
}

// ── Chat pieces ────────────────────────────────────────────────────────────────

function ChatBubble({ role, content }: DialogueMessage) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
        isUser ? 'bg-brand text-white rounded-br-md whitespace-pre-wrap' : 'bg-slate-100 text-slate-800 rounded-bl-md'
      }`}>
        {isUser ? content : (
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
              em:     ({ children }) => <em className="italic">{children}</em>,
              ol:     ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
              ul:     ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
              li:     ({ children }) => <li>{children}</li>,
              hr:     () => <hr className="border-slate-300 my-2" />,
              code:   ({ children }) => <code className="bg-slate-200 rounded px-1 text-xs font-mono">{children}</code>,
            }}
          >
            {content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-slate-100 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1">
        {[0, 150, 300].map(delay => (
          <span
            key={delay}
            className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  )
}

// ── Editable design summary (right panel) ──────────────────────────────────────

function ChipEditor({ items, onAdd, onRemove, placeholder, suggestions }: {
  items: string[]
  onAdd: (value: string) => void
  onRemove: (value: string) => void
  placeholder: string
  suggestions?: string[]
}) {
  const [value, setValue] = useState('')
  const listId = useId()
  const available = suggestions?.filter(s => !items.includes(s)) ?? []

  const add = (v = value) => {
    const trimmed = v.trim()
    if (trimmed) onAdd(trimmed)
    setValue('')
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    if (available.includes(v)) {
      // User picked from datalist — add immediately
      onAdd(v)
      setValue('')
    } else {
      setValue(v)
    }
  }

  return (
    <div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {items.map(item => (
            <span key={item} className="flex items-center gap-1 px-2.5 py-1 bg-indigo-50 text-brand text-xs font-medium rounded-full border border-indigo-200">
              {item}
              <button onClick={() => onRemove(item)} className="hover:text-indigo-800">
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      {available.length > 0 && (
        <datalist id={listId}>
          {available.map(s => <option key={s} value={s} />)}
        </datalist>
      )}
      <div className="flex gap-1.5">
        <input
          value={value}
          onChange={handleChange}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={available.length > 0 ? `${placeholder} (or pick from list ▾)` : placeholder}
          list={available.length > 0 ? listId : undefined}
          className="flex-1 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand"
        />
        <button
          onClick={() => add()}
          disabled={!value.trim()}
          className="p-1.5 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-40"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      {children}
    </div>
  )
}

const SELECT_CLS = 'w-full border border-slate-200 rounded-lg px-2.5 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand'

function EditableDesignCard({ draft, onChange, onConfirm, confounderSuggestions }: {
  draft: StudyDesign
  onChange: (d: StudyDesign) => void
  onConfirm: () => void | Promise<void>
  confounderSuggestions?: string[]
}) {
  const addConfounder = (name: string) => {
    if (draft.confounders.some(c => c.name === name)) return
    const confounder: Confounder = {
      name, role: 'CONFOUNDER', is_measured: true,
      adjustment_recommended: true, rationale: 'Added by the researcher at review',
    }
    onChange({ ...draft, confounders: [...draft.confounders, confounder] })
  }

  return (
    <div className="bg-white rounded-2xl border border-indigo-200 shadow-sm p-5">
      <p className="text-xs font-semibold text-brand uppercase tracking-wide mb-1">Design captured</p>
      <p className="text-xs text-slate-400 mb-4">Check each field — correct anything the assistant misread.</p>
      <div className="space-y-4">
        <Field label="Design type">
          <select
            value={draft.design_type}
            onChange={e => onChange({ ...draft, design_type: e.target.value as StudyDesignType })}
            className={SELECT_CLS}
          >
            {DESIGN_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Measurement">
          <select
            value={draft.measurement_type}
            onChange={e => onChange({ ...draft, measurement_type: e.target.value as MeasurementType })}
            className={SELECT_CLS}
          >
            {MEASUREMENT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Randomised">
          <select
            value={draft.is_randomized ? 'yes' : 'no'}
            onChange={e => onChange({ ...draft, is_randomized: e.target.value === 'yes' })}
            className={SELECT_CLS}
          >
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </Field>
        <Field label="Confounders">
          <ChipEditor
            items={draft.confounders.map(c => c.name)}
            onAdd={addConfounder}
            onRemove={name => onChange({ ...draft, confounders: draft.confounders.filter(c => c.name !== name) })}
            placeholder="Add confounder…"
            suggestions={confounderSuggestions}
          />
        </Field>
        <Field label="Notes">
          <ChipEditor
            items={draft.notes}
            onAdd={note => { if (!draft.notes.includes(note)) onChange({ ...draft, notes: [...draft.notes, note] }) }}
            onRemove={note => onChange({ ...draft, notes: draft.notes.filter(n => n !== note) })}
            placeholder="Add note…"
          />
        </Field>
      </div>
      <button
        onClick={() => void onConfirm()}
        className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-3 bg-brand text-white rounded-xl text-sm font-semibold hover:bg-brand-dark transition-colors"
      >
        Confirm design <ArrowRight size={15} />
      </button>
    </div>
  )
}

// ── Static form fallback (kept for dry-run / no-LLM deployments) ───────────────

function OptionCard({
  label, description, selected, onClick,
}: {
  label: string
  description: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 rounded-xl border-2 transition-all ${
        selected
          ? 'border-brand bg-indigo-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <p className={`text-sm font-semibold ${selected ? 'text-brand' : 'text-slate-800'}`}>{label}</p>
      <p className="text-xs text-slate-500 mt-0.5 leading-snug">{description}</p>
    </button>
  )
}

function Question({ number, label, children, visible }: {
  number: number
  label: string
  children: React.ReactNode
  visible: boolean
}) {
  if (!visible) return null
  return (
    <div className="space-y-3 animate-[fadeIn_0.2s_ease-in]">
      <div className="flex items-center gap-2">
        <span className="w-6 h-6 rounded-full bg-brand text-white text-xs font-bold flex items-center justify-center shrink-0">
          {number}
        </span>
        <p className="text-sm font-semibold text-slate-700">{label}</p>
      </div>
      <div className="space-y-2 pl-8">{children}</div>
    </div>
  )
}

type RelationshipForm = 'linear' | 'monotone' | 'nonlinear' | 'unknown'

function DesignForm({ onConfirm }: { onConfirm: (design: StudyDesign) => void | Promise<void> }) {
  const [designType, setDesignType]         = useState<StudyDesignType | null>(null)
  const [measurementType, setMeasurementType] = useState<MeasurementType | null>(null)
  const [isRandomized, setIsRandomized]     = useState<boolean | null>(null)
  const [relationship, setRelationship]     = useState<RelationshipForm | null>(null)
  const [confounderInput, setConfounderInput] = useState('')
  const [confounders, setConfounders]       = useState<string[]>([])

  // Progressive reveal: each step unlocks the next
  const showStep2 = designType !== null
  const showStep3 = showStep2 && measurementType !== null
  const showStep4 = showStep3 && isRandomized !== null
  const showStep5 = showStep4 && relationship !== null
  const canConfirm = showStep5

  const addConfounder = () => {
    const name = confounderInput.trim()
    if (name && !confounders.includes(name)) {
      setConfounders(prev => [...prev, name])
    }
    setConfounderInput('')
  }

  const buildDesign = (): StudyDesign => {
    const confounderObjects: Confounder[] = confounders.map(name => ({
      name,
      role: 'potential_confounder',
      is_measured: false,
      adjustment_recommended: true,
      rationale: 'User-identified confounder',
    }))
    const notes: string[] = []
    if (relationship) notes.push(`Expected relationship form: ${relationship}`)
    return {
      design_type: designType!,
      measurement_type: measurementType!,
      is_randomized: isRandomized!,
      confounders: confounderObjects,
      notes,
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <div className="space-y-8">

        {/* Q1 — Study type */}
        <Question number={1} label="How was the study conducted?" visible>
          {(
            [
              ['EXPERIMENTAL',      'Experimental',       'Researchers assigned treatments or exposures to participants'],
              ['OBSERVATIONAL',     'Observational',      'Researchers observed naturally occurring variables, no assignment'],
              ['QUASI_EXPERIMENTAL','Quasi-experimental', 'Treatment-like groups, but assignment was not fully random'],
            ] as [StudyDesignType, string, string][]
          ).map(([val, label, desc]) => (
            <OptionCard key={val} label={label} description={desc}
              selected={designType === val} onClick={() => setDesignType(val)} />
          ))}
        </Question>

        {/* Q2 — Measurement structure */}
        <Question number={2} label="Are the observations independent?" visible={showStep2}>
          {(
            [
              ['BETWEEN_SUBJECTS', 'Independent',         'Each row is a different participant or unit — no pairing or clustering'],
              ['WITHIN_SUBJECTS',  'Repeated / paired',   'Same participant measured multiple times, or matched pairs'],
              ['MIXED',            'Mixed / clustered',   'Some grouping structure: nested data, split-plot, or partial pairing'],
            ] as [MeasurementType, string, string][]
          ).map(([val, label, desc]) => (
            <OptionCard key={val} label={label} description={desc}
              selected={measurementType === val} onClick={() => setMeasurementType(val)} />
          ))}
        </Question>

        {/* Q3 — Randomization */}
        <Question number={3} label="Was randomization used?" visible={showStep3}>
          {(
            [
              [true,  'Yes', 'Participants were randomly assigned to conditions'],
              [false, 'No',  'Assignment was based on availability, self-selection, or other criteria'],
            ] as [boolean, string, string][]
          ).map(([val, label, desc]) => (
            <OptionCard key={String(val)} label={label} description={desc}
              selected={isRandomized === val} onClick={() => setIsRandomized(val)} />
          ))}
        </Question>

        {/* Q4 — Relationship form */}
        <Question number={4} label="What relationship do you expect between variables?" visible={showStep4}>
          {(
            [
              ['linear',    'Linear',           'A straight-line relationship — equal change in Y per unit X'],
              ['monotone',  'Monotone',          'Consistently increasing or decreasing, but not necessarily straight'],
              ['nonlinear', 'Nonlinear / complex','U-shaped, threshold effects, or other non-monotone patterns'],
              ['unknown',   'Unknown',           "Not sure — let HTA decide based on the data"],
            ] as [RelationshipForm, string, string][]
          ).map(([val, label, desc]) => (
            <OptionCard key={val} label={label} description={desc}
              selected={relationship === val} onClick={() => setRelationship(val)} />
          ))}
        </Question>

        {/* Q5 — Confounders */}
        <Question number={5} label="Any known confounders to note? (optional)" visible={showStep5}>
          <p className="text-xs text-slate-400 -mt-1 mb-2">
            e.g. age, sex, baseline severity, site — type one at a time and press Enter or +
          </p>
          <div className="flex gap-2">
            <input
              value={confounderInput}
              onChange={e => setConfounderInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addConfounder() } }}
              placeholder="Confounder name…"
              className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <button
              onClick={addConfounder}
              disabled={!confounderInput.trim()}
              className="p-2.5 bg-slate-100 text-slate-600 rounded-xl hover:bg-slate-200 transition-colors disabled:opacity-40"
            >
              <Plus size={16} />
            </button>
          </div>
          {confounders.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {confounders.map(c => (
                <span key={c} className="flex items-center gap-1 px-3 py-1 bg-indigo-50 text-brand text-xs font-medium rounded-full border border-indigo-200">
                  {c}
                  <button onClick={() => setConfounders(prev => prev.filter(x => x !== c))} className="hover:text-indigo-800">
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </Question>

        {/* Confirm */}
        {canConfirm && (
          <button
            onClick={() => onConfirm(buildDesign())}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-brand text-white rounded-xl text-sm font-semibold hover:bg-brand-dark transition-colors animate-[fadeIn_0.2s_ease-in]"
          >
            Confirm design <ArrowRight size={15} />
          </button>
        )}

      </div>
    </div>
  )
}

// ── Main component — LLM chat with form fallback ───────────────────────────────

export default function StepDialogue({ sessionId, messages, studyDesign, edaSummary, variables, columns, onSend, onConfirm }: Props) {
  const [mode, setMode] = useState<'chat' | 'form'>('chat')
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [draft, setDraft] = useState<StudyDesign | null>(null)
  // Tracks which option the user has selected per group label (not yet sent).
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({})
  const initRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const designCardRef = useRef<HTMLDivElement>(null)

  // The design captured by the dialogue (done event → hook state), with any local
  // edits from the right panel overlaid.
  const design = draft ?? studyDesign

  // Keep the newest message / streaming token in view.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, sending])

  const runSend = async (msg: string, isInitCall = false) => {
    setSelectedOptions({})
    setSending(true)
    setStreamError(null)
    try {
      const result = await onSend(msg)
      if (isInitCall && result.isComplete && result.tokens === 0) {
        // Completed instantly with no conversation — a dry-run stub, not a real LLM.
        setMode('form')
      } else if (result.tokens === 0 && !result.isComplete) {
        setStreamError('The assistant did not respond — the LLM may be unreachable. Retry by sending a message, or use the form instead.')
      }
    } catch (e) {
      setStreamError(String(e))
    } finally {
      setSending(false)
    }
  }

  // On mount: probe for dry-run mode (the dialogue endpoint would stream a canned demo
  // conversation — show the form instead), and open the dialogue with a hidden
  // __init__ message carrying the BET EDA context.
  useEffect(() => {
    if (initRef.current) return
    initRef.current = true
    if (sessionId) {
      previewTest(sessionId)
        .then(p => { if (p.rationale.startsWith('Dry-run mode')) setMode('form') })
        .catch(() => { /* best-effort probe — stay in chat mode */ })
    }
    if (messages.length === 0 && !studyDesign) {
      // Deferred to a microtask so no state update runs synchronously in the effect.
      const init = buildInitMessage(edaSummary, variables)
      queueMicrotask(() => { void runSend(init, true) })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || sending) return
    setInput('')
    void runSend(msg)
  }

  const handleOptionClick = (groupLabel: string, opt: string) => {
    if (sending || captured) return
    const next = { ...selectedOptions, [groupLabel]: opt }
    setSelectedOptions(next)
    setInput(Object.values(next).join('; '))
  }

  const captured = design !== null

  // Scroll the design card into view the first time the design is captured
  // (important on mobile where it's below the chat, not beside it).
  const prevCapturedRef = useRef(false)
  useEffect(() => {
    if (captured && !prevCapturedRef.current) {
      prevCapturedRef.current = true
      setTimeout(() => {
        designCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }, 300)
    }
  }, [captured])

  const awaitingAssistant = sending
    && (messages.length === 0 || messages[messages.length - 1]?.role === 'user')

  const lastAssistantMsg = useMemo(
    () => [...messages].reverse().find(m => m.role === 'assistant')?.content ?? '',
    [messages],
  )

  const quickReplies = useMemo(() => {
    if (captured || sending) return []

    // Find the index of the last assistant message so we only scan history before it.
    let lastIdx = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') { lastIdx = i; break }
    }

    // Group labels whose pattern already appeared in an earlier assistant turn.
    const seenLabels = new Set<string>()
    for (let i = 0; i < lastIdx; i++) {
      const msg = messages[i]
      if (msg.role !== 'assistant') continue
      for (const g of QUICK_REPLY_GROUPS) {
        if (g.pattern.test(msg.content)) seenLabels.add(g.label)
      }
    }

    return detectQuickReplies(lastAssistantMsg)
      .filter(g => !seenLabels.has(g.label))
  }, [lastAssistantMsg, captured, sending, messages])

  const confounderSuggestions = useMemo(() => {
    const exclude = new Set([
      variables?.outcome_variable,
      variables?.predictor_variable,
    ].filter(Boolean) as string[])
    return (columns ?? []).filter(c => !exclude.has(c))
  }, [columns, variables])

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-1">Study design</h2>
          <p className="text-slate-500 text-sm">
            {mode === 'chat'
              ? 'Describe your study to the assistant — it captures the design, and you can correct any field before confirming.'
              : 'Answer a few questions so HTA can select the right statistical test.'}
          </p>
        </div>
        <button
          onClick={() => setMode(m => (m === 'chat' ? 'form' : 'chat'))}
          className="shrink-0 px-3 py-1.5 text-xs font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
        >
          {mode === 'chat' ? 'Use form instead' : 'Use chat instead'}
        </button>
      </div>

      {mode === 'form' ? (
        <DesignForm onConfirm={onConfirm} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">

          {/* LEFT (60%) — chat history + input */}
          <div className="lg:col-span-3 bg-white border border-slate-200 rounded-2xl shadow-sm flex flex-col h-[34rem]">
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((m, i) => (
                <ChatBubble key={i} role={m.role} content={m.content} />
              ))}
              {awaitingAssistant && <TypingIndicator />}
              {!captured && !sending && quickReplies.length > 0 && (
                <div className="space-y-3 pt-1">
                  {quickReplies.map(group => (
                    <div key={group.label}>
                      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                        {group.label}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {group.options.map(opt => {
                          const isSelected = selectedOptions[group.label] === opt
                          return (
                            <button
                              key={opt}
                              onClick={() => handleOptionClick(group.label, opt)}
                              className={`px-3 py-1.5 text-xs rounded-lg transition-colors font-medium shadow-sm border ${
                                isSelected
                                  ? 'bg-brand text-white border-brand'
                                  : 'bg-white border-indigo-200 text-brand hover:bg-indigo-50 active:bg-indigo-100'
                              }`}
                            >
                              {opt}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                  <p className="text-[10px] text-slate-400">
                    Select answers above, then press <span className="font-semibold">Send</span> — or type your own reply below.
                  </p>
                </div>
              )}
              {captured && (
                <div className="flex items-start gap-2.5 p-3 bg-green-50 border border-green-200 rounded-xl text-sm text-green-800 animate-[fadeIn_0.3s_ease-out]">
                  <CheckCircle size={16} className="text-green-600 shrink-0 mt-0.5" />
                  <span>
                    Design captured — review and confirm the summary{' '}
                    <span className="lg:inline hidden">on the right</span>
                    <span className="lg:hidden">below</span>.
                  </span>
                </div>
              )}
              {streamError && (
                <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {streamError}
                </div>
              )}
            </div>
            <div className="border-t border-slate-100 p-3 flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend() } }}
                placeholder={captured ? 'Design captured — review it on the right' : 'Type your reply…'}
                disabled={sending || captured}
                className="flex-1 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand disabled:bg-slate-50 disabled:text-slate-400"
              />
              <button
                onClick={handleSend}
                disabled={sending || captured || !input.trim()}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-brand text-white rounded-xl text-sm font-semibold hover:bg-brand-dark transition-colors disabled:opacity-40"
              >
                <Send size={14} /> Send
              </button>
            </div>
          </div>

          {/* RIGHT (40%) — study design summary card */}
          <div className="lg:col-span-2" ref={designCardRef}>
            {design ? (
              <EditableDesignCard
                draft={design}
                onChange={setDraft}
                onConfirm={() => onConfirm(design)}
                confounderSuggestions={confounderSuggestions}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-8 text-center">
                <p className="text-sm text-slate-400 leading-relaxed">
                  The study design summary will appear here once the conversation has gathered enough information.
                </p>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}
