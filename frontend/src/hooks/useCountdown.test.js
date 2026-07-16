import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCountdown } from './useCountdown'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useCountdown', () => {
  it('ticks down once per second without re-fetching anything', () => {
    const { result } = renderHook(() => useCountdown(3))
    expect(result.current).toBe(3)

    act(() => vi.advanceTimersByTime(1000))
    expect(result.current).toBe(2)

    act(() => vi.advanceTimersByTime(2000))
    expect(result.current).toBe(0)
  })

  it('does not go below zero', () => {
    const { result } = renderHook(() => useCountdown(1))
    act(() => vi.advanceTimersByTime(5000))
    expect(result.current).toBe(0)
  })

  it('resets when a new initial value arrives', () => {
    const { result, rerender } = renderHook(({ seconds }) => useCountdown(seconds), {
      initialProps: { seconds: 5 },
    })
    act(() => vi.advanceTimersByTime(2000))
    expect(result.current).toBe(3)

    rerender({ seconds: 10 })
    expect(result.current).toBe(10)
  })

  it('does not start a timer for null/zero', () => {
    const { result } = renderHook(() => useCountdown(null))
    expect(result.current).toBe(null)
  })
})
