import type { HistoryRecord } from '../api/types'
import { money } from '../utils'

interface Props {
  records: HistoryRecord[]
  loading: boolean
}

export function PriceChart({ records, loading }: Props) {
  const chronological = [...records].reverse()
  const prices = chronological.map((item) => item.price_usd)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const spread = max - min || 1
  const points = prices
    .map((price, index) => {
      const x = chronological.length < 2 ? 50 : 8 + (index / (chronological.length - 1)) * 284
      const y = 112 - ((price - min) / spread) * 88
      return `${x},${y}`
    })
    .join(' ')

  return (
    <div className="chart-wrap" aria-label="Historical price chart">
      {loading ? <div className="chart-empty">Loading price history…</div> : null}
      {!loading && chronological.length === 0 ? (
        <div className="chart-empty">No saved price history yet. Refresh market data to start a series.</div>
      ) : null}
      {!loading && chronological.length > 0 ? (
        <>
          <svg className="chart" viewBox="0 0 300 130" role="img" aria-label={`${chronological.length} historical prices`}>
            <defs>
              <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#42d6ba" stopOpacity=".25" />
                <stop offset="100%" stopColor="#42d6ba" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[24, 68, 112].map((y) => <line key={y} x1="0" x2="300" y1={y} y2={y} className="chart-grid" />)}
            {chronological.length > 1 ? <polygon points={`8,130 ${points} 292,130`} fill="url(#chart-fill)" /> : null}
            <polyline points={points} className="chart-line" />
          </svg>
          <div className="chart-labels"><span>{money(prices[0])}</span><span>{money(prices[prices.length - 1])}</span></div>
        </>
      ) : null}
    </div>
  )
}
