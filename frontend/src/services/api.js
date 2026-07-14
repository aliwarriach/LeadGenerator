import { create } from 'apisauce'

export const api = create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})

export function getErrorMessage(response, fallback = 'Something went wrong') {
  return response?.data?.detail || fallback
}
