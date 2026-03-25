const DEFAULT_API_BASE = "http://localhost:8000";
const API_KEY = "apiBase";

function getApiBase() {
  return localStorage.getItem(API_KEY) || DEFAULT_API_BASE;
}

function setApiBase(v) {
  localStorage.setItem(API_KEY, v);
}

function $(id) {
  return document.getElementById(id);
}

function getQueryParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function fmtNum(v, digits = 2) {
  if (v === null || v === undefined) return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function fmtPct(v, digits = 2) {
  if (v === null || v === undefined) return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(digits)} %`;
}

function createMetricCard(label, value, helpText = null) {
  const el = document.createElement("div");
  el.className = "metricCard";
  el.innerHTML = `
    <div class="metricLabel">${label}</div>
    <div class="metricValue">${value}</div>
    ${helpText ? `<div class="metricHelp">${helpText}</div>` : ""}
  `;
  return el;
}

async function loadDetail() {
  const stockId = getQueryParam("stock_id");
  const loadingEl = $("loading");
  const contentEl = $("content");
  const captionEl = $("pageCaption");
  const metricsGrid = $("metricsGrid");
  const valuationMetrics = $("valuationMetrics");
  const conclusionEl = $("conclusion");
  const tableBody = $("dataTable").querySelector("tbody");

  if (!stockId) {
    loadingEl.textContent = "缺少 stock_id 參數。";
    return;
  }

  const apiBase = getApiBase();
  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  try {
    const res = await fetch(`${apiBase}/api/stocks/${encodeURIComponent(stockId)}/detail`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const stockName = data.stock_name || stockId;
    const targetYear = data.target_year;
    captionEl.textContent = `${stockId} ${stockName} - ${targetYear} 年營收進度`;
    $("pageTitle").textContent = `📊 ${stockId} ${stockName} 營收進度`;

    // Metrics
    metricsGrid.innerHTML = "";
    const m = data.metrics || {};

    const baselineSuffix = m.baseline_year ? `（基準 ${m.baseline_year} 年）` : "";
    const estimatedText =
      m.estimated_total_revenue === null || m.estimated_total_revenue === undefined
        ? "尚未公布"
        : `${fmtNum(m.estimated_total_revenue, 2)} 億`;
    const currentText =
      m.current_total_revenue === null || m.current_total_revenue === undefined
        ? "尚未公布"
        : `${fmtNum(m.current_total_revenue, 2)} 億`;
    const achieveText =
      m.revenue_achieve_rate === null || m.revenue_achieve_rate === undefined
        ? "尚未公布"
        : `${fmtNum(m.revenue_achieve_rate, 2)} %`;

    metricsGrid.appendChild(
      createMetricCard(`推估 ${targetYear} 年總營收${baselineSuffix}`, estimatedText)
    );
    metricsGrid.appendChild(
      createMetricCard(`${targetYear} 年目前總營收`, currentText)
    );
    metricsGrid.appendChild(
      createMetricCard("目前達成率", achieveText)
    );

    // Chart
    const points = (data.chart && data.chart.points) || [];
    const labels = points.map((p) => p.date.slice(0, 7)); // YYYY-MM
    const values = points.map((p) => (p.revenue_mon_bil === null ? null : Number(p.revenue_mon_bil)));

    const canvas = $("revenueChart");
    if (canvas._chartInstance) canvas._chartInstance.destroy();
    const chart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "月營收 (億)",
            data: values,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            borderWidth: 2,
            pointRadius: 3,
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { labels: { color: "#9ca3af" } },
          tooltip: { enabled: true },
        },
        scales: {
          x: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.06)" } },
          y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.06)" }, beginAtZero: true },
        },
      },
    });
    canvas._chartInstance = chart;

    // Table
    tableBody.innerHTML = "";
    for (const row of data.table_rows || []) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.date}</td>
        <td>${row.revenue_mon_bil === null ? "—" : fmtNum(row.revenue_mon_bil, 2)}</td>
        <td>${row.yoy_percent === null ? "—" : fmtPct(row.yoy_percent, 2)}</td>
        <td>${row.revenue_ytd_bil === null ? "—" : fmtNum(row.revenue_ytd_bil, 2)}</td>
        <td>${row.ytd_yoy_percent === null ? "—" : fmtPct(row.ytd_yoy_percent, 2)}</td>
      `;
      tableBody.appendChild(tr);
    }

    // Valuation
    valuationMetrics.innerHTML = "";
    conclusionEl.style.display = "none";
    conclusionEl.className = "alert";

    if (data.valuation) {
      const v = data.valuation;

      const currentPrice = v.current_price === null ? null : Number(v.current_price);
      const currentPe = v.current_pe === null ? null : Number(v.current_pe);
      const estYield = v.est_current_yield === null ? null : Number(v.est_current_yield);

      valuationMetrics.appendChild(createMetricCard("目前股價", currentPrice === null ? "尚未公布" : `${fmtNum(currentPrice, 2)} 元`));
      valuationMetrics.appendChild(createMetricCard("最新本益比", currentPe === null ? "尚未公布" : `${fmtNum(currentPe, 2)} 倍`));
      valuationMetrics.appendChild(createMetricCard("推估現價殖利率", estYield === null ? "尚未公布" : `${fmtNum(estYield, 2)} %`));

      const ytdYoYHelp = v.ytd_yoy_percent !== null && v.ytd_yoy_percent !== undefined ? `年增率設定：約 ${fmtPct(v.ytd_yoy_percent, 2)}` : null;
      valuationMetrics.appendChild(
        createMetricCard("推估今年營收", v.est_revenue === null ? "尚未公布" : `${fmtNum(v.est_revenue, 2)} 億元`, ytdYoYHelp)
      );
      valuationMetrics.appendChild(
        createMetricCard("目前累計營收", v.revenue_ytd === null ? "尚未公布" : `${fmtNum(v.revenue_ytd, 2)} 億元`)
      );
      valuationMetrics.appendChild(
        createMetricCard("營收達成率", v.rev_achieve_rate === null ? "尚未公布" : `${fmtNum(v.rev_achieve_rate, 2)} %`)
      );

      const netMarginHelp = v.net_margin !== null && v.net_margin !== undefined ? `反推淨利率：約 ${fmtPct(v.net_margin, 2)}` : null;
      valuationMetrics.appendChild(
        createMetricCard("推估稅後淨利", v.est_net_income === null ? "尚未公布" : `${fmtNum(v.est_net_income, 2)} 億元`, netMarginHelp)
      );
      valuationMetrics.appendChild(
        createMetricCard("推估全年 EPS", v.est_eps === null ? "尚未公布" : `${fmtNum(v.est_eps, 2)} 元`)
      );
      valuationMetrics.appendChild(
        createMetricCard("EPS 達成率", v.eps_achieve_rate === null ? "尚未公布" : `${fmtNum(v.eps_achieve_rate, 2)} %`, v.eps_ytd !== null ? `目前累計 EPS：${v.eps_ytd}` : null)
      );

      valuationMetrics.appendChild(
        createMetricCard("推估總股息", v.est_dividend === null ? "尚未公布" : `${fmtNum(v.est_dividend, 2)} 元`, v.avg_payout_ratio !== null ? `近 7 年平均分配率：約 ${fmtPct(v.avg_payout_ratio, 2)}` : null)
      );
      valuationMetrics.appendChild(
        createMetricCard("推估基本面價", v.est_fair_price === null ? "尚未公布" : `${fmtNum(v.est_fair_price, 2)} 元`, v.avg_yield_3yr !== null ? `採用近 3 年平均殖利率：約 ${fmtPct(v.avg_yield_3yr, 2)}` : null)
      );
      valuationMetrics.appendChild(
        createMetricCard("股價波動位階", v.price_volatility === null ? "尚未公布" : `${fmtNum(v.price_volatility, 2)} %`, "現價佔基本面價的比例")
      );

      const isUndervalued = Boolean(v.is_undervalued);
      const basePrice = v.est_fair_price;
      const curPrice = v.current_price;

      conclusionEl.style.display = "block";
      conclusionEl.className = `alert ${isUndervalued ? "success" : "error"}`;
      conclusionEl.textContent = isUndervalued
        ? `【結論】${v.stock_name} 目前股價 (${fmtNum(curPrice, 2)} 元) 低於基本面推估價 (${fmtNum(basePrice, 2)} 元)，屬於相對便宜區間。`
        : `【結論】${v.stock_name} 目前股價 (${fmtNum(curPrice, 2)} 元) 高於或接近基本面推估價 (${fmtNum(basePrice, 2)} 元)，屬於相對偏貴區間。`;
    }

    loadingEl.style.display = "none";
    contentEl.style.display = "block";
  } catch (err) {
    console.error(err);
    loadingEl.textContent = `載入失敗：${err?.message || err}`;
  }
}

function initApiBar() {
  const apiBaseInput = $("apiBaseInput");
  const saveBtn = $("saveApiBase");
  apiBaseInput.value = getApiBase();

  saveBtn.addEventListener("click", () => {
    const v = apiBaseInput.value.trim();
    if (!v) return;
    setApiBase(v);
    loadDetail();
  });
}

function initBackButton() {
  $("backBtn").addEventListener("click", () => {
    window.location.href = "index.html";
  });
}

initApiBar();
initBackButton();
loadDetail();

