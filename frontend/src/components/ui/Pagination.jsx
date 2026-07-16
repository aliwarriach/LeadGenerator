import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1)

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        className="grid h-8 w-8 place-items-center rounded-lg border border-line-hi text-txt-dim hover:bg-ink-card disabled:cursor-not-allowed disabled:opacity-40"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {pageNumbers.map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onPageChange(n)}
          aria-current={n === page ? 'page' : undefined}
          className={`grid h-8 w-8 place-items-center rounded-lg border font-mono text-xs ${
            n === page ? 'border-signal bg-signal-dim text-signal' : 'border-line-hi text-txt-dim hover:bg-ink-card'
          }`}
        >
          {n}
        </button>
      ))}
      <button
        type="button"
        className="grid h-8 w-8 place-items-center rounded-lg border border-line-hi text-txt-dim hover:bg-ink-card disabled:cursor-not-allowed disabled:opacity-40"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}
