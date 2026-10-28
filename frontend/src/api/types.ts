export const ASSETS = ['BTC', 'ETH', 'SOL', 'DOGE'] as const
export type AssetSymbol = (typeof ASSETS)[number]

export interface MarketAsset {
  symbol: AssetSymbol
  price: number
}

export interface MarketResponse {
  market: string
  assets: MarketAsset[]
  source: string
  updated_at: string
}

export interface MarketStatus {
  last_updated_at: string | null
  history_records: number
}

export interface HistoryRecord {
  id: number
  symbol: AssetSymbol
  price_usd: number
  fetched_at: string
}

export interface HistoryResponse {
  symbol: AssetSymbol
  history: HistoryRecord[]
}

export interface MarketSignal {
  symbol: AssetSymbol
  signal: 'BUY' | 'SELL' | 'HOLD' | 'INSUFFICIENT_DATA'
  first_price: number | null
  last_price: number | null
  change_percent: number | null
  records_analyzed: number
}

export interface SignalsResponse {
  limit: number
  threshold_percent: number
  generated_at: string
  signals: MarketSignal[]
}

export interface IndicatorResponse {
  symbol: AssetSymbol
  records_analyzed: number
  sma: number | null
  rsi: number | null
  rsi_period: number
  updated_at: string
}

export interface PortfolioPosition {
  id: number
  symbol: AssetSymbol
  quantity: number
  purchase_price: number
  created_at: string
  purchase_value?: number
  current_price?: number | null
  current_value?: number | null
  profit_loss?: number | null
  profit_loss_percent?: number | null
}

export interface PortfolioSummary {
  positions: PortfolioPosition[]
  total_purchase_value: number
  total_current_value: number
  total_profit_loss: number
  total_profit_loss_percent: number | null
  positions_count: number
  generated_at: string
}

export interface CreatePositionRequest {
  symbol: AssetSymbol
  quantity: number
  purchase_price: number
}

export interface RefreshResponse {
  status: string
  assets: MarketAsset[]
  updated_at: string
}
