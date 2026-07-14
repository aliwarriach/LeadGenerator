export const COUNTRIES = [
  { id: 'uae', label: 'UAE', flag: '🇦🇪' },
  { id: 'sa', label: 'Saudi Arabia', flag: '🇸🇦' },
  { id: 'us', label: 'United States', flag: '🇺🇸' },
  { id: 'uk', label: 'UK', flag: '🇬🇧' },
  { id: 'pk', label: 'Pakistan', flag: '🇵🇰' },
]

export const CITIES_BY_COUNTRY = {
  uae: [
    { id: 'uae-dubai', label: 'Dubai' },
    { id: 'uae-sharjah', label: 'Sharjah' },
    { id: 'uae-abudhabi', label: 'Abu Dhabi' },
    { id: 'uae-ajman', label: 'Ajman' },
    { id: 'uae-rak', label: 'Ras Al Khaimah' },
  ],
  sa: [
    { id: 'sa-riyadh', label: 'Riyadh' },
    { id: 'sa-jeddah', label: 'Jeddah' },
    { id: 'sa-dammam', label: 'Dammam' },
    { id: 'sa-mecca', label: 'Mecca' },
    { id: 'sa-medina', label: 'Medina' },
  ],
  us: [
    { id: 'us-nyc', label: 'New York' },
    { id: 'us-la', label: 'Los Angeles' },
    { id: 'us-chicago', label: 'Chicago' },
    { id: 'us-houston', label: 'Houston' },
    { id: 'us-miami', label: 'Miami' },
  ],
  uk: [
    { id: 'uk-london', label: 'London' },
    { id: 'uk-manchester', label: 'Manchester' },
    { id: 'uk-birmingham', label: 'Birmingham' },
    { id: 'uk-leeds', label: 'Leeds' },
    { id: 'uk-glasgow', label: 'Glasgow' },
  ],
  pk: [
    { id: 'pk-karachi', label: 'Karachi' },
    { id: 'pk-lahore', label: 'Lahore' },
    { id: 'pk-islamabad', label: 'Islamabad' },
    { id: 'pk-faisalabad', label: 'Faisalabad' },
    { id: 'pk-rawalpindi', label: 'Rawalpindi' },
  ],
}

export const INDUSTRIES = [
  { id: 'dental', label: 'Dental clinics' },
  { id: 'medspa', label: 'Med spas' },
  { id: 'restaurants', label: 'Restaurants' },
  { id: 'realestate', label: 'Real estate' },
  { id: 'gyms', label: 'Gyms & fitness' },
  { id: 'salons', label: 'Salons' },
]

export const DISCOVERY_FILTERS = [
  { id: 'rating4', label: 'Rating ≥ 4.0' },
  { id: 'reviews50', label: 'Reviews ≥ 50' },
  { id: 'open', label: 'Currently open' },
]

export const DEFAULT_SELECTION = {
  countries: ['uae'],
  cities: ['uae-dubai', 'uae-sharjah'],
  industries: ['dental'],
  filters: ['rating4'],
}

export const RUN_ESTIMATE = {
  subQueries: 14,
  expectedRange: '~380–460',
  cachedPct: '~31% free',
  costRange: '$8.40 – $10.90',
  note: 'Text Search returns max 60 results per query, so this run fans out across 14 neighborhood sub-queries and dedups on place ID. Cached places (<30 days) cost nothing.',
}
