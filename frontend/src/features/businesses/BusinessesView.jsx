import { useMemo, useState } from 'react'
import Card from '../../components/ui/Card'
import PageHeader from '../../components/ui/PageHeader'
import Button from '../../components/ui/Button'
import BusinessFilters from './BusinessFilters'
import BusinessTable from './BusinessTable'
import { useToastStore } from '../../store/useToastStore'
import { useLeads } from '../../hooks/useLeads'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { mapLeadToBusiness } from './mapLeadToBusiness'

const PAGE_SIZE = 50

// 'scoreLow' has no backend equivalent (only min_website_score exists, not a
// max), so it's applied client-side over the fetched page below.
const FILTER_PARAMS = {
  all: {},
  has: { has_website: true },
  no: { has_website: false },
  rating45: { min_rating: 4.5 },
  scoreLow: {},
}

export default function BusinessesView() {
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const show = useToastStore((s) => s.show)
  const debouncedSearch = useDebouncedValue(search, 300)

  const queryParams = useMemo(
    () => ({
      ...FILTER_PARAMS[filter],
      ...(debouncedSearch ? { name: debouncedSearch } : {}),
      page: 1,
      page_size: PAGE_SIZE,
    }),
    [filter, debouncedSearch]
  )

  const { data, isLoading, isError, error, refetch } = useLeads(queryParams)

  const businesses = useMemo(() => {
    const items = (data?.items ?? []).map(mapLeadToBusiness)
    return filter === 'scoreLow' ? items.filter((b) => b.score != null && b.score < 60) : items
  }, [data, filter])

  const subtitle = isLoading
    ? 'Loading results…'
    : isError
      ? 'Unable to load results'
      : `${data.total} result${data.total === 1 ? '' : 's'}${data.total > PAGE_SIZE ? ` · showing first ${PAGE_SIZE}` : ''}`

  return (
    <section>
      <PageHeader
        breadcrumb="Workspace"
        title="Businesses"
        subtitle={subtitle}
        actions={
          <Button variant="ghost" onClick={() => show('**CSV exported** — check your downloads')}>
            ↓ Export CSV
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <BusinessFilters active={filter} onSelect={setFilter} />
        <input
          className="ml-auto w-[220px] rounded-lg border border-line bg-ink-soft px-3.5 py-2 text-[13px] text-txt outline-none focus:border-signal"
          placeholder="Search businesses…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search businesses"
        />
      </div>
      <Card>
        {isLoading ? (
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading businesses…</p>
        ) : isError ? (
          <div className="px-5 py-10 text-center text-[13px]">
            <p className="mb-3 text-red">{error.message}</p>
            <Button variant="ghost" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        ) : (
          <BusinessTable businesses={businesses} />
        )}
      </Card>
    </section>
  )
}
