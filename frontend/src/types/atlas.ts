export interface AtlasItem {
  id: string
  label: string
  x: number // percentage
  y: number // percentage
  definition: string
  example: string
}

export interface AtlasTheme {
  id: string
  title: string
  description: string
  image: string
  items: AtlasItem[]
}
