import { useState } from 'react'
import Card from '../../components/ui/Card'
import PageHeader from '../../components/ui/PageHeader'
import FilterGroup from './FilterGroup'
import RunEstimateCard from './RunEstimateCard'
import { COUNTRIES, CITIES_BY_COUNTRY, INDUSTRIES, DISCOVERY_FILTERS, DEFAULT_SELECTION } from '../../constants/discovery'

function useToggle(initial) {
  const [selected, setSelected] = useState(initial)
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  return [selected, toggle, setSelected]
}

export default function DiscoveryView() {
  // Backend accepts exactly one country per request, so this is single-select
  // (radio-like) even though it reuses the multi-select FilterGroup UI.
  const [countryId, setCountryId] = useState(DEFAULT_SELECTION.countries[0])
  const [cities, toggleCity, setCities] = useToggle(DEFAULT_SELECTION.cities)
  const [customCity, setCustomCity] = useState('')
  const [industries, toggleIndustry] = useToggle(DEFAULT_SELECTION.industries)
  const [filters, toggleFilter] = useToggle(DEFAULT_SELECTION.filters)
  const [niche, setNiche] = useState('')

  const cityOptions = CITIES_BY_COUNTRY[countryId] ?? []

  function handleCountrySelect(id) {
    setCountryId(id)
    // Preset city ids belong to the previous country, so they'd silently
    // mismatch the new country's option list — reset and let the user repick.
    setCities([])
    setCustomCity('')
  }

  return (
    <section>
      <PageHeader
        breadcrumb="Workspace"
        title="New Discovery"
        subtitle="Find businesses via Google Places — compliant, deduped, cost-estimated before you run."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Card className="pt-5">
          <FilterGroup
            label="Country"
            options={COUNTRIES}
            selected={[countryId]}
            onToggle={handleCountrySelect}
            getLabel={(o) => `${o.flag} ${o.label}`}
          />
          <FilterGroup label="Cities" options={cityOptions} selected={cities} onToggle={toggleCity} />
          <div className="px-[22px] pb-[18px]">
            <label htmlFor="customCity" className="mb-2 block text-[11.5px] font-semibold uppercase tracking-wider text-txt-dim">
              Add another city
            </label>
            <input
              id="customCity"
              className="w-full rounded-lg border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] text-txt outline-none focus:border-signal"
              placeholder="e.g. Al Ain, Fujairah… (comma-separated)"
              value={customCity}
              onChange={(e) => setCustomCity(e.target.value)}
            />
          </div>
          <FilterGroup label="Industry" options={INDUSTRIES} selected={industries} onToggle={toggleIndustry} />
          <div className="px-[22px] pb-[18px]">
            <label htmlFor="niche" className="mb-2 block text-[11.5px] font-semibold uppercase tracking-wider text-txt-dim">
              Custom niche
            </label>
            <input
              id="niche"
              className="w-full rounded-lg border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] text-txt outline-none focus:border-signal"
              placeholder="e.g. orthodontists, cosmetic dentistry…"
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
            />
          </div>
          <FilterGroup label="Filters" options={DISCOVERY_FILTERS} selected={filters} onToggle={toggleFilter} />
        </Card>
        <RunEstimateCard
          countryId={countryId}
          cityIds={cities}
          customCity={customCity}
          industryIds={industries}
          niche={niche}
          filterIds={filters}
        />
      </div>
    </section>
  )
}
