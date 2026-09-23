export function createShipIcon(fill: string, glow = false, size = 64): ImageData {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return new ImageData(size, size)
  }

  ctx.translate(size / 2, size / 2)
  if (glow) {
    ctx.shadowColor = fill
    ctx.shadowBlur = 14
  }

  ctx.beginPath()
  ctx.moveTo(0, -size * 0.38)
  ctx.lineTo(size * 0.22, size * 0.34)
  ctx.lineTo(0, size * 0.2)
  ctx.lineTo(-size * 0.22, size * 0.34)
  ctx.closePath()
  ctx.fillStyle = fill
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = '#041018'
  ctx.stroke()

  return ctx.getImageData(0, 0, size, size)
}

export interface BaseMapConfig {
  style: string
  clusterFont: string[]
}

export function getBaseMap(): BaseMapConfig {
  const key = import.meta.env.VITE_MAPTILER_API_KEY?.trim()
  if (key) {
    return {
      style: `https://api.maptiler.com/maps/dataviz-dark/style.json?key=${encodeURIComponent(key)}`,
      clusterFont: ['Open Sans Regular'],
    }
  }

  // OSM-based dark vector tiles, no API key required.
  return {
    style: 'https://tiles.openfreemap.org/styles/dark',
    clusterFont: ['Noto Sans Regular'],
  }
}
