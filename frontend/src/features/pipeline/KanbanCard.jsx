import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'

export default function KanbanCard({ card }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: card.id })
  const style = { transform: CSS.Translate.toString(transform) }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`mb-2.5 flex h-[4.75rem] cursor-grab flex-col justify-between rounded-[11px] border border-line bg-ink-card p-3 transition-colors duration-150 hover:border-line-hi active:cursor-grabbing ${
        isDragging ? 'opacity-40' : ''
      }`}
    >
      <div>
        <div className="truncate text-[12.5px] font-semibold text-white">{card.name}</div>
        <div className="mt-0.5 truncate text-[11px] text-txt-mute">{card.meta}</div>
      </div>
      <div className="flex items-center justify-between">
        {card.revenueLevel ? (
          <span className="truncate font-mono text-[11px] text-signal">{card.revenueLevel}</span>
        ) : (
          <span />
        )}
        <GripVertical className="h-3.5 w-3.5 shrink-0 text-txt-mute" />
      </div>
    </div>
  )
}
