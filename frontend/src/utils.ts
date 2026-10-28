export function money(value: number | null | undefined, maximumFractionDigits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits,
  }).format(value)
}

export function number(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value)
}

export function percent(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return 'No refresh recorded'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? '—' : `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}
