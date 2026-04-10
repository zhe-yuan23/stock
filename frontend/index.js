// const DEFAULT_API_BASE = "";
const DEFAULT_API_BASE = "http://localhost:8000";
const API_KEY = "apiBase";

function getApiBase() {
  return localStorage.getItem(API_KEY) || DEFAULT_API_BASE;
}

function $(id) { return document.getElementById(id); }

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
          <div class="price-value">${priceDisplay}</div>
        </div>
        <div class="volatility-wrap">
          <div class="volatility-label">波動位階</div>
          <div class="volatility-value">${volDisplay}</div>
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

  } catch (err) {
    console.error(err);
    $('loading').innerHTML = `<div class="loading-text" style="color:var(--red);">ERROR: ${err?.message || err}</div>`;
  }
}

loadSummary();
