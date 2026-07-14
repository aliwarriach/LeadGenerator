import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import PageHeader from '../../components/ui/PageHeader'
import Chip from '../../components/ui/Chip'
import KanbanColumn from './KanbanColumn'
import { PIPELINE_STAGES, PIPELINE_TOTAL_VALUE } from '../../constants/pipeline'
import { usePipelineStore } from '../../store/usePipelineStore'
import { useToastStore } from '../../store/useToastStore'

export default function PipelineView() {
  const cards = usePipelineStore((s) => s.cards)
  const moveCard = usePipelineStore((s) => s.moveCard)
  const show = useToastStore((s) => s.show)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  function handleDragEnd(event) {
    const { active, over } = event
    if (!over) return
    const moved = moveCard(active.id, over.id)
    if (moved) {
      const stage = PIPELINE_STAGES.find((s) => s.id === over.id)
      show(`**${moved.name}** moved to ${stage.label} — logged to activity`)
    }
  }

  return (
    <section>
      <PageHeader
        breadcrumb="Workspace"
        title="Pipeline"
        subtitle="Drag cards between stages — every move is logged to the activity timeline."
        actions={
          <Chip tone="signal" className="font-mono">
            {PIPELINE_TOTAL_VALUE}
          </Chip>
        }
      />
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {PIPELINE_STAGES.map((stage) => (
            <KanbanColumn key={stage.id} stage={stage} cards={cards.filter((c) => c.stage === stage.id)} />
          ))}
        </div>
      </DndContext>
    </section>
  )
}
