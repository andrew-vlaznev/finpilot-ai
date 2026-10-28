import type {
  CreatePositionRequest,
  HistoryResponse,
  IndicatorResponse,
  MarketResponse,
  MarketStatus,
  PortfolioPosition,
  PortfolioSummary,
  RefreshResponse,
  SignalsResponse,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('Cannot reach the FinPilot API. Check that the backend is running.')
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch {
      // Keep the HTTP status message when the server did not return JSON.
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  getMarket: () => request<MarketResponse>('/market'),
  getMarketStatus: () => request<MarketStatus>('/market/status'),
  getSignals: () => request<SignalsResponse>('/market/signals'),
  getIndicators: (symbol: string) =>
    request<IndicatorResponse>(`/market/indicators?symbol=${encodeURIComponent(symbol)}&limit=100`),
  getHistory: (symbol: string) =>
    request<HistoryResponse>(`/market/history/${encodeURIComponent(symbol)}?limit=100`),
  refreshMarket: () => request<RefreshResponse>('/market/refresh', { method: 'POST' }),
  getPortfolio: () => request<PortfolioSummary>('/portfolio'),
  addPosition: (position: CreatePositionRequest) =>
    request<PortfolioPosition>('/portfolio/positions', {
      method: 'POST',
      body: JSON.stringify(position),
    }),
  getPosition: (positionId: number) =>
    request<PortfolioPosition>(`/portfolio/positions/${positionId}`),
  deletePosition: (positionId: number) =>
    request<void>(`/portfolio/positions/${positionId}`, { method: 'DELETE' }),
}
