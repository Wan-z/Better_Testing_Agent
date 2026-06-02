import { useState, useCallback } from 'react'
import type {
  SessionStatus, VariableType, StudyDesign,
  Report, DialogueMessage, VariablesPayload,
} from '../types/api'
import {
  mockUpload, mockSetVariables, mockDialogueTurn, mockRunAnalysis,
} from '../api/mock'

export interface SessionState {
  sessionId: string | null
  status: SessionStatus | null
  step: 1 | 2 | 3 | 4 | 5
  // Step 1
  columns: string[]
  inferredTypes: Record<string, VariableType>
  preview: Record<string, unknown>[]
  // Step 2
  variables: VariablesPayload | null
  // Step 3
  messages: DialogueMessage[]
  studyDesign: StudyDesign | null
  dialogueTurn: number
  // Step 4 / 5
  progressMessage: string
  report: Report | null
  error: string | null
}

const INITIAL: SessionState = {
  sessionId: null, status: null, step: 1,
  columns: [], inferredTypes: {}, preview: [],
  variables: null,
  messages: [], studyDesign: null, dialogueTurn: 0,
  progressMessage: '', report: null, error: null,
}

export function useSession() {
  const [state, setState] = useState<SessionState>(INITIAL)

  const update = useCallback((patch: Partial<SessionState>) =>
    setState(s => ({ ...s, ...patch })), [])

  // Step 1 — upload CSV
  const upload = useCallback(async (file: File) => {
    update({ error: null })
    try {
      const res = await mockUpload(file)
      update({
        sessionId: res.session_id,
        status: res.status,
        columns: res.columns,
        inferredTypes: res.inferred_types,
        preview: res.preview,
        step: 2,
      })
    } catch (e) {
      update({ error: String(e) })
    }
  }, [update])

  // Step 2 — set variables and hypothesis
  const setVariables = useCallback(async (payload: VariablesPayload) => {
    if (!state.sessionId) return
    await mockSetVariables(state.sessionId, payload)
    update({ variables: payload, step: 3 })
  }, [state.sessionId, update])

  // Step 3 — one dialogue turn (streamed)
  const sendMessage = useCallback(async (userMessage: string) => {
    if (!state.sessionId) return
    update({
      messages: [...state.messages, { role: 'user', content: userMessage }],
    })

    let assistantText = ''
    let finalDesign: StudyDesign | null = null

    for await (const event of mockDialogueTurn(state.sessionId, userMessage, state.dialogueTurn)) {
      if (event.type === 'token' && event.content) {
        assistantText += event.content
        setState(s => {
          const msgs = [...s.messages]
          const last = msgs[msgs.length - 1]
          if (last?.role === 'assistant') {
            msgs[msgs.length - 1] = { role: 'assistant', content: assistantText }
          } else {
            msgs.push({ role: 'assistant', content: assistantText })
          }
          return { ...s, messages: msgs }
        })
      } else if (event.type === 'done') {
        if (event.study_design) finalDesign = event.study_design
      }
    }

    update({
      dialogueTurn: state.dialogueTurn + 1,
      studyDesign: finalDesign ?? state.studyDesign,
    })
  }, [state, update])

  const confirmDesign = useCallback((design: StudyDesign) => {
    update({ studyDesign: design, step: 4 })
  }, [update])

  // Step 4 — run analysis (streamed)
  const runAnalysis = useCallback(async () => {
    if (!state.sessionId) return
    update({ step: 5, status: 'RUNNING', progressMessage: 'Starting analysis…' })

    for await (const event of mockRunAnalysis(state.sessionId)) {
      if (event.type === 'progress' && event.message) {
        update({ progressMessage: event.message })
      } else if (event.type === 'result' && event.report) {
        update({ report: event.report, status: 'COMPLETE', progressMessage: '' })
      }
    }
  }, [state.sessionId, update])

  const reset = useCallback(() => setState(INITIAL), [])

  return { state, upload, setVariables, sendMessage, confirmDesign, runAnalysis, reset, update }
}
