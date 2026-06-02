import { useNavigate } from 'react-router-dom'
import { useSession } from '../../hooks/useSession'
import StepUpload from './StepUpload'
import StepVariables from './StepVariables'
import StepDialogue from './StepDialogue'
import StepReview from './StepReview'
import StepResults from './StepResults'

const STEP_LABELS = ['Upload', 'Variables', 'Design', 'Review', 'Results']

export default function Wizard() {
  const navigate = useNavigate()
  const session = useSession()
  const { state } = session

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Nav */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <button onClick={() => navigate('/')} className="font-semibold text-brand text-lg">HTA</button>
        <div className="flex items-center gap-2">
          {STEP_LABELS.map((label, i) => {
            const stepNum = (i + 1) as 1 | 2 | 3 | 4 | 5
            const active = state.step === stepNum
            const done   = state.step > stepNum
            return (
              <div key={label} className="flex items-center gap-2">
                {i > 0 && <div className="w-8 h-px bg-slate-200" />}
                <div className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full transition-colors ${
                  active ? 'bg-brand text-white' :
                  done   ? 'bg-indigo-100 text-brand' :
                           'text-slate-400'
                }`}>
                  {done ? '✓' : stepNum}
                  <span className="hidden sm:inline">{label}</span>
                </div>
              </div>
            )
          })}
        </div>
        {state.sessionId && (
          <span className="text-xs text-slate-400 font-mono hidden md:block">
            {state.sessionId.slice(0, 8)}…
          </span>
        )}
      </nav>

      {/* Step content */}
      <main className="max-w-5xl mx-auto px-4 py-10">
        {state.step === 1 && <StepUpload onUpload={session.upload} />}
        {state.step === 2 && (
          <StepVariables
            columns={state.columns}
            inferredTypes={state.inferredTypes}
            preview={state.preview}
            onNext={session.setVariables}
          />
        )}
        {state.step === 3 && (
          <StepDialogue
            messages={state.messages}
            studyDesign={state.studyDesign}
            onSend={session.sendMessage}
            onConfirm={session.confirmDesign}
          />
        )}
        {state.step === 4 && state.variables && state.studyDesign && (
          <StepReview
            profile={state.report?.data_profile ?? null}
            variables={state.variables}
            studyDesign={state.studyDesign}
            onRun={session.runAnalysis}
          />
        )}
        {state.step === 5 && (
          <StepResults
            report={state.report}
            progressMessage={state.progressMessage}
            onReset={session.reset}
          />
        )}
      </main>
    </div>
  )
}
