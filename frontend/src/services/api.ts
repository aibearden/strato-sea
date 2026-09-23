import type { SearchResponse, Vessel } from '../types/vessel'

export async function searchVessels(query: string): Promise<Vessel[]> {
  const trimmed = query.trim()
  if (!trimmed) {
    return []
  }
  const response = await fetch(`/api/vessels/search?q=${encodeURIComponent(trimmed)}`)
  if (!response.ok) {
    throw new Error('Search failed')
  }
  const data = (await response.json()) as SearchResponse
  return data.vessels
}
