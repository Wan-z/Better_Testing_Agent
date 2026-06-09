// Real API client — all calls go to /api (proxied to FastAPI in dev).

import type { SessionResponse, StudyDesign, UploadResponse, VariablesPayload } from '../types/api'

const BASE = '/api'

async function* sseStream(res: Response): AsyncGenerator<Record<string, unknown>> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()!
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)) } catch { /* skip malformed */ }
      }
    }
  }
}

export async function upload(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/sessions`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function setVariables(sessionId: string, payload: VariablesPayload): Promise<void> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/variables`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await res.text())
}

export async function saveDesign(sessionId: string, design: StudyDesign): Promise<void> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/design`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(design),
  })
  if (!res.ok) throw new Error(await res.text())
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function* dialogueTurn(
  sessionId: string,
  userMessage: string,
): AsyncGenerator<Record<string, unknown>> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/dialogue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_message: userMessage }),
  })
  if (!res.ok) throw new Error(await res.text())
  yield* sseStream(res)
}

export async function* runAnalysis(
  sessionId: string,
): AsyncGenerator<Record<string, unknown>> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/run`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  yield* sseStream(res)
}

export async function previewTest(
  sessionId: string,
): Promise<{ test_name: string; rationale: string; caveats: string[] }> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/preview-test`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function exportHtmlUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/export/html`
}
