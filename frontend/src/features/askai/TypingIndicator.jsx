export default function TypingIndicator() {
  return (
    <div
      className="flex max-w-[82%] items-center gap-1 self-start rounded-2xl border border-line bg-ink-soft px-4 py-3"
      aria-label="Assistant is typing"
    >
      {[0, 1, 2].map((i) => (
        <i
          key={i}
          className="h-1.5 w-1.5 animate-typing-dot rounded-full bg-txt-mute"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}
