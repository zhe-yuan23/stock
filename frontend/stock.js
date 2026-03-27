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

    $('loading').style.display = 'none';
    $('content').style.display = 'block';

  } catch (err) {
    console.error(err);
    $('loading').innerHTML = `<div class="loading-text" style="color:var(--red);">ERROR: ${err?.message || err}</div>`;
  }
}

loadDetail();
