import { renderRichText } from '../../utils/richText'

export default function MessageBlocks({ blocks }) {
  return (
    <>
      {blocks.map((block, i) =>
        block.type === 'ul' ? (
          <ul key={i} className="ml-4 mt-1.5 list-disc space-y-1">
            {block.items.map((item, j) => (
              <li key={j}>{renderRichText(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={i} className={i > 0 ? 'mt-1.5' : ''}>
            {renderRichText(block.text)}
          </p>
        )
      )}
    </>
  )
}
