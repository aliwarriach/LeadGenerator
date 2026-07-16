import { Map, Globe, Search } from 'lucide-react'

const SOURCE_META = {
  google_maps: { label: 'Google Maps', icon: Map },
  facebook: { label: 'Facebook', icon: Globe },
  serper: { label: 'Serper', icon: Search },
}

export function sourceMeta(source) {
  return SOURCE_META[source] ?? { label: source, icon: Map }
}

export const SOURCE_OPTIONS = Object.keys(SOURCE_META)
