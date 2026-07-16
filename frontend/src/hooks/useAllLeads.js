import { useQuery } from '@tanstack/react-query'
import { listLeads } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

const PAGE_SIZE = 100

// Pipeline board needs every lead at once (columned client-side by stage), so
// this merges all pages rather than truncating at the API's page_size cap.
export function useAllLeads() {
  return useQuery({
    queryKey: ['leads', 'all'],
    queryFn: async () => {
      const first = await listLeads({ page: 1, page_size: PAGE_SIZE })
      if (!first.ok) {
        throw new Error(getErrorMessage(first, 'Failed to load pipeline'))
      }

      let items = first.data.items
      const totalPages = first.data.total_pages
      for (let page = 2; page <= totalPages; page += 1) {
        const response = await listLeads({ page, page_size: PAGE_SIZE })
        if (!response.ok) {
          throw new Error(getErrorMessage(response, 'Failed to load pipeline'))
        }
        items = items.concat(response.data.items)
      }

      return { items, total: first.data.total }
    },
  })
}
