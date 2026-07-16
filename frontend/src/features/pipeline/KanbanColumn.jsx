import { useDroppable } from '@dnd-kit/core'
import KanbanCard from './KanbanCard'

export default function KanbanColumn({ stage, cards }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage.id })

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[200px] rounded-[13px] border p-3 transition-colors duration-150 ${
        isOver ? 'border-signal bg-signal/[.04]' : 'border-line bg-ink-soft'
      }`}
    >
      <div className="flex items-center justify-between px-1 pb-[11px] pt-0.5 text-xs font-semibold">
        <span style={{ color: stage.color }}>{stage.label}</span>
        <span className="rounded-full bg-ink-card px-2 py-0.5 font-mono text-[11px] text-txt-mute">{cards.length}</span>
      </div>
      {/* 4.75rem must match KanbanCard's fixed height; 0.625rem matches its mb-2.5 gap */}
      <div className="max-h-[calc(4.75rem*3+0.625rem*2)] overflow-y-auto overflow-x-hidden">
        {cards.map((c) => (
          <KanbanCard key={c.id} card={c} />
        ))}
      </div>
    </div>
  )
}
