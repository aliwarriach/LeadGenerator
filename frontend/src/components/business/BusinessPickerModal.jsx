import { useMemo, useState } from 'react'
import { Search, Check, Star, Globe } from 'lucide-react'
import Modal from '../ui/Modal'
import { useLeads } from '../../hooks/useLeads'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

const PAGE_SIZE = 8

// Search-and-select entity switcher, reusing the exact server-side search
// pattern established in BusinessesView (debounced name filter -> useLeads).
// Shared across features (Ask AI, Audit) — lives in components/, not inside
// any one feature, per the no-cross-feature-import-of-internals rule.
export default function BusinessPickerModal({ open, onClose, activeLeadId, onSelect }) {
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)

  const queryParams = useMemo(
    () => ({ ...(debouncedSearch ? { name: debouncedSearch } : {}), page: 1, page_size: PAGE_SIZE }),
    [debouncedSearch]
  )

  const { data, isLoading, isError, error } = useLeads(queryParams)
  // Website-less leads sort last: several destinations reached through this
  // picker (e.g. Audit) can't do anything useful with them, so surfacing
  // "audit-able" businesses first avoids picking a dead end by accident.
  const results = useMemo(() => {
    const items = data?.items ?? []
    return [...items].sort((a, b) => Number(b.has_website) - Number(a.has_website))
  }, [data])

  function handleClose() {
    setSearch('')
    onClose()
  }

  function handleSelect(leadId) {
    onSelect(leadId)
    setSearch('')
  }

  return (
    <Modal open={open} onClose={handleClose} title="Switch business">
      <div className="relative mb-3.5">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-txt-mute" />
        <input
          autoFocus
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search businesses by name…"
          aria-label="Search businesses"
          className="w-full rounded-lg border border-line bg-ink-soft py-2.5 pl-9 pr-3.5 text-[13px] text-txt outline-none focus:border-signal"
        />
      </div>

      <div className="max-h-[340px] space-y-1.5 overflow-y-auto">
        {isLoading && <p className="px-1 py-4 text-center text-[12.5px] text-txt-mute">Loading businesses…</p>}
        {isError && <p className="px-1 py-4 text-center text-[12.5px] text-red">{error.message}</p>}
        {!isLoading && !isError && results.length === 0 && (
          <p className="px-1 py-4 text-center text-[12.5px] text-txt-mute">
            No businesses match "{debouncedSearch}" — try a different name.
          </p>
        )}
        {results.map((lead) => {
          const isActive = lead.id === activeLeadId
          return (
            <button
              key={lead.id}
              type="button"
              onClick={() => handleSelect(lead.id)}
              className={`flex w-full items-center justify-between gap-3 rounded-[10px] border px-3.5 py-2.5 text-left transition-colors duration-150 ${
                isActive ? 'border-signal bg-signal-dim' : 'border-line-hi hover:border-signal'
              }`}
            >
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold text-white">{lead.name}</div>
                <div className="truncate text-[11.5px] text-txt-mute">
                  {lead.category ?? lead.search_location ?? 'Uncategorized'}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                {!lead.has_website && (
                  <span className="flex items-center gap-1 text-[11px] text-amber" title="No website — some actions won't be available">
                    <Globe className="h-3 w-3" /> No site
                  </span>
                )}
                {lead.rating != null && (
                  <span className="flex items-center gap-1 text-[11.5px] text-txt-dim">
                    <Star className="h-3 w-3 text-amber" /> {lead.rating}
                  </span>
                )}
                {isActive && <Check className="h-4 w-4 text-signal" />}
              </div>
            </button>
          )
        })}
      </div>
    </Modal>
  )
}
