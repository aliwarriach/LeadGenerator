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
      className={`mb-2.5 cursor-grab rounded-[11px] border border-line bg-ink-card p-3 transition-colors duration-150 hover:border-line-hi active:cursor-grabbing ${
        isDragging ? 'opacity-40' : ''
      }`}
    >
      <div className="text-[12.5px] font-semibold text-white">{card.name}</div>
      <div className="mt-0.5 text-[11px] text-txt-mute">{card.meta}</div>
      <div className="mt-2.5 flex items-center justify-between">
        <span className="font-mono text-[11px] text-signal">{card.value}</span>
        <GripVertical className="h-3.5 w-3.5 text-txt-mute" />
      </div>
    </div>
  )
}
