import { useNavigate } from 'react-router-dom'
import { useSession } from '../../hooks/useSession'
import StepUpload from './StepUpload'
import StepBET from './StepBET'
import StepVariables from './StepVariables'
import StepDialogue from './StepDialogue'
import StepReview from './StepReview'
import StepResults from './StepResults'

const STEP_LABELS = ['Upload', 'Explore', 'Variables', 'Design', 'Review', 'Results']

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
            const stepNum = (i + 1) as 1 | 2 | 3 | 4 | 5 | 6
            const active = state.step === stepNum
            const done   = state.step > stepNum
            const chip = (
              <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full transition-colors ${
                active ? 'bg-brand text-white' :
                done   ? 'bg-indigo-100 text-brand hover:bg-indigo-200' :
                         'text-slate-400'
              }`}>
                {done ? '✓' : stepNum}
                <span className="hidden sm:inline">{label}</span>
              </span>
            )
            return (
              <div key={label} className="flex items-center gap-2">
                {i > 0 && <div className="w-6 h-px bg-slate-200" />}
                {done
                  ? <button title={`Go back to ${label}`} onClick={() => session.update({ step: stepNum })}>{chip}</button>
                  : chip
                }
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
        {state.restoring && (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
            Restoring session…
          </div>
        )}
        <div key={state.step} className="animate-[fadeIn_0.25s_ease-out]">
        {!state.restoring && state.step === 1 && <StepUpload onUpload={session.upload} />}
        {state.step === 2 && state.sessionId && (
          <StepBET
            columns={state.columns}
            inferredTypes={state.inferredTypes}
            sessionId={state.sessionId}
            onNext={() => session.update({ step: 3 })}
          />
        )}
        {state.step === 3 && (
          <StepVariables
            columns={state.columns}
            inferredTypes={state.inferredTypes}
            preview={state.preview}
            onNext={session.setVariables}
          />
        )}
        {state.step === 4 && (
          <StepDialogue
            sessionId={state.sessionId}
            messages={state.messages}
            studyDesign={state.studyDesign}
            edaSummary={state.profile?.eda_summary ?? null}
            variables={state.variables}
            onSend={session.sendMessage}
            onConfirm={session.confirmDesign}
          />
        )}
        {state.step === 5 && state.variables && state.studyDesign && (
          <StepReview
            sessionId={state.sessionId}
            profile={state.profile}
            variables={state.variables}
            studyDesign={state.studyDesign}
            onRun={session.runAnalysis}
            onBack={() => session.update({ step: 3 })}
          />
        )}
        {state.step === 6 && (
          <StepResults
            report={state.report}
            sessionId={state.sessionId}
            progressMessage={state.progressMessage}
            progressStage={state.progressStage}
            error={state.error}
            onReset={session.reset}
          />
        )}
        </div>
      </main>
    </div>
  )
}
