import { useEffect, useRef, useState } from 'react'
import { Sparkles, Send } from 'lucide-react'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import ChatMessage from './ChatMessage'
import TypingIndicator from './TypingIndicator'
import { CHAT_SUBJECT, INITIAL_MESSAGES, AI_REPLIES } from '../../constants/askai'

export default function ChatPanel() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const nextId = useRef(INITIAL_MESSAGES.length + 1)
  const replyIndex = useRef(0)
  const bodyRef = useRef(null)

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [messages, typing])

  function send() {
    const text = input.trim()
    if (!text) return
    setMessages((m) => [...m, { id: nextId.current++, role: 'user', blocks: [{ type: 'p', text }] }])
    setInput('')
    setTyping(true)
    setTimeout(() => {
      const reply = AI_REPLIES[replyIndex.current % AI_REPLIES.length]
      replyIndex.current += 1
      setTyping(false)
      setMessages((m) => [...m, { id: nextId.current++, role: 'assistant', blocks: [{ type: 'p', text: reply }] }])
    }, 1100)
  }

  return (
    <Card className="flex h-[600px] flex-col">
      <div className="flex items-center gap-2.5 border-b border-line px-5 py-[15px]">
        <div className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-lg bg-violet-dim">
          <Sparkles className="h-4 w-4 text-violet" />
        </div>
        <div>
          <div className="text-[13.5px] font-semibold text-white">{CHAT_SUBJECT.title}</div>
          <div className="text-[11px] text-txt-mute">{CHAT_SUBJECT.context}</div>
        </div>
      </div>
      <div ref={bodyRef} className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-5">
        {messages.map((m) => (
          <ChatMessage key={m.id} role={m.role} blocks={m.blocks} />
        ))}
        {typing && <TypingIndicator />}
      </div>
      <div className="flex gap-2.5 border-t border-line px-4 py-3.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask about this business…"
          aria-label="Ask about this business"
          className="flex-1 rounded-[10px] border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] text-txt outline-none focus:border-violet"
        />
        <Button onClick={send}>
          <Send className="h-3.5 w-3.5" /> Send
        </Button>
      </div>
    </Card>
  )
}
