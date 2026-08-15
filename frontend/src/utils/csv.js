const BUSINESS_CSV_HEADERS = ['Name', 'Category', 'Rating', 'Website', 'Score', 'Pipeline Stage']

function escapeCsvField(value) {
  const str = value == null ? '' : String(value)
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
}

export function businessesToCsv(businesses) {
  const rows = businesses.map((b) => [b.name, b.category, b.rating ?? '', b.website ?? '', b.score ?? '', b.pipelineStage ?? ''])
  return [BUSINESS_CSV_HEADERS, ...rows].map((row) => row.map(escapeCsvField).join(',')).join('\r\n')
}

// Pure client-side download — no backend endpoint exists or is needed for this.
export function downloadCsv(filename, content) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
