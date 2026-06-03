import { useState } from 'react'
import { ArrowRight, X, Plus } from 'lucide-react'
import type { StudyDesign, StudyDesignType, MeasurementType, Confounder } from '../../types/api'

interface Props {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  messages: any[]            // kept for interface compatibility
  studyDesign: StudyDesign | null
  onSend: (msg: string) => Promise<void>   // kept for interface compatibility
  onConfirm: (design: StudyDesign) => void
}

// ── Option card ────────────────────────────────────────────────────────────────

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

// ── Question block ─────────────────────────────────────────────────────────────

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

// ── Main component ─────────────────────────────────────────────────────────────

type RelationshipForm = 'linear' | 'monotone' | 'nonlinear' | 'unknown'

export default function StepDialogue({ studyDesign, onConfirm }: Props) {
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

  if (studyDesign) {
    // Already confirmed — show read-only summary
    return (
      <div className="max-w-xl mx-auto">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Study design</h2>
        <div className="bg-white rounded-2xl border border-indigo-200 shadow-sm p-6">
          <p className="text-xs font-semibold text-brand uppercase tracking-wide mb-4">Design captured</p>
          <dl className="space-y-3 text-sm">
            {[
              ['Design type', studyDesign.design_type.replace('_', ' ')],
              ['Measurement', studyDesign.measurement_type.replace('_', ' ')],
              ['Randomised', studyDesign.is_randomized ? 'Yes' : 'No'],
              studyDesign.confounders.length > 0
                ? ['Confounders', studyDesign.confounders.map(c => c.name).join(', ')]
                : null,
              studyDesign.notes.length > 0
                ? ['Notes', studyDesign.notes.join('; ')]
                : null,
            ].filter((x): x is [string, string] => x !== null).map(([dt, dd]) => (
              <div key={dt as string}>
                <dt className="text-slate-500 text-xs mb-0.5">{dt as string}</dt>
                <dd className="font-medium text-slate-800 capitalize">{(dd as string).toLowerCase()}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-1">Study design</h2>
      <p className="text-slate-500 mb-8 text-sm">Answer a few questions so HTA can select the right statistical test.</p>

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
