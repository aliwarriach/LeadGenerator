import { describe, it, expect } from 'vitest'
import { parseApiError, getErrorMessage } from './api'

describe('parseApiError', () => {
  it('parses the shared error envelope', () => {
    const response = {
      data: {
        error: {
          code: 'blocked_captcha',
          message: 'Blocked by CAPTCHA',
          retryable: true,
          retry_after_seconds: 1800,
          details: { source: 'facebook' },
        },
      },
    }

    expect(parseApiError(response)).toEqual({
      code: 'blocked_captcha',
      message: 'Blocked by CAPTCHA',
      retryable: true,
      retryAfterSeconds: 1800,
      details: { source: 'facebook' },
    })
  })

  it('falls back to a string detail (FastAPI 422 shape)', () => {
    const response = { data: { detail: 'Invalid status value' } }
    expect(parseApiError(response, 'fallback')).toMatchObject({
      message: 'Invalid status value',
      retryable: false,
      retryAfterSeconds: null,
    })
  })

  it('falls back to a validation-error array detail', () => {
    const response = { data: { detail: [{ msg: 'field required' }, { msg: 'must be one of enum' }] } }
    expect(parseApiError(response).message).toBe('field required; must be one of enum')
  })

  it('uses the fallback message when the body is unrecognized', () => {
    expect(parseApiError({ data: null }, 'Something went wrong').message).toBe('Something went wrong')
    expect(parseApiError(undefined, 'Something went wrong').message).toBe('Something went wrong')
  })
})

describe('getErrorMessage', () => {
  it('returns just the message string', () => {
    const response = { data: { error: { message: 'Failed to stop job', retryable: false } } }
    expect(getErrorMessage(response)).toBe('Failed to stop job')
  })
})
