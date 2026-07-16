import { useEffect, useState } from 'react'

// Ticks down client-side from a server-provided seconds value instead of
// re-polling every second just to watch a number count down.
export function useCountdown(initialSeconds) {
  const [secondsLeft, setSecondsLeft] = useState(initialSeconds)

  useEffect(() => {
    setSecondsLeft(initialSeconds)
    if (initialSeconds == null || initialSeconds <= 0) return undefined

    const interval = setInterval(() => {
      setSecondsLeft((current) => (current == null ? current : Math.max(0, current - 1)))
    }, 1000)

    return () => clearInterval(interval)
  }, [initialSeconds])

  return secondsLeft
}
