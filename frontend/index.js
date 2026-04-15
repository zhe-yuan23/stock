const DEFAULT_API_BASE = "";
// const DEFAULT_API_BASE = "http://localhost:8000";
const API_KEY = "apiBase";

function getApiBase() {
  return localStorage.getItem(API_KEY) || DEFAULT_API_BASE;
}

function $(id) { return document.getElementById(id); }

// ── Trading Hours (Taiwan time, Mon–Fri 09:00 ~ next day 08:00) ──
function isTradingHours() {
  const param = new URLSearchParams(window.location.search).get('live');
  if (param === '1') return true;
  if (param === '0') return false;
  const now = new Date();
  const tw = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  const day = tw.getDay();
  const minutes = tw.getHours() * 60 + tw.getMinutes();
  // 週一～五 09:00 以後，或 週二～六 08:00 以前（即前一個交易日收盤後到隔天更新前）
  const isTradingDay = day >= 1 && day <= 5;
  const isNextMorning = day >= 2 && day <= 6 && minutes < 8 * 60;
  return (isTradingDay && minutes >= 9 * 60) || isNextMorning;
}

// ── Fetch live price via backend proxy ──
async function fetchLivePrice(stockId) {
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/api/live-price/${encodeURIComponent(stockId)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data?.price ?? null;
  } catch {
    return null;
  }
}

// ── Fetch all live prices in one request ──
async function fetchAllLivePrices(stockIds) {
  try {
    const apiBase = getApiBase();
    const ids = stockIds.join(',');
    const res = await fetch(`${apiBase}/api/live-prices?ids=${encodeURIComponent(ids)}`);
    if (!res.ok) return {};
    const data = await res.json();
    return data?.prices ?? {};
  } catch {
    return {};
  }
}

// ── Clock ──
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  $('clock').textContent = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Formatters ──
function fmt(v, d = 2) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(d) : '—';
}

function fmtAchieve(v) {
  if (v === null || v === undefined) return '尚未公布';
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '尚未公布';
}

function achieveClass(rate) {
  if (rate === null || rate === undefined) return 'gray';
  const v = Number(rate);
  if (!Number.isFinite(v)) return 'gray';
  if (v >= 100) return 'green';
  if (v >= 70) return 'orange';
  return 'blue';
}

function cardBgClass(vol) {
  if (vol === null || vol === undefined) return 'bg-none';
  const v = Number(vol);
  if (!Number.isFinite(v)) return 'bg-none';
  return v >= 100 ? 'bg-red' : 'bg-green';
}

// ── State ──
let allItems = [];
let currentSort = 'achieve';
let lastLivePrices = {};

function sortBy(key) {
  currentSort = key;
  ['sortAchieve', 'sortPrice', 'sortVolatility'].forEach(id => $( id) && $( id).classList.remove('active'));
  const btnMap = { achieve: 'sortAchieve', price: 'sortPrice', vol: 'sortVolatility' };
  if ($(btnMap[key])) $(btnMap[key]).classList.add('active');

  const sorted = [...allItems].sort((a, b) => {
    if (key === 'achieve') {
      const av = a.revenue_achieve_rate ?? -1;
      const bv = b.revenue_achieve_rate ?? -1;
      return bv - av;
    }
    if (key === 'price') {
      const av = a.current_price ?? -1;
      const bv = b.current_price ?? -1;
      return bv - av;
    }
    if (key === 'vol') {
      const av = a.price_volatility ?? -1;
      const bv = b.price_volatility ?? -1;
      return bv - av; // higher volatility = expensive = at first
    }
    return 0;
  });
  renderCards(sorted);

  // Re-apply live prices if available
  if (isTradingHours() && Object.keys(lastLivePrices).length > 0) {
    applyLivePricesToCards(lastLivePrices, allItems);
  }
}

// ── Stats bar ──
function renderStats(items) {
  const total = items.length;
  const high = items.filter(i => (i.revenue_achieve_rate ?? 0) >= 70).length;
  const full = items.filter(i => (i.revenue_achieve_rate ?? 0) >= 100).length;
  const cheap = items.filter(i => i.price_volatility !== null && Number(i.price_volatility) < 100).length;
  const exp = items.filter(i => i.price_volatility !== null && Number(i.price_volatility) >= 100).length;

  $('statTotal').textContent = total;
  $('statHigh').textContent = high;
  $('statFull').textContent = full;
  $('statCheap').textContent = cheap;
  $('statExp').textContent = exp;
  $('statsBar').style.display = 'flex';
}

// ── Card builder ──
function buildCard(item, index) {
  const rate = item.revenue_achieve_rate;
  const vol = item.price_volatility;
  const priceDisplay = item.current_price !== null && item.current_price !== undefined
    ? `${fmt(item.current_price, 2)}<span class="price-unit">元</span>`
    : '—';
  const volDisplay = vol !== null && vol !== undefined ? `${fmt(vol, 2)} %` : '—';
  const monthText = item.update_month ? `更新至 ${item.update_month}` : '尚未公布';
  const statusClass = item.is_latest ? 'latest' : 'pending';
  const statusText = item.is_latest ? '▲ 最新月份' : '◌ 待更新';

  // ── Band gauge bar ──
  const low   = item.band_low;
  const mid   = item.band_mid;
  const high  = item.band_high;
  const price = item.current_price;
  const vol_num = vol !== null && vol !== undefined ? Number(vol) : null;
  let bandBarHtml = '';

  if (low != null && mid != null && high != null && price != null) {
    // Full band data available
    const range = high - low || 1;
    const pct = Math.min(100, Math.max(0, ((price - low) / range) * 100));
    let zoneColor = 'var(--muted)';
    if (price <= mid)       zoneColor = 'var(--green)';
    else if (price <= high) zoneColor = 'var(--orange)';
    else                    zoneColor = 'var(--red)';
    bandBarHtml = `
      <div class="band-bar-wrap" title="低 ${fmt(low,1)} ／ 中 ${fmt(mid,1)} ／ 高 ${fmt(high,1)}">
        <div class="band-bar-track">
          <div class="band-bar-mid" style="left:50%"></div>
          <div class="band-bar-marker" style="left:${pct}%;background:${zoneColor};box-shadow:0 0 5px ${zoneColor};"></div>
        </div>
      </div>`;
  } else if (vol_num !== null) {
    // Fallback: use price_volatility (100% = fair price midpoint, range 50–150%)
    const pct = Math.min(100, Math.max(0, ((vol_num - 50) / 100) * 100));
    let zoneColor = 'var(--muted)';
    if (vol_num < 100)       zoneColor = 'var(--green)';
    else if (vol_num < 120)  zoneColor = 'var(--orange)';
    else                     zoneColor = 'var(--red)';
    bandBarHtml = `
      <div class="band-bar-wrap" title="波動位階 ${fmt(vol_num,1)}%（基本面估價=100%）">
        <div class="band-bar-track">
          <div class="band-bar-mid" style="left:50%"></div>
          <div class="band-bar-marker" style="left:${pct}%;background:${zoneColor};box-shadow:0 0 5px ${zoneColor};"></div>
        </div>
      </div>`;
  }

  const card = document.createElement('div');
  card.className = `card ${cardBgClass(vol)}`;
  card.style.animationDelay = `${index * 40}ms`;
  card.dataset.stockId = item.stock_id;

  card.innerHTML = `
    <div class="card-accent-bar"></div>
    <div class="card-body">
      <div class="card-left">
        <div class="stock-code">${item.stock_id}</div>
        <div class="stock-name">${item.company_name_short || '未知'}</div>
        <div class="achieve-label">YTD 達成率</div>
        <div class="achieve-value ${achieveClass(rate)}">${fmtAchieve(rate)}</div>
        <div class="card-meta">
          <div class="meta-row">${monthText}</div>
          <div class="meta-row ${statusClass}">${statusText}</div>
        </div>
      </div>
      <div class="card-right">
        <div>
          <div class="price-label">LAST PRICE</div>
          <div class="price-value card-price-value">${priceDisplay}</div>
        </div>
        <div class="volatility-wrap">
          <div class="volatility-label">波動位階</div>
          <div class="volatility-value card-vol-value">${volDisplay}</div>
        </div>
        ${bandBarHtml}
      </div>
    </div>
  `;

  card.addEventListener('click', () => {
    window.location.href = `stock.html?stock_id=${encodeURIComponent(item.stock_id)}`;
  });

  return card;
}

// ── Render ──
function renderCards(items) {
  const grid = $('grid');
  grid.innerHTML = '';
  if (!items.length) {
    grid.innerHTML = '<div style="color:var(--muted);font-family:var(--mono);font-size:12px;padding:20px;">NO DATA AVAILABLE</div>';
    return;
  }
  items.forEach((item, i) => grid.appendChild(buildCard(item, i)));
}

// ── Fetch ──
async function loadSummary() {
  const apiBase = getApiBase();
  $('loading').style.display = 'flex';
  $('grid').innerHTML = '';

  try {
    const res = await fetch(`${apiBase}/api/stocks/summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const year = data.global_target_year;
    $('targetYear').textContent = year || '----';
    $('subLabel').textContent = year
      ? `${year} ANNUAL REVENUE ACHIEVEMENT TRACKER`
      : 'NO DATA';

    allItems = data.items || [];
    if (!allItems.length) {
      $('loading').innerHTML = '<div class="loading-text">NO DATA AVAILABLE</div>';
      return;
    }

    renderStats(allItems);
    sortBy('achieve');
    $('loading').style.display = 'none';

    // ── Live price overlay (trading hours only) ──
    if (isTradingHours()) {
      const stockIds = allItems.map(i => i.stock_id);
      const livePrices = await fetchAllLivePrices(stockIds);
      lastLivePrices = livePrices;
      applyLivePricesToCards(livePrices, allItems);
    }

  } catch (err) {
    console.error(err);
    $('loading').innerHTML = `<div class="loading-text" style="color:var(--red);">ERROR: ${err?.message || err}</div>`;
  }
}

loadSummary();

// ── Auto update every 30 min during 09:00–14:00 ──
function isAutoUpdateHours() {
  const now = new Date();
  const tw = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  const day = tw.getDay();
  if (day === 0 || day === 6) return false;
  const minutes = tw.getHours() * 60 + tw.getMinutes();
  return minutes >= 9 * 60 && minutes < 14 * 60;
}

setInterval(async () => {
  if (!isAutoUpdateHours()) return;
  const stockIds = allItems.map(i => i.stock_id);
  const livePrices = await fetchAllLivePrices(stockIds);
  lastLivePrices = livePrices;
  applyLivePricesToCards(livePrices, allItems);
}, 30 * 60 * 1000);

// ── Pull to Refresh ──
(function initPullToRefresh() {
  const THRESHOLD = 80;
  let startY = 0;
  let pulling = false;
  const indicator = document.getElementById('pullIndicator');

  document.addEventListener('touchstart', e => {
    if (window.scrollY === 0) {
      startY = e.touches[0].clientY;
      pulling = true;
    }
  }, { passive: true });

  document.addEventListener('touchmove', e => {
    if (!pulling) return;
    const dist = Math.min(e.touches[0].clientY - startY, THRESHOLD * 1.5);
    if (dist <= 0) return;
    indicator.style.height = `${Math.min(dist * 0.5, 44)}px`;
    if (dist >= THRESHOLD) {
      indicator.textContent = '↑ 放開更新';
      indicator.classList.add('ready');
    } else {
      indicator.textContent = '↓ 下拉更新價格';
      indicator.classList.remove('ready');
    }
  }, { passive: true });

  document.addEventListener('touchend', async e => {
    if (!pulling) return;
    pulling = false;
    const dist = e.changedTouches[0].clientY - startY;
    indicator.style.height = '0';
    indicator.classList.remove('ready');
    indicator.textContent = '↓ 下拉更新價格';
    if (dist >= THRESHOLD && isTradingHours()) {
      indicator.style.height = '44px';
      indicator.textContent = '更新中...';
      const stockIds = allItems.map(i => i.stock_id);
      const livePrices = await fetchAllLivePrices(stockIds);
      lastLivePrices = livePrices;
      applyLivePricesToCards(livePrices, allItems);
      indicator.style.height = '0';
    }
  }, { passive: true });
})();
function applyLivePricesToCards(livePrices, items) {
  document.querySelectorAll('.card[data-stock-id]').forEach(card => {
    const stockId = card.dataset.stockId;
    const livePrice = livePrices[stockId];
    if (livePrice == null) return;

    // Update price label to LIVE PRICE
    const priceLabel = card.querySelector('.price-label');
    if (priceLabel) priceLabel.textContent = 'LIVE PRICE';

    // Update price display
    const priceEl = card.querySelector('.card-price-value');
    if (priceEl) {
      priceEl.innerHTML = `${fmt(livePrice, 2)}<span class="price-unit">元</span>`;
    }

    // Update volatility value and band bar if est_fair_price exists
    const item = items.find(i => i.stock_id === stockId);
    if (!item) return;

    // Recalculate price_volatility with live price
    const fairPrice = item.est_fair_price;
    if (fairPrice) {
      const newVol = (livePrice / fairPrice) * 100;
      const volEl = card.querySelector('.card-vol-value');
      if (volEl) volEl.textContent = `${fmt(newVol, 2)} %`;
    }

    // Update band bar marker position
    const low = item.band_low, mid = item.band_mid, high = item.band_high;
    const marker = card.querySelector('.band-bar-marker');
    if (marker && low != null && mid != null && high != null) {
      const range = high - low || 1;
      const pct = Math.min(100, Math.max(0, ((livePrice - low) / range) * 100));
      let zoneColor = 'var(--muted)';
      if (livePrice <= mid)       zoneColor = 'var(--green)';
      else if (livePrice <= high) zoneColor = 'var(--orange)';
      else                        zoneColor = 'var(--red)';
      marker.style.left = `${pct}%`;
      marker.style.background = zoneColor;
      marker.style.boxShadow = `0 0 5px ${zoneColor}`;
    }
  });
}

// ── Taiex Banner ──
async function loadTaiex() {
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/api/taiex`);
    if (!res.ok) return;
    const data = await res.json();
 
    const { current_close, all_time_high, drawdown_pct, date, is_drawdown_alert } = data;
 
    $('taiexClose').textContent = current_close.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
 
    const drawdownEl = $('taiexDrawdown');
    const sign = drawdown_pct >= 0 ? '+' : '';
    drawdownEl.textContent = `${sign}${drawdown_pct.toFixed(2)}% from ATH`;
 
    if (drawdown_pct >= -5)        drawdownEl.className = 'taiex-drawdown safe';
    else if (drawdown_pct >= -10)  drawdownEl.className = 'taiex-drawdown warn';
    else                           drawdownEl.className = 'taiex-drawdown alert';
 
    $('taiexAth').textContent = `ATH ${all_time_high.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    $('taiexDate').textContent = date;
 
    if (is_drawdown_alert) {
      $('taiexAlertBadge').classList.add('visible');
    }
 
    $('taiexBanner').style.display = 'flex';
  } catch {
    // 靜默失敗，不影響主頁面
  }
}
 
loadTaiex();