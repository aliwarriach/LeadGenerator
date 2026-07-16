import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

export function createQueryWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  function Wrapper({ children }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  return { Wrapper, queryClient }
}
