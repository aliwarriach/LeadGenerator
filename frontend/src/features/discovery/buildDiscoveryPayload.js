import { COUNTRIES, CITIES_BY_COUNTRY, INDUSTRIES } from '../../constants/discovery'

const RATING_FILTER_ID = 'rating4'
const MIN_RATING_VALUE = 4.0

function labelFor(options, id) {
  return options.find((o) => o.id === id)?.label
}

export function buildDiscoveryPayload({ countryId, cityIds, customCity, industryIds, niche, filterIds }) {
  const country = labelFor(COUNTRIES, countryId)
  const cityOptions = CITIES_BY_COUNTRY[countryId] ?? []
  const chipCityLabels = cityIds.map((id) => labelFor(cityOptions, id)).filter(Boolean)
  const typedCityLabels = customCity
    .split(',')
    .map((city) => city.trim())
    .filter(Boolean)
  const cityLabels = [...new Set([...chipCityLabels, ...typedCityLabels])]

  const customNiche =
    niche.trim() ||
    industryIds
      .map((id) => labelFor(INDUSTRIES, id))
      .filter(Boolean)
      .join(', ')

  const fieldErrors = {}
  if (!country) fieldErrors.country = 'Select a country.'
  if (cityLabels.length === 0) fieldErrors.city = 'Select or type at least one city.'
  if (!customNiche) fieldErrors.niche = 'Enter a custom niche or select an industry.'

  const errors = Object.values(fieldErrors)

  if (errors.length > 0) {
    return { payload: null, errors, fieldErrors }
  }

  return {
    payload: {
      country,
      city: cityLabels.join(', '),
      custom_niche: customNiche,
      ...(filterIds.includes(RATING_FILTER_ID) ? { min_rating: MIN_RATING_VALUE } : {}),
    },
    errors: [],
    fieldErrors: {},
  }
}
