import { useEffect, useRef, useState } from 'react'
import { Sparkles, Send, Search } from 'lucide-react'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import ChatMessage from './ChatMessage'
import TypingIndicator from './TypingIndicator'
import { useChatHistory } from '../../hooks/useChatHistory'
import { useSendChatMessage } from '../../hooks/useSendChatMessage'
import { useLead } from '../../hooks/useLead'

function toBlocks(content) {
  return [{ type: 'p', text: content }]
}

export default function ChatPanel({ leadId, onOpenPicker }) {
  const [input, setInput] = useState('')
  const bodyRef = useRef(null)
  const leadQuery = useLead(leadId)
  const historyQuery = useChatHistory(leadId)
  const sendMutation = useSendChatMessage(leadId)

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [historyQuery.data, sendMutation.isPending])

  function send() {
    const text = input.trim()
    if (!text || sendMutation.isPending) return
    setInput('')
    sendMutation.mutate(text, {
      onError: () => setInput(text),
    })
  }

  if (!leadId) {
    return (
      <Card className="flex h-[600px] flex-col items-center justify-center gap-3 px-5 text-center">
        <p className="text-[13px] text-txt-mute">No business selected yet — pick one to start a conversation.</p>
        <Button onClick={onOpenPicker}>
          <Search className="h-3.5 w-3.5" /> Choose a business
        </Button>
      </Card>
    )
  }

  return (
    <Card className="flex h-[600px] flex-col">
      <div className="flex items-center gap-2.5 border-b border-line px-5 py-[15px]">
        <div className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-lg bg-violet-dim">
          <Sparkles className="h-4 w-4 text-violet" />
        </div>
        <div>
          <div className="text-[13.5px] font-semibold text-white">{leadQuery.data?.name ?? 'Loading…'} — assistant</div>
          <div className="text-[11px] text-txt-mute">Grounded on this business's data + latest audit</div>
        </div>
      </div>
      <div ref={bodyRef} className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-5">
        {historyQuery.isLoading && <p className="text-[13px] text-txt-mute">Loading conversation…</p>}
        {historyQuery.isError && <p className="text-[13px] text-red">{historyQuery.error.message}</p>}
        {historyQuery.data?.length === 0 && (
          <p className="text-[13px] text-txt-mute">Ask anything about this business to get started.</p>
        )}
        {historyQuery.data?.map((m, i) => (
          <ChatMessage key={i} role={m.role} blocks={toBlocks(m.content)} />
        ))}
        {sendMutation.isPending && <TypingIndicator />}
      </div>
      <div className="flex gap-2.5 border-t border-line px-4 py-3.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask about this business…"
          aria-label="Ask about this business"
          maxLength={2000}
          className="flex-1 rounded-[10px] border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] text-txt outline-none focus:border-violet"
        />
        <Button onClick={send} disabled={sendMutation.isPending || !input.trim()}>
          <Send className="h-3.5 w-3.5" /> Send
        </Button>
      </div>
    </Card>
  )
}
