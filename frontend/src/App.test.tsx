import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api, ApiError } from './api/client'

vi.mock('./api/client', () => ({
  ApiError: class ApiError extends Error {},
  api: {
    getMarket: vi.fn(),
    getPortfolio: vi.fn(),
    getMarketStatus: vi.fn(),
    getSignals: vi.fn(),
    getIndicators: vi.fn(),
    getHistory: vi.fn(),
    refreshMarket: vi.fn(),
    addPosition: vi.fn(),
    getPosition: vi.fn(),
    deletePosition: vi.fn(),
  },
}))

const emptyPortfolio = {
  positions: [],
  total_purchase_value: 0,
  total_current_value: 0,
  total_profit_loss: 0,
  total_profit_loss_percent: null,
  positions_count: 0,
  generated_at: '2026-10-23T10:00:00+00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getMarket).mockResolvedValue({ market: 'crypto', source: 'CoinGecko', updated_at: '2026-10-23T10:00:00+00:00', assets: [
    { symbol: 'BTC', price: 65000 }, { symbol: 'ETH', price: 3200 }, { symbol: 'SOL', price: 150 }, { symbol: 'DOGE', price: 0.2 },
  ] })
  vi.mocked(api.getPortfolio).mockResolvedValue(emptyPortfolio)
  vi.mocked(api.getMarketStatus).mockResolvedValue({ last_updated_at: '2026-10-23T10:00:00+00:00', history_records: 4 })
  vi.mocked(api.getSignals).mockResolvedValue({ limit: 100, threshold_percent: 3, generated_at: '2026-10-23T10:00:00+00:00', signals: [] })
  vi.mocked(api.getIndicators).mockResolvedValue({ symbol: 'BTC', records_analyzed: 0, sma: null, rsi: null, rsi_period: 14, updated_at: '2026-10-23T10:00:00+00:00' })
  vi.mocked(api.getHistory).mockResolvedValue({ symbol: 'BTC', history: [] })
  vi.mocked(api.addPosition).mockResolvedValue({ id: 1, symbol: 'BTC', quantity: 1, purchase_price: 100, created_at: '2026-10-23T10:00:00+00:00' })
})

describe('FinPilot dashboard', () => {
  it('renders market dashboard from the API', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
    expect(await screen.findByText('$65,000.00')).toBeInTheDocument()
    expect(screen.getByText('Digital assets')).toBeInTheDocument()
    expect(api.getMarket).toHaveBeenCalled()
  })

  it('shows an API failure and retry action', async () => {
    vi.mocked(api.getMarket).mockRejectedValueOnce(new ApiError('Backend unavailable'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows an empty portfolio state', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(within(screen.getByRole('navigation')).getByRole('button', { name: /Portfolio/ }))
    expect(await screen.findByText('No positions yet')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Your positions' })).toBeInTheDocument()
  })

  it('validates position form values before submitting', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(within(screen.getByRole('navigation')).getByRole('button', { name: /Portfolio/ }))
    const form = await screen.findByRole('heading', { name: 'Add a position' })
    expect(form).toBeInTheDocument()
    await user.type(screen.getByLabelText('Quantity'), '-1')
    await user.type(screen.getByLabelText('Purchase price (USD)'), '0')
    await user.click(screen.getByRole('button', { name: 'Add position' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('greater than zero')
    expect(api.addPosition).not.toHaveBeenCalled()
  })
})
