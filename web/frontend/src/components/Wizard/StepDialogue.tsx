import { useEffect, useRef, useState } from 'react'
import { Send, ArrowRight } from 'lucide-react'
import type { DialogueMessage, StudyDesign } from '../../types/api'

interface Props {
  messages: DialogueMessage[]
  studyDesign: StudyDesign | null
  onSend: (msg: string) => Promise<void>
  onConfirm: (design: StudyDesign) => void
}

const DESIGN_TYPE_LABELS: Record<string, string> = {
  EXPERIMENTAL: 'Experimental', OBSERVATIONAL: 'Observational', QUASI_EXPERIMENTAL: 'Quasi-experimental',
}
const MEASUREMENT_LABELS: Record<string, string> = {
  BETWEEN_SUBJECTS: 'Between-subjects', WITHIN_SUBJECTS: 'Within-subjects', MIXED: 'Mixed',
}

export default function StepDialogue({ messages, studyDesign, onSend, onConfirm }: Props) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-send opening message
  useEffect(() => {
    if (messages.length === 0) {
      setSending(true)
      onSend('__init__').finally(() => setSending(false))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || sending) return
    setInput('')
    setSending(true)
    await onSend(msg)
    setSending(false)
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Study design</h2>
      <p className="text-slate-500 mb-6">Answer a few questions so HTA can select the right test for your design.</p>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Chat panel */}
        <div className="lg:col-span-3 flex flex-col bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden" style={{ minHeight: 480 }}>
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Conversation</p>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-brand text-white rounded-br-md'
                    : 'bg-slate-100 text-slate-800 rounded-bl-md'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            {sending && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex justify-start">
                <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-bl-md">
                  <span className="flex gap-1">
                    {[0,1,2].map(i => (
                      <span key={i} className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="p-3 border-t border-slate-100 flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              disabled={sending || !!studyDesign}
              placeholder={studyDesign ? 'Design captured — confirm on the right' : 'Type your reply…'}
              className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand disabled:bg-slate-50"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim() || !!studyDesign}
              className="p-2.5 bg-brand text-white rounded-xl hover:bg-brand-dark transition-colors disabled:opacity-40"
            >
              <Send size={16} />
            </button>
          </div>
        </div>

        {/* Design summary card */}
        <div className="lg:col-span-2">
          {studyDesign ? (
            <div className="bg-white rounded-2xl border border-indigo-200 shadow-sm p-5">
              <p className="text-xs font-semibold text-brand uppercase tracking-wide mb-4">Study design captured</p>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-slate-500 text-xs mb-0.5">Design type</dt>
                  <dd className="font-medium text-slate-800">{DESIGN_TYPE_LABELS[studyDesign.design_type]}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 text-xs mb-0.5">Measurement</dt>
                  <dd className="font-medium text-slate-800">{MEASUREMENT_LABELS[studyDesign.measurement_type]}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 text-xs mb-0.5">Randomised</dt>
                  <dd className="font-medium text-slate-800">{studyDesign.is_randomized ? 'Yes' : 'No'}</dd>
                </div>
                {studyDesign.confounders.length > 0 && (
                  <div>
                    <dt className="text-slate-500 text-xs mb-0.5">Confounders identified</dt>
                    <dd className="font-medium text-slate-800">{studyDesign.confounders.map(c => c.name).join(', ')}</dd>
                  </div>
                )}
                {studyDesign.notes.length > 0 && (
                  <div>
                    <dt className="text-slate-500 text-xs mb-0.5">Notes</dt>
                    <dd className="text-slate-600">{studyDesign.notes.join('; ')}</dd>
                  </div>
                )}
              </dl>
              <button
                onClick={() => onConfirm(studyDesign)}
                className="mt-6 w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand text-white rounded-xl text-sm font-medium hover:bg-brand-dark transition-colors"
              >
                Confirm design <ArrowRight size={15} />
              </button>
            </div>
          ) : (
            <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5 text-center text-slate-400 text-sm" style={{ minHeight: 200 }}>
              <p className="mt-8">The study design summary will appear here once the conversation is complete.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
