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

// Sources fanned into for every city in a run — a fixed fact about how
// discovery works, independent of the current filter selection. Ids match
// the backend's DiscoverySourceLiteral values so real per-source stats
// (RunEstimateCard) can be joined onto these labels directly.
export const DISCOVERY_SOURCES = [
  { id: 'google_maps', label: 'Google Maps' },
  { id: 'facebook', label: 'Facebook' },
  { id: 'serper', label: 'Serper' },
]
