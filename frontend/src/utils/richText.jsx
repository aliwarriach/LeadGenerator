/**
 * Splits `**bold**` markers out of a string into text/<strong> nodes.
 * Lets constants hold copy with inline emphasis without JSX or dangerouslySetInnerHTML.
 */
export function renderRichText(text) {
  return text.split('**').map((chunk, i) =>
    i % 2 === 1 ? <strong key={i} className="font-semibold text-txt">{chunk}</strong> : chunk
  )
}
