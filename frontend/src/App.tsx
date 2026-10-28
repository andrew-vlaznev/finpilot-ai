import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from './api/client'
import { ASSETS, type AssetSymbol, type HistoryRecord, type IndicatorResponse, type MarketResponse, type MarketSignal, type MarketStatus, type PortfolioPosition, type PortfolioSummary, type SignalsResponse } from './api/types'
import { PriceChart } from './components/PriceChart'
import { dateTime, money, number, percent } from './utils'

type Page = 'dashboard' | 'portfolio'
type Result<T> = { data: T | null; error: string | null; loading: boolean }

const initial = <T,>(): Result<T> => ({ data: null, error: null, loading: true })

function message(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
}

function MetricCard({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: string }) {
  return <article className="metric-card"><span className="metric-label">{label}</span><strong className={accent ?? ''}>{value}</strong>{note ? <small>{note}</small> : null}</article>
}

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [market, setMarket] = useState(initial<MarketResponse>())
  const [portfolio, setPortfolio] = useState(initial<PortfolioSummary>())
  const [status, setStatus] = useState(initial<MarketStatus>())
  const [signals, setSignals] = useState(initial<SignalsResponse>())
  const [symbol, setSymbol] = useState<AssetSymbol>('BTC')
  const [indicators, setIndicators] = useState(initial<IndicatorResponse>())
  const [history, setHistory] = useState(initial<HistoryRecord[]>())
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [positionDetail, setPositionDetail] = useState<PortfolioPosition | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadDashboard = useCallback(async (includeMarket = true) => {
    if (includeMarket) setMarket((state) => ({ ...state, loading: true, error: null }))
    setPortfolio((state) => ({ ...state, loading: true, error: null }))
    setStatus((state) => ({ ...state, loading: true, error: null }))
    setSignals((state) => ({ ...state, loading: true, error: null }))
    const jobs = [
      ...(includeMarket ? [api.getMarket().then((data) => setMarket({ data, error: null, loading: false })).catch((error) => setMarket((state) => ({ ...state, error: message(error), loading: false })))] : []),
      api.getPortfolio().then((data) => setPortfolio({ data, error: null, loading: false })).catch((error) => setPortfolio((state) => ({ ...state, error: message(error), loading: false }))),
      api.getMarketStatus().then((data) => setStatus({ data, error: null, loading: false })).catch((error) => setStatus((state) => ({ ...state, error: message(error), loading: false }))),
      api.getSignals().then((data) => setSignals({ data, error: null, loading: false })).catch((error) => setSignals((state) => ({ ...state, error: message(error), loading: false }))),
    ]
    await Promise.all(jobs)
  }, [])

  const loadAssetData = useCallback(async () => {
    setIndicators((state) => ({ ...state, loading: true, error: null }))
    setHistory((state) => ({ ...state, loading: true, error: null }))
    const jobs = [
      api.getIndicators(symbol).then((data) => setIndicators({ data, error: null, loading: false })).catch((error) => setIndicators((state) => ({ ...state, error: message(error), loading: false }))),
      api.getHistory(symbol).then((data) => setHistory({ data: data.history, error: null, loading: false })).catch((error) => setHistory((state) => ({ ...state, error: message(error), loading: false }))),
    ]
    await Promise.all(jobs)
  }, [symbol])

  useEffect(() => { void loadDashboard() }, [loadDashboard])
  useEffect(() => { void loadAssetData() }, [loadAssetData])

  const reloadPortfolio = async () => {
    setPortfolio((state) => ({ ...state, loading: true, error: null }))
    try {
      const data = await api.getPortfolio()
      setPortfolio({ data, error: null, loading: false })
    } catch (error) {
      setPortfolio((state) => ({ ...state, error: message(error), loading: false }))
    }
  }

  const refreshMarket = async () => {
    setRefreshing(true)
    setRefreshError(null)
    setNotice(null)
    try {
      const refreshed = await api.refreshMarket()
      setMarket({
        data: { market: 'crypto', assets: refreshed.assets, source: 'CoinGecko', updated_at: refreshed.updated_at },
        error: null,
        loading: false,
      })
      setNotice('Market data refreshed and saved to history.')
      await Promise.all([loadDashboard(false), loadAssetData()])
    } catch (error) {
      setRefreshError(message(error))
    } finally {
      setRefreshing(false)
    }
  }

  const addPosition = async (input: { symbol: AssetSymbol; quantity: number; purchase_price: number }) => {
    await api.addPosition(input)
    setNotice(`${input.symbol} position added.`)
    await reloadPortfolio()
  }

  const deletePosition = async (positionId: number, asset: AssetSymbol) => {
    if (!window.confirm(`Remove this ${asset} position from your portfolio?`)) return
    try {
      await api.deletePosition(positionId)
      setNotice(`${asset} position removed.`)
      await reloadPortfolio()
    } catch (error) {
      setNotice(message(error))
    }
  }

  const viewPosition = async (positionId: number) => {
    setDetailLoading(true)
    try {
      setPositionDetail(await api.getPosition(positionId))
    } catch (error) {
      setNotice(message(error))
    } finally {
      setDetailLoading(false)
    }
  }

  const prices = new Map((market.data?.assets ?? []).map((asset) => [asset.symbol, asset.price]))
  const signalMap = new Map((signals.data?.signals ?? []).map((item) => [item.symbol, item]))

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#dashboard" onClick={() => setPage('dashboard')}><span className="brand-mark">F</span><span>FINPILOT<small>MARKET TERMINAL</small></span></a>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button className={`nav-item ${page === 'dashboard' ? 'active' : ''}`} onClick={() => setPage('dashboard')}><span>▦</span> Dashboard</button>
          <button className={`nav-item ${page === 'portfolio' ? 'active' : ''}`} onClick={() => setPage('portfolio')}><span>◫</span> Portfolio</button>
        </nav>
        <div className="sidebar-bottom"><div className="connection-dot" /> Local API <span className="api-url">127.0.0.1:8000</span></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb"><span>FINPILOT</span><b>/</b>{page === 'dashboard' ? 'Dashboard' : 'Portfolio'}</div>
          <div className="topbar-right"><span className="market-open"><i /> MARKET DATA</span><button className="icon-button" aria-label="Refresh market data" onClick={() => void refreshMarket()} disabled={refreshing}>{refreshing ? '◌' : '↻'}</button><span className="avatar">FP</span></div>
        </header>

        {notice ? <div className="toast" role="status">{notice}<button aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div> : null}
        {page === 'dashboard' ? (
          <section className="page-content">
            <div className="page-heading"><div><p className="eyebrow">YOUR FINANCIAL OVERVIEW</p><h1>Dashboard <span className="live-badge"><i /> LIVE</span></h1><p className="subheading">Market data and portfolio performance at a glance.</p></div><div className="heading-actions"><span className="updated">Updated {dateTime(status.data?.last_updated_at ?? market.data?.updated_at)}</span><button className="button button-primary" onClick={() => void refreshMarket()} disabled={refreshing}>{refreshing ? <><span className="spinner" /> Updating…</> : <><span>↻</span> Refresh market</>}</button></div></div>
            {refreshError ? <ErrorBanner text={refreshError} onRetry={() => void refreshMarket()} /> : null}
            <div className="metrics-grid">
              <MetricCard label="PORTFOLIO VALUE" value={portfolio.loading ? '…' : money(portfolio.data?.total_current_value)} note="At latest available prices" />
              <MetricCard label="TOTAL INVESTED" value={portfolio.loading ? '…' : money(portfolio.data?.total_purchase_value)} note="Across all positions" />
              <MetricCard label="TOTAL P&L" value={portfolio.loading ? '…' : money(portfolio.data?.total_profit_loss)} note={percent(portfolio.data?.total_profit_loss_percent)} accent={(portfolio.data?.total_profit_loss ?? 0) >= 0 ? 'positive' : 'negative'} />
              <MetricCard label="OPEN POSITIONS" value={portfolio.loading ? '…' : number(portfolio.data?.positions_count, 0)} note="Tracked assets" />
            </div>
            {portfolio.error ? <ErrorBanner text={portfolio.error} onRetry={() => void reloadPortfolio()} /> : null}

            <div className="section-heading"><div><p className="eyebrow">LIVE MARKET</p><h2>Digital assets</h2></div><span className="source-tag">◈ {market.data?.source ?? 'CoinGecko'}</span></div>
            {market.error ? <ErrorBanner text={market.error} onRetry={() => void loadDashboard()} /> : null}
            <div className="asset-grid">
              {ASSETS.map((asset) => <AssetCard key={asset} symbol={asset} price={prices.get(asset)} signal={signalMap.get(asset)} loading={market.loading || signals.loading} />)}
            </div>

            <div className="content-grid">
              <section className="panel chart-panel">
                <div className="panel-heading"><div><p className="eyebrow">PRICE HISTORY</p><h2>{symbol} / USD</h2></div><select aria-label="Chart asset" value={symbol} onChange={(event) => setSymbol(event.target.value as AssetSymbol)}>{ASSETS.map((asset) => <option key={asset}>{asset}</option>)}</select></div>
                <PriceChart records={history.data ?? []} loading={history.loading} />
                {history.error ? <ErrorInline text={history.error} onRetry={() => void loadAssetData()} /> : null}
                <div className="chart-foot"><span>Saved observations · latest 100</span><span>{history.data?.length ?? 0} records</span></div>
              </section>
              <section className="panel indicators-panel">
                <div className="panel-heading"><div><p className="eyebrow">TECHNICAL SNAPSHOT</p><h2>Indicators <span className="muted">{symbol}</span></h2></div><span className="live-dot" /></div>
                {indicators.error ? <ErrorInline text={indicators.error} onRetry={() => void loadAssetData()} /> : null}
                <div className="indicator-row"><div><span>SMA</span><small>Simple moving average</small></div><strong>{indicators.loading ? '…' : money(indicators.data?.sma)}</strong></div>
                <div className="indicator-row"><div><span>RSI</span><small>Wilder · {indicators.data?.rsi_period ?? 14} period</small></div><strong className={indicators.data?.rsi != null && indicators.data.rsi >= 70 ? 'negative' : indicators.data?.rsi != null && indicators.data.rsi <= 30 ? 'positive' : ''}>{indicators.loading ? '…' : number(indicators.data?.rsi)}</strong></div>
                <div className="indicator-note">Calculated from {indicators.data?.records_analyzed ?? 0} saved observations.</div>
              </section>
            </div>

            <section className="panel signals-panel">
              <div className="panel-heading"><div><p className="eyebrow">HISTORICAL PRICE MOVEMENT</p><h2>Market signals</h2></div><span className="educational-tag">EDUCATIONAL</span></div>
              {signals.error ? <ErrorInline text={signals.error} onRetry={() => void loadDashboard()} /> : null}
              <div className="signal-table-wrap"><table><thead><tr><th>ASSET</th><th>SIGNAL</th><th>CHANGE</th><th>WINDOW</th><th className="align-right">OBSERVATIONS</th></tr></thead><tbody>{ASSETS.map((asset) => <SignalRow key={asset} signal={signalMap.get(asset)} loading={signals.loading} />)}</tbody></table></div>
              <div className="disclaimer">Signals reflect historical change only. They are educational and are not investment advice.</div>
            </section>

            <section className="assistant-card"><div className="assistant-icon">✳</div><div><span className="eyebrow">ON THE ROADMAP</span><h3>AI Assistant</h3><p>Portfolio insights and conversational market analysis are planned for a future release.</p></div><span className="coming-soon">COMING SOON</span></section>
            <footer className="page-footer">FINPILOT AI <span>·</span> Educational market analytics <span>·</span> Data from CoinGecko</footer>
          </section>
        ) : (
          <PortfolioPage result={portfolio} onRetry={() => void reloadPortfolio()} onAdd={addPosition} onDelete={deletePosition} onView={viewPosition} />
        )}
        {detailLoading ? <div className="modal-backdrop"><div className="position-modal">Loading position…</div></div> : null}
        {positionDetail ? <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPositionDetail(null) }}><section className="position-modal" role="dialog" aria-modal="true" aria-labelledby="position-detail-title"><button className="modal-close" aria-label="Close position details" onClick={() => setPositionDetail(null)}>×</button><p className="eyebrow">POSITION DETAILS</p><h2 id="position-detail-title">{positionDetail.symbol} holding</h2><dl><div><dt>Quantity</dt><dd>{number(positionDetail.quantity, 8)}</dd></div><div><dt>Purchase price</dt><dd>{money(positionDetail.purchase_price)}</dd></div><div><dt>Opened</dt><dd>{dateTime(positionDetail.created_at)}</dd></div></dl></section></div> : null}
      </main>
    </div>
  )
}

function AssetCard({ symbol, price, signal, loading }: { symbol: AssetSymbol; price?: number; signal?: MarketSignal; loading: boolean }) {
  return <article className="asset-card"><div className="asset-top"><span className={`coin-icon coin-${symbol.toLowerCase()}`}>{symbol.slice(0, 1)}</span><div><strong>{symbol}</strong><small>{assetNames[symbol]}</small></div><span className="asset-arrow">↗</span></div><div className="asset-price">{loading && price == null ? '…' : money(price, price != null && price < 1 ? 4 : 2)}</div><div className="asset-bottom"><span className="muted">USD spot</span><SignalBadge value={signal?.signal} compact /></div></article>
}

const assetNames: Record<AssetSymbol, string> = { BTC: 'Bitcoin', ETH: 'Ethereum', SOL: 'Solana', DOGE: 'Dogecoin' }

function SignalBadge({ value, compact = false }: { value?: MarketSignal['signal']; compact?: boolean }) {
  return <span className={`signal-badge ${value?.toLowerCase() ?? 'unknown'} ${compact ? 'compact' : ''}`}>{value ?? '—'}</span>
}

function SignalRow({ signal, loading }: { signal?: MarketSignal; loading: boolean }) {
  if (!signal) return <tr><td colSpan={5} className="empty-cell">{loading ? 'Loading signals…' : 'No signal data available.'}</td></tr>
  return <tr><td><span className={`coin-icon small coin-${signal.symbol.toLowerCase()}`}>{signal.symbol.slice(0, 1)}</span><strong>{signal.symbol}</strong><small className="table-sub">{assetNames[signal.symbol]}</small></td><td><SignalBadge value={signal.signal} /></td><td className={signal.change_percent != null && signal.change_percent >= 0 ? 'positive' : signal.change_percent != null ? 'negative' : 'muted'}>{percent(signal.change_percent)}</td><td>{signal.first_price != null && signal.last_price != null ? `${money(signal.first_price)} → ${money(signal.last_price)}` : '—'}</td><td className="align-right">{signal.records_analyzed}</td></tr>
}

function ErrorBanner({ text, onRetry }: { text: string; onRetry: () => void }) {
  return <div className="error-banner" role="alert"><span>!</span><div><strong>Unable to load data</strong><p>{text}</p></div><button className="button button-secondary" onClick={onRetry}>Try again</button></div>
}

function ErrorInline({ text, onRetry }: { text: string; onRetry: () => void }) {
  return <div className="error-inline" role="alert">{text}<button onClick={onRetry}>Retry</button></div>
}

function PortfolioPage({ result, onRetry, onAdd, onDelete, onView }: { result: Result<PortfolioSummary>; onRetry: () => void; onAdd: (input: { symbol: AssetSymbol; quantity: number; purchase_price: number }) => Promise<void>; onDelete: (id: number, asset: AssetSymbol) => Promise<void>; onView: (id: number) => Promise<void> }) {
  const [asset, setAsset] = useState<AssetSymbol>('BTC')
  const [quantity, setQuantity] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const quantityValue = Number(quantity)
    const priceValue = Number(purchasePrice)
    if (!Number.isFinite(quantityValue) || quantityValue <= 0 || !Number.isFinite(priceValue) || priceValue <= 0) {
      setFormError('Enter a quantity and purchase price greater than zero.')
      return
    }
    setFormError(null)
    setSubmitting(true)
    try {
      await onAdd({ symbol: asset, quantity: quantityValue, purchase_price: priceValue })
      setQuantity('')
      setPurchasePrice('')
    } catch (error) {
      setFormError(message(error))
    } finally {
      setSubmitting(false)
    }
  }

  const summary = result.data
  return <section className="page-content portfolio-page">
    <div className="page-heading"><div><p className="eyebrow">YOUR HOLDINGS</p><h1>Portfolio</h1><p className="subheading">Track your positions and their current market value.</p></div><span className="updated">{summary?.positions_count ?? 0} positions</span></div>
    {result.error ? <ErrorBanner text={result.error} onRetry={onRetry} /> : null}
    <div className="metrics-grid portfolio-metrics"><MetricCard label="CURRENT VALUE" value={result.loading ? '…' : money(summary?.total_current_value)} note="Based on available quotes" /><MetricCard label="TOTAL INVESTED" value={result.loading ? '…' : money(summary?.total_purchase_value)} note="Cost basis" /><MetricCard label="UNREALIZED P&L" value={result.loading ? '…' : money(summary?.total_profit_loss)} note={percent(summary?.total_profit_loss_percent)} accent={(summary?.total_profit_loss ?? 0) >= 0 ? 'positive' : 'negative'} /><MetricCard label="POSITIONS" value={result.loading ? '…' : number(summary?.positions_count, 0)} note="Across supported assets" /></div>
    <div className="portfolio-layout">
      <section className="panel positions-panel"><div className="panel-heading"><div><p className="eyebrow">HOLDINGS</p><h2>Your positions</h2></div><span className="count-pill">{summary?.positions.length ?? 0}</span></div>
        {result.loading && !summary ? <div className="empty-state"><span className="spinner dark" /> Loading portfolio…</div> : null}
        {!result.loading && summary?.positions.length === 0 ? <div className="empty-state"><span className="empty-icon">◫</span><strong>No positions yet</strong><span>Add your first holding with the form.</span></div> : null}
        {summary && summary.positions.length > 0 ? <div className="signal-table-wrap"><table className="positions-table"><thead><tr><th>ASSET</th><th>QUANTITY</th><th>AVG. BUY PRICE</th><th>CURRENT VALUE</th><th>P&L</th><th></th></tr></thead><tbody>{summary.positions.map((position) => <tr key={position.id}><td><span className={`coin-icon small coin-${position.symbol.toLowerCase()}`}>{position.symbol.slice(0, 1)}</span><strong>{position.symbol}</strong><small className="table-sub">{assetNames[position.symbol]}</small></td><td>{number(position.quantity, 8)}</td><td>{money(position.purchase_price)}</td><td>{money(position.current_value)}</td><td className={position.profit_loss == null ? 'muted' : position.profit_loss >= 0 ? 'positive' : 'negative'}>{position.profit_loss == null ? '—' : <>{money(position.profit_loss)}<small className="table-sub">{percent(position.profit_loss_percent)}</small></>}</td><td><div className="row-actions"><button className="view-button" aria-label={`View ${position.symbol} position`} onClick={() => void onView(position.id)}>View</button><button className="delete-button" aria-label={`Remove ${position.symbol} position`} onClick={() => void onDelete(position.id, position.symbol)}>×</button></div></td></tr>)}</tbody></table></div> : null}
      </section>
      <section className="panel add-panel"><div className="panel-heading"><div><p className="eyebrow">NEW HOLDING</p><h2>Add a position</h2></div><span className="add-symbol">＋</span></div><form onSubmit={submit} noValidate>
        <label htmlFor="asset">Asset</label><select id="asset" value={asset} onChange={(event) => setAsset(event.target.value as AssetSymbol)}>{ASSETS.map((item) => <option key={item} value={item}>{item} · {assetNames[item]}</option>)}</select>
        <label htmlFor="quantity">Quantity</label><input id="quantity" type="number" min="0" step="any" placeholder="0.00" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
        <label htmlFor="purchase-price">Purchase price (USD)</label><div className="input-prefix"><span>$</span><input id="purchase-price" type="number" min="0" step="any" placeholder="0.00" value={purchasePrice} onChange={(event) => setPurchasePrice(event.target.value)} /></div>
        {formError ? <p className="form-error" role="alert">{formError}</p> : null}
        <button className="button button-primary submit-button" type="submit" disabled={submitting}>{submitting ? 'Adding…' : 'Add position'}</button><small className="form-footnote">Quantity and purchase price must be greater than zero.</small>
      </form></section>
    </div>
    <div className="portfolio-note">Portfolio tracking is for informational and educational purposes only. It does not execute trades.</div>
  </section>
}

export default App
