import { PROPOSAL_SECTION_HEADINGS } from '../../constants/askai'

// Draft storage is one markdown string (PDF renderer treats `content` as
// markdown/HTML) — sections only exist as separate fields in the editor UI.
export function sectionsToContent(sections) {
  return sections.map((s) => `## ${s.heading}\n\n${s.content}`).join('\n\n')
}

export function contentToSections(content) {
  if (!content) return PROPOSAL_SECTION_HEADINGS.map((heading) => ({ heading, content: '' }))
  const parts = content.split(/^##\s+/m).filter(Boolean)
  return parts.map((part) => {
    const [heading, ...rest] = part.split('\n')
    return { heading: heading.trim(), content: rest.join('\n').trim() }
  })
}
