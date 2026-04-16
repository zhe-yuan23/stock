const DEFAULT_API_BASE = "";
// const DEFAULT_API_BASE = "http://localhost:8000";
const API_KEY = "apiBase";

function getApiBase() {
  return localStorage.getItem(API_KEY) || DEFAULT_API_BASE;
}

function $(id) { return document.getElementById(id); }

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

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

function fmtPct(v, d = 2) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toFixed(d)} %` : '—';
}

function metricCard(label, value, helpText = null) {
  const el = document.createElement('div');
  el.className = 'metric-card fade-in';
  el.innerHTML = `
    <div class="metric-label">${label}</div>
    <div class="metric-value">${value}</div>
    ${helpText ? `<div class="metric-help">${helpText}</div>` : ''}
  `;
  return el;
}

// ── Back button ──
$('backBtn').addEventListener('click', () => {
  window.location.href = 'index.html';
});

// ── Main loader ──
async function loadDetail() {
  const stockId = getQueryParam('stock_id');
  if (!stockId) {
    $('loading').innerHTML = '<div class="loading-text" style="color:var(--red);">MISSING STOCK_ID PARAMETER</div>';
    return;
  }

  $('headerStockId').textContent = stockId;
  document.title = `${stockId} - 台股追蹤`;

  const apiBase = getApiBase();

  try {
    const res = await fetch(`${apiBase}/api/stocks/${encodeURIComponent(stockId)}/detail`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const stockName = data.stock_name || stockId;
    const targetYear = data.target_year;

    $('headerStockId').textContent = stockId;
    $('headerStockName').textContent = stockName;

    // ── News（早點觸發，不等其他資料）──
    loadNews(stockId, stockName);

    // ── Hero strip ──
    const v = data.valuation;
    // 從資料中取得最新日期
    const latestDate = data.valuation?.latest_date || null;
    if (v) {
      const heroPrice = $('heroPrice');
      heroPrice.innerHTML = v.current_price !== null
        ? `${fmt(v.current_price, 2)}<span class="hero-price-unit"> 元</span>`
        : '—';
      $('heroPE').textContent = v.current_pe !== null ? `${fmt(v.current_pe, 2)} 倍` : '—';
      $('heroAchieve').textContent = data.metrics?.revenue_achieve_rate !== null
        ? `${fmt(data.metrics.revenue_achieve_rate, 1)} %`
        : '—';
      $('heroVolatility').textContent = v.price_volatility !== null ? `${fmt(v.price_volatility, 2)} %` : '—';
      $('heroYield').textContent = v.est_current_yield !== null ? `${fmt(v.est_current_yield, 2)} %` : '—';
      $('heroDate').textContent = latestDate || '—';
    }
    $('heroStrip').style.display = 'flex';

    // ── Revenue metrics ──
    const revenueMetrics = $('revenueMetrics');
    revenueMetrics.innerHTML = '';
    const m = data.metrics || {};
    const baselineSuffix = m.baseline_year ? ` (基準 ${m.baseline_year})` : '';
    revenueMetrics.appendChild(metricCard(
      `推估 ${targetYear} 年總營收${baselineSuffix}`,
      m.estimated_total_revenue !== null ? `${fmt(m.estimated_total_revenue, 2)} 億` : '—'
    ));
    revenueMetrics.appendChild(metricCard(
      `${targetYear} 年累計營收`,
      m.current_total_revenue !== null ? `${fmt(m.current_total_revenue, 2)} 億` : '—'
    ));
    revenueMetrics.appendChild(metricCard(
      'YTD 達成率',
      m.revenue_achieve_rate !== null ? `${fmt(m.revenue_achieve_rate, 2)} %` : '—'
    ));

    // ── Chart ──
    const points = (data.chart && data.chart.points) || [];
    const labels = points.map(p => p.date.slice(0, 7));
    const values = points.map(p => p.revenue_mon_bil !== null ? Number(p.revenue_mon_bil) : null);

    const canvas = $('revenueChart');
    if (canvas._chartInstance) canvas._chartInstance.destroy();
    canvas._chartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: '月營收 (億)',
          data: values,
          borderColor: '#00d4ff',
          backgroundColor: 'rgba(0, 212, 255, 0.06)',
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#00d4ff',
          pointBorderColor: '#080c10',
          pointBorderWidth: 2,
          fill: true,
          tension: 0.3,
          spanGaps: true,
        }],
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#111820',
            borderColor: '#1c2530',
            borderWidth: 1,
            titleColor: '#6b8096',
            bodyColor: '#00d4ff',
            titleFont: { family: 'IBM Plex Mono', size: 10 },
            bodyFont: { family: 'IBM Plex Mono', size: 13, weight: '700' },
            padding: 10,
            callbacks: {
              label: ctx => ` ${ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) : '—'} 億`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#4a5f72', font: { family: 'IBM Plex Mono', size: 10 } },
            grid: { color: 'rgba(255,255,255,0.04)' },
          },
          y: {
            ticks: { color: '#4a5f72', font: { family: 'IBM Plex Mono', size: 10 } },
            grid: { color: 'rgba(255,255,255,0.04)' },
            beginAtZero: false,
          },
        },
      },
    });

    // ── Table ──
    const tbody = $('tableBody');
    tbody.innerHTML = '';
    const rows = (data.table_rows || []).slice(); // latest first .reverse()
    for (const row of rows) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.date ? row.date.slice(0, 7) : '—'}</td>
        <td>${row.revenue_mon_bil !== null ? fmt(row.revenue_mon_bil) : '—'}</td>
        <td style="color:${(row.yoy_percent ?? 0) > 0 ? 'var(--red)' : 'var(--green)'}">${row.yoy_percent !== null ? fmtPct(row.yoy_percent) : '—'}</td>
        <td>${row.revenue_ytd_bil !== null ? fmt(row.revenue_ytd_bil) : '—'}</td>
        <td style="color:${(row.ytd_yoy_percent ?? 0) > 0 ? 'var(--red)' : 'var(--green)'}">${row.ytd_yoy_percent !== null ? fmtPct(row.ytd_yoy_percent) : '—'}</td>
      `;
      tbody.appendChild(tr);
    }

    // ── Valuation metrics ──
    const valMetrics = $('valuationMetrics');
    valMetrics.innerHTML = '';
    const conclusionEl = $('conclusion');
    conclusionEl.style.display = 'none';

    if (v) {
      valMetrics.appendChild(metricCard('目前股價', v.current_price !== null ? `${fmt(v.current_price, 2)} 元` : '—'));
      valMetrics.appendChild(metricCard('最新本益比', v.current_pe !== null ? `${fmt(v.current_pe, 2)} 倍` : '—'));
      valMetrics.appendChild(metricCard('推估現價殖利率', v.est_current_yield !== null ? `${fmt(v.est_current_yield, 2)} %` : '—'));

      valMetrics.appendChild(metricCard(
        '推估今年營收',
        v.est_revenue !== null ? `${fmt(v.est_revenue, 2)} 億元` : '—',
        v.ytd_yoy_percent !== null ? `年增率設定：${fmtPct(v.ytd_yoy_percent)}` : null
      ));
      valMetrics.appendChild(metricCard('目前累計營收', v.revenue_ytd !== null ? `${fmt(v.revenue_ytd, 2)} 億元` : '—'));
      valMetrics.appendChild(metricCard('營收達成率', v.rev_achieve_rate !== null ? `${fmt(v.rev_achieve_rate, 2)} %` : '—'));

      valMetrics.appendChild(metricCard(
        '推估稅後淨利',
        v.est_net_income !== null ? `${fmt(v.est_net_income, 2)} 億元` : '—',
        v.net_margin !== null ? `反推淨利率：${fmtPct(v.net_margin)}` : null
      ));
      valMetrics.appendChild(metricCard('推估全年 EPS', v.est_eps !== null ? `${fmt(v.est_eps, 2)} 元` : '—'));
      valMetrics.appendChild(metricCard(
        'EPS 達成率',
        v.eps_achieve_rate !== null ? `${fmt(v.eps_achieve_rate, 2)} %` : '—',
        v.eps_ytd !== null ? `累計 EPS：${v.eps_ytd}` : null
      ));

      valMetrics.appendChild(metricCard(
        '推估總股息',
        v.est_dividend !== null ? `${fmt(v.est_dividend, 2)} 元` : '—',
        v.avg_payout_ratio !== null ? `7 年平均分配率：${fmtPct(v.avg_payout_ratio)}` : null
      ));
      valMetrics.appendChild(metricCard(
        '推估基本面價',
        v.est_fair_price !== null ? `${fmt(v.est_fair_price, 2)} 元` : '—',
        v.avg_yield_3yr !== null ? `3 年平均殖利率：${fmtPct(v.avg_yield_3yr)}` : null
      ));
      valMetrics.appendChild(metricCard(
        '股價波動位階',
        v.price_volatility !== null ? `${fmt(v.price_volatility, 2)} %` : '—',
        '現價佔基本面估價的比例'
      ));

      // ── Conclusion ──
      const isUnder = Boolean(v.is_undervalued);
      conclusionEl.style.display = 'block';
      conclusionEl.className = `conclusion ${isUnder ? 'success' : 'error'}`;
      const arrow = isUnder ? '▼ UNDERVALUED' : '▲ OVERVALUED';
      conclusionEl.textContent = isUnder
        ? `${arrow}  ${v.stock_name} 目前股價 (${fmt(v.current_price, 2)} 元) 低於基本面推估價 (${fmt(v.est_fair_price, 2)} 元)，屬於相對便宜區間。`
        : `${arrow}  ${v.stock_name} 目前股價 (${fmt(v.current_price, 2)} 元) 高於基本面推估價 (${fmt(v.est_fair_price, 2)} 元)，屬於相對偏貴區間。`;
    }

    // ── Price Band Section ──
    const bandSection = document.createElement('div');
    bandSection.innerHTML = `
      <div class="section-header" style="margin-top:20px;">
        <div class="section-title">📐 本益比／殖利率區間估價</div>
        <div class="section-line"></div>
      </div>
    `;
    $('content').appendChild(bandSection);

    if (v && v.band_low !== undefined) {
      const price = v.current_price ?? 0;
      const low   = v.band_low;
      const mid   = v.band_mid;
      const high  = v.band_high;

      // Determine zone
      let zoneLabel = '', zoneColor = 'var(--muted2)';
      if (price <= mid) {
        zoneLabel = '▼ 買進區間（低價～中間價）';
        zoneColor = 'var(--green)';
      } else if (price <= high) {
        zoneLabel = '◆ 觀察區間（中間價～高價）';
        zoneColor = 'var(--orange)';
      } else {
        zoneLabel = '▲ 賣出區間（高價以上）';
        zoneColor = 'var(--red)';
      }

      // Build gauge bar — clamp price position between 0–100% across low→high range
      const range = high - low || 1;
      const pct = Math.min(100, Math.max(0, ((price - low) / range) * 100));
      const midPct = 50;

      const bandWrap = document.createElement('div');
      bandWrap.className = 'fade-in';
      bandWrap.innerHTML = `
        <div class="metrics-grid" style="margin-bottom:12px;">
          <div class="metric-card">
            <div class="metric-label">近7年本益比最低均值</div>
            <div class="metric-value">${fmt(v.avg_7yr_low_pe, 2)} 倍</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">近7年本益比最高均值</div>
            <div class="metric-value">${fmt(v.avg_7yr_high_pe, 2)} 倍</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">近7年殖利率區間</div>
            <div class="metric-value">${fmt(v.min_7yr_yield, 2)}% ～ ${fmt(v.max_7yr_yield, 2)}%</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">本益比低估價</div>
            <div class="metric-value" style="color:var(--green)">${fmt(v.pe_low_price, 2)} 元</div>
            <div class="metric-help">EPS × 近7年最低本益比均值</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">殖利率低估價</div>
            <div class="metric-value" style="color:var(--green)">${fmt(v.yield_low_price, 2)} 元</div>
            <div class="metric-help">預估股利 ÷ 近7年最高殖利率</div>
          </div>
          <div class="metric-card">
            <div class="metric-label" style="color:var(--green);font-weight:700;">▶ 低價（買進參考）</div>
            <div class="metric-value" style="color:var(--green);font-size:24px;">${fmt(low, 2)} 元</div>
            <div class="metric-help">低本益比價 vs 高殖利率價 取高</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">本益比高估價</div>
            <div class="metric-value" style="color:var(--red)">${fmt(v.pe_high_price, 2)} 元</div>
            <div class="metric-help">EPS × 近7年最高本益比均值</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">殖利率高估價</div>
            <div class="metric-value" style="color:var(--red)">${fmt(v.yield_high_price, 2)} 元</div>
            <div class="metric-help">預估股利 ÷ 近7年最低殖利率</div>
          </div>
          <div class="metric-card">
            <div class="metric-label" style="color:var(--red);font-weight:700;">▶ 高價（賣出參考）</div>
            <div class="metric-value" style="color:var(--red);font-size:24px;">${fmt(high, 2)} 元</div>
            <div class="metric-help">高本益比價 vs 低殖利率價 取低</div>
          </div>
        </div>

        <!-- Gauge bar -->
        <div class="panel" style="margin-bottom:10px;">
          <div class="panel-title">股價位置</div>
          <div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;color:var(--muted);margin-bottom:6px;">
            <span style="color:var(--green)">低價 ${fmt(low, 2)}</span>
            <span style="color:var(--gold)">中間價 ${fmt(mid, 2)}</span>
            <span style="color:var(--red)">高價 ${fmt(high, 2)}</span>
          </div>
          <div style="position:relative;height:14px;background:linear-gradient(90deg,rgba(0,230,118,0.25),rgba(255,152,0,0.25),rgba(255,61,90,0.25));border-radius:7px;border:1px solid var(--border2);">
            <!-- mid marker -->
            <div style="position:absolute;left:${midPct}%;top:0;bottom:0;width:1px;background:var(--gold);opacity:0.6;"></div>
            <!-- price marker -->
            <div style="position:absolute;left:${pct}%;transform:translateX(-50%);top:-4px;width:8px;height:22px;background:var(--accent);border-radius:3px;box-shadow:0 0 8px rgba(0,212,255,0.6);"></div>
          </div>
          <div style="margin-top:10px;font-family:var(--mono);font-size:13px;font-weight:700;color:${zoneColor};">${zoneLabel}</div>
          <div style="margin-top:4px;font-family:var(--mono);font-size:11px;color:var(--muted);">
            目前股價 <span style="color:var(--accent)">${fmt(price, 2)} 元</span>，中間價 <span style="color:var(--gold)">${fmt(mid, 2)} 元</span>
          </div>
        </div>
      `;
      $('content').appendChild(bandWrap);
    }

    $('loading').style.display = 'none';
    $('content').style.display = 'block';

    // Store for auto update
    _detailValuation = v;
    _detailData = data;

    // ── Live price overlay (trading hours only) ──
    if (isTradingHours()) {
      const stockId = getQueryParam('stock_id');
      const livePrice = await fetchLivePrice(stockId);
      if (livePrice !== null) {
        applyLivePriceToDetail(livePrice, v, data);
      }
    }

  } catch (err) {
    console.error(err);
    $('loading').innerHTML = `<div class="loading-text" style="color:var(--red);">ERROR: ${err?.message || err}</div>`;
  }
}

loadDetail();

// ── Auto update every 30 min during 09:00–14:00 ──
function isAutoUpdateHours() {
  const now = new Date();
  const tw = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  const day = tw.getDay();
  if (day === 0 || day === 6) return false;
  const minutes = tw.getHours() * 60 + tw.getMinutes();
  return minutes >= 9 * 60 && minutes < 14 * 60;
}

let _detailValuation = null;
let _detailData = null;

// setInterval(async () => {
//   if (!isAutoUpdateHours()) return;
//   const stockId = getQueryParam('stock_id');
//   if (!stockId || !_detailValuation) return;
//   const livePrice = await fetchLivePrice(stockId);
//   if (livePrice !== null) {
//     applyLivePriceToDetail(livePrice, _detailValuation, _detailData);
//   }
// }, 30 * 60 * 1000);  //每 60 分鐘執行一次（30 × 60 × 1000 毫秒）

// ── Tab switch ──
function switchTab(tab) {
  const isNews = tab === 'news';
  $('tabPaneNews').style.display  = isNews ? 'block' : 'none';
  $('tabPaneTable').style.display = isNews ? 'none'  : 'block';
  $('tabNews').classList.toggle('active', isNews);
  $('tabTable').classList.toggle('active', !isNews);
}

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
      const stockId = getQueryParam('stock_id');
      const livePrice = await fetchLivePrice(stockId);
      if (livePrice !== null && _detailValuation) {
        applyLivePriceToDetail(livePrice, _detailValuation, _detailData);
      }
      indicator.style.height = '0';
    }
  }, { passive: true });
})();

// ── Apply live price to stock detail page ──
function applyLivePriceToDetail(livePrice, v, data) {
  // 1. Hero strip price + label
  const heroPrice = $('heroPrice');
  if (heroPrice) {
    heroPrice.innerHTML = `${fmt(livePrice, 2)}<span class="hero-price-unit"> 元</span>`;
  }
  const label = $('heroPriceLabel');
  if (label) label.textContent = 'LIVE PRICE';

  // 2. Recalculate derived values with live price
  const fairPrice = v?.est_fair_price;
  const newVol = fairPrice ? (livePrice / fairPrice) * 100 : null;

  // Update hero volatility
  if (newVol !== null) {
    const heroVol = $('heroVolatility');
    if (heroVol) heroVol.textContent = `${fmt(newVol, 2)} %`;
  }

  // Update est_current_yield with live price
  const estDiv = v?.est_dividend;
  const newYield = estDiv ? (estDiv / livePrice) * 100 : null;
  if (newYield !== null) {
    const heroYield = $('heroYield');
    if (heroYield) heroYield.textContent = `${fmt(newYield, 2)} %`;
  }

  // 3. Update valuation metric cards
  document.querySelectorAll('.metric-card').forEach(card => {
    const label = card.querySelector('.metric-label')?.textContent?.trim();
    const valueEl = card.querySelector('.metric-value');
    if (!valueEl) return;
    if (label === '目前股價') {
      valueEl.textContent = `${fmt(livePrice, 2)} 元`;
    } else if (label === '推估現價殖利率' && newYield !== null) {
      valueEl.textContent = `${fmt(newYield, 2)} %`;
    } else if (label === '股價波動位階' && newVol !== null) {
      valueEl.textContent = `${fmt(newVol, 2)} %`;
    }
  });

  // 4. Update conclusion banner
  const conclusionEl = $('conclusion');
  if (conclusionEl && fairPrice) {
    const isUnder = livePrice < fairPrice;
    conclusionEl.className = `conclusion ${isUnder ? 'success' : 'error'}`;
    const arrow = isUnder ? '▼ UNDERVALUED' : '▲ OVERVALUED';
    const stockName = v?.stock_name || '';
    conclusionEl.textContent = isUnder
      ? `${arrow}  ${stockName} 目前股價 (${fmt(livePrice, 2)} 元) 低於基本面推估價 (${fmt(fairPrice, 2)} 元)，屬於相對便宜區間。`
      : `${arrow}  ${stockName} 目前股價 (${fmt(livePrice, 2)} 元) 高於基本面推估價 (${fmt(fairPrice, 2)} 元)，屬於相對偏貴區間。`;
  }

  // 5. Update gauge bar marker and zone label
  const low = v?.band_low, mid = v?.band_mid, high = v?.band_high;
  if (low != null && mid != null && high != null) {
    const range = high - low || 1;
    const pct = Math.min(100, Math.max(0, ((livePrice - low) / range) * 100));

    let zoneLabel = '', zoneColor = 'var(--muted2)';
    if (livePrice <= mid) {
      zoneLabel = '▼ 買進區間（低價～中間價）';
      zoneColor = 'var(--green)';
    } else if (livePrice <= high) {
      zoneLabel = '◆ 觀察區間（中間價～高價）';
      zoneColor = 'var(--orange)';
    } else {
      zoneLabel = '▲ 賣出區間（高價以上）';
      zoneColor = 'var(--red)';
    }

    // marker (blue rect in gauge bar)
    const marker = document.querySelector('.panel [style*="background:var(--accent)"]');
    if (marker) marker.style.left = `${pct}%`;

    // zone label text
    document.querySelectorAll('.panel [style*="font-weight:700"]').forEach(el => {
      if (el.textContent.includes('區間')) {
        el.style.color = zoneColor;
        el.textContent = zoneLabel;
      }
    });

    // price text under gauge
    document.querySelectorAll('.panel [style*="font-size:11px"]').forEach(el => {
      if (el.innerHTML.includes('目前股價')) {
        el.innerHTML = `目前股價 <span style="color:var(--accent)">${fmt(livePrice, 2)} 元</span>，中間價 <span style="color:var(--gold)">${fmt(mid, 2)} 元</span>`;
      }
    });
  }
}

async function loadNews(stockId, stockName) {
  const newsList = $('newsList');

  try {
    const apiBase = getApiBase();
    const params = stockName ? `?name=${encodeURIComponent(stockName)}` : '';
    const res = await fetch(`${apiBase}/api/news/${encodeURIComponent(stockId)}${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.items || data.items.length === 0) {
      newsList.innerHTML = '<div class="news-error">目前無相關新聞</div>';
      return;
    }

    newsList.innerHTML = '';
    data.items.forEach(item => {
      const pubDate = new Date(item.pubDate);
      const diffMs = Date.now() - pubDate.getTime();
      const diffHr = Math.floor(diffMs / 3600000);
      const diffDay = Math.floor(diffMs / 86400000);
      let timeStr;
      if (isNaN(pubDate.getTime())) timeStr = '';
      else if (diffHr < 1)          timeStr = '剛剛';
      else if (diffHr < 24)         timeStr = `${diffHr} 小時前`;
      else if (diffDay < 7)         timeStr = `${diffDay} 天前`;
      else                          timeStr = pubDate.toLocaleDateString('zh-TW');

      const a = document.createElement('a');
      a.className = 'news-item fade-in';
      a.href = item.link;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML = `
        <div class="news-title">${item.title}</div>
        <div class="news-meta">
          <span class="news-source">${item.source || ''}</span>
          <span>${timeStr}</span>
        </div>
      `;
      newsList.appendChild(a);
    });

  } catch (err) {
    newsList.innerHTML = `<div class="news-error">新聞載入失敗：${err.message}</div>`;
  }
}
