import { useState, useCallback, useEffect } from 'react'
import type {
  SessionStatus, VariableType, StudyDesign, DataProfile,
  Report, DialogueMessage, VariablesPayload,
} from '../types/api'
import { upload as apiUpload, setVariables as apiSetVariables, saveDesign as apiSaveDesign, getSession, dialogueTurn, runAnalysis as apiRunAnalysis } from '../api/client'

const SESSION_STORAGE_KEY = 'hta_session_id'

export interface SessionState {
  sessionId: string | null
  status: SessionStatus | null
  step: 1 | 2 | 3 | 4 | 5 | 6
  restoring: boolean   // true while the initial localStorage restore check is in flight
  // Step 1 — Upload
  columns: string[]
  inferredTypes: Record<string, VariableType>
  preview: Record<string, unknown>[]
  // Step 3 — Variables
  variables: VariablesPayload | null
  profile: DataProfile | null      // BET EDA profile (step 2 Explore), fetched after the variables step
  // Step 4 — Design dialogue
  messages: DialogueMessage[]
  studyDesign: StudyDesign | null
  dialogueTurn: number
  // Steps 5–6 — run (triggered from Review) + Results
  progressMessage: string
  progressStage: string
  report: Report | null
  error: string | null
}

const INITIAL: SessionState = {
  sessionId: null, status: null, step: 1,
  restoring: typeof localStorage !== 'undefined' && !!localStorage.getItem(SESSION_STORAGE_KEY),
  columns: [], inferredTypes: {}, preview: [],
  variables: null, profile: null,
  messages: [], studyDesign: null, dialogueTurn: 0,
  progressMessage: '', progressStage: '', report: null, error: null,
}

export function useSession() {
  const [state, setState] = useState<SessionState>(INITIAL)

  const update = useCallback((patch: Partial<SessionState>) =>
    setState(s => ({ ...s, ...patch })), [])

  // Restore a COMPLETE session from localStorage on mount (avoids losing results on refresh).
  useEffect(() => {
    const savedId = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!savedId) return
    getSession(savedId)
      .then(session => {
        if (session.status === 'COMPLETE' && session.report) {
          update({
            sessionId: savedId,
            status: 'COMPLETE',
            step: 6,
            restoring: false,
            profile: session.profile ?? null,
            studyDesign: session.design ?? null,
            report: session.report,
          })
        } else {
          // Incomplete or failed session — drop the stale reference.
          localStorage.removeItem(SESSION_STORAGE_KEY)
          update({ restoring: false })
        }
      })
      .catch(() => {
        localStorage.removeItem(SESSION_STORAGE_KEY)
        update({ restoring: false })
      })
  }, [update])

  // Step 1 — upload CSV
  const upload = useCallback(async (file: File) => {
    update({ error: null })
    try {
      const res = await apiUpload(file)
      localStorage.setItem(SESSION_STORAGE_KEY, res.session_id)
      update({
        sessionId: res.session_id,
        status: res.status,
        columns: res.columns,
        inferredTypes: res.inferred_types,
        preview: res.preview,
        step: 2,  // → BET Explore step
      })
    } catch (e) {
      update({ error: String(e) })
    }
  }, [update])

  // Step 3 — set variables and hypothesis, then fetch the full profile (which includes
  // the pre-computed BET EDA if the user ran the Explore step).
  const setVariables = useCallback(async (payload: VariablesPayload) => {
    if (!state.sessionId) return
    await apiSetVariables(state.sessionId, payload)
    let profile: DataProfile | null = null
    try {
      const s = await getSession(state.sessionId)
      profile = s.profile ?? null
    } catch { /* non-fatal — the EDA panel simply won't render */ }
    update({ variables: payload, profile, step: 4 })
  }, [state.sessionId, update])

  // Step 4 — one dialogue turn (streamed). Returns stream stats so the caller can
  // detect degenerate streams (a dry-run stub completing instantly, or a dead LLM).
  // Messages prefixed '__init__' open the dialogue: they are hidden from the visible
  // chat, and the prefix is stripped before sending so the remainder (researcher
  // framing + BET EDA context) becomes the first stored user turn — live providers
  // require a non-empty message history.
  const sendMessage = useCallback(async (
    userMessage: string,
  ): Promise<{ tokens: number; isComplete: boolean }> => {
    if (!state.sessionId) return { tokens: 0, isComplete: false }

    const isInit = userMessage.startsWith('__init__')
    if (!isInit) {
      update({ messages: [...state.messages, { role: 'user', content: userMessage }] })
    }
    const wireMessage = isInit
      ? (userMessage.slice('__init__'.length).trimStart() || '__init__')
      : userMessage

    let assistantText = ''
    let finalDesign: StudyDesign | null = null
    let tokenCount = 0

    for await (const event of dialogueTurn(state.sessionId, wireMessage)) {
      if (event.type === 'token' && typeof event.content === 'string') {
        tokenCount += 1
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
        if (event.is_complete && event.study_design) {
          finalDesign = event.study_design as StudyDesign
        }
      }
    }

    update({
      dialogueTurn: state.dialogueTurn + 1,
      studyDesign: finalDesign ?? state.studyDesign,
    })
    return { tokens: tokenCount, isComplete: finalDesign !== null }
  }, [state, update])

  const confirmDesign = useCallback(async (design: StudyDesign) => {
    update({ studyDesign: design, step: 5 })
    if (state.sessionId) {
      try { await apiSaveDesign(state.sessionId, design) } catch { /* non-fatal — run uses DEFAULT_DESIGN as fallback */ }
    }
  }, [state.sessionId, update])

  // Step 6 — run analysis (streamed)
  const runAnalysis = useCallback(async () => {
    if (!state.sessionId) return
    update({ step: 6, status: 'RUNNING', progressMessage: 'Starting analysis…', progressStage: '', error: null })

    try {
      for await (const event of apiRunAnalysis(state.sessionId)) {
        if (event.type === 'progress' && typeof event.message === 'string') {
          update({
            progressMessage: event.message,
            progressStage: typeof event.stage === 'string' ? event.stage : '',
          })
        } else if (event.type === 'result' && event.report) {
          update({ report: event.report as Report, status: 'COMPLETE', progressMessage: '', progressStage: '' })
        }
      }
    } catch (e) {
      update({ status: 'FAILED', progressMessage: '', progressStage: '', error: String(e) })
    }
  }, [state.sessionId, update])

  const reset = useCallback(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY)
    setState({ ...INITIAL, restoring: false })
  }, [])

  return { state, upload, setVariables, sendMessage, confirmDesign, runAnalysis, reset, update }
}
