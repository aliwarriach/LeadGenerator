import { create } from 'zustand'
import { PIPELINE_CARDS } from '../constants/pipeline'

export const usePipelineStore = create((set, get) => ({
  cards: PIPELINE_CARDS,
  moveCard: (cardId, stageId) => {
    const card = get().cards.find((c) => c.id === cardId)
    if (!card || card.stage === stageId) return null
    set((s) => ({
      cards: s.cards.map((c) => (c.id === cardId ? { ...c, stage: stageId } : c)),
    }))
    return card
  },
}))
