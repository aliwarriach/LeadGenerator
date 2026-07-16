import { useMemo } from 'react'
import { DndContext, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import Button from '../../components/ui/Button'
import KanbanColumn from './KanbanColumn'
import { PIPELINE_STAGES } from '../../constants/pipeline'
import { useAllLeads } from '../../hooks/useAllLeads'
import { useUpdateLeadStage } from '../../hooks/useUpdateLeadStage'
import { useToastStore } from '../../store/useToastStore'
import { mapLeadToCard } from './mapLeadToCard'

export default function PipelineView() {
  const show = useToastStore((s) => s.show)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))
  const { data, isLoading, isError, error, refetch } = useAllLeads()
  const updateStage = useUpdateLeadStage()

  const cards = useMemo(() => (data?.items ?? []).map(mapLeadToCard), [data])

  function handleDragEnd(event) {
    const { active, over } = event
    if (!over) return
    const card = cards.find((c) => c.id === active.id)
    if (!card || card.stage === over.id) return

    const stage = PIPELINE_STAGES.find((s) => s.id === over.id)
    updateStage.mutate(
      { leadId: card.id, stage: over.id },
      {
        onSuccess: () => show(`**${card.name}** moved to ${stage.label} — logged to activity`),
        onError: (err) => show(err.message),
      }
    )
  }

  return (
    <section>
      <PageHeader
        breadcrumb="Workspace"
        title="Pipeline"
        subtitle="Drag cards between stages — every move is logged to the activity timeline."
        actions={
          !isLoading &&
          !isError && (
            <Chip tone="signal" className="font-mono">
              {data.total} lead{data.total === 1 ? '' : 's'}
            </Chip>
          )
        }
      />
      {isLoading ? (
        <Card>
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading pipeline…</p>
        </Card>
      ) : isError ? (
        <Card>
          <div className="px-5 py-10 text-center text-[13px]">
            <p className="mb-3 text-red">{error.message}</p>
            <Button variant="ghost" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        </Card>
      ) : data.total === 0 ? (
        <Card>
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No leads yet — run a discovery search to populate the pipeline.</p>
        </Card>
      ) : (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {PIPELINE_STAGES.map((stage) => (
              <KanbanColumn key={stage.id} stage={stage} cards={cards.filter((c) => c.stage === stage.id)} />
            ))}
          </div>
        </DndContext>
      )}
    </section>
  )
}
