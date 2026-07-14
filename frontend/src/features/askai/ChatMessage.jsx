import MessageBlocks from './MessageBlocks'

export default function ChatMessage({ role, blocks }) {
  const isUser = role === 'user'

  return (
    <div
      className={`max-w-[82%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
        isUser
          ? 'self-end border border-signal/25 bg-signal-dim text-txt'
          : 'self-start border border-line bg-ink-soft text-txt-dim'
      }`}
    >
      <MessageBlocks blocks={blocks} />
    </div>
  )
}
