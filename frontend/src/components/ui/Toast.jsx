import { useToastStore } from '../../store/useToastStore'
import { renderRichText } from '../../utils/richText'

export default function Toast() {
  const message = useToastStore((s) => s.message)
  const visible = useToastStore((s) => s.visible)

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 rounded-xl border border-signal bg-ink-card px-[18px] py-3 text-[13px] text-txt shadow-2xl transition-all duration-200 ${
        visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-2.5 opacity-0'
      }`}
    >
      {message ? renderRichText(message) : null}
    </div>
  )
}
