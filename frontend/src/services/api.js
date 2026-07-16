import { create } from 'apisauce'

export const api = create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})

// Shared error envelope: { error: { code, message, retryable, retry_after_seconds, details } }.
// The one exception is a 422 from a malformed query param, which returns FastAPI's
// default validation shape ({ detail: string | [{msg, ...}] }) instead — handled below.
export function parseApiError(response, fallbackMessage = 'Something went wrong') {
  const body = response?.data
  const envelope = body?.error

  if (envelope) {
    return {
      code: envelope.code ?? null,
      message: envelope.message || fallbackMessage,
      retryable: Boolean(envelope.retryable),
      retryAfterSeconds: envelope.retry_after_seconds ?? null,
      details: envelope.details ?? null,
    }
  }

  const detailMessage = Array.isArray(body?.detail)
    ? body.detail.map((d) => d.msg).filter(Boolean).join('; ')
    : typeof body?.detail === 'string'
      ? body.detail
      : null

  return {
    code: null,
    message: detailMessage || fallbackMessage,
    retryable: false,
    retryAfterSeconds: null,
    details: null,
  }
}

export function getErrorMessage(response, fallback = 'Something went wrong') {
  return parseApiError(response, fallback).message
}
