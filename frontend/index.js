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

function formatPrice(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v !== "number") v = Number(v);
  if (!Number.isFinite(v)) return "—";
  return `${v.toFixed(2)} 元`;
}

function formatVolatility(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v !== "number") v = Number(v);
  if (!Number.isFinite(v)) return "—";
  return `${v.toFixed(2)} %`;
}

function formatAchieveRate(v) {
  if (v === null || v === undefined) return "尚未公布";
  if (typeof v !== "number") v = Number(v);
  if (!Number.isFinite(v)) return "尚未公布";
  return `${v} %`;
}

function achieveColor(rate) {
  if (rate === null || rate === undefined) return "#6b7280";
  const v = Number(rate);
  if (!Number.isFinite(v)) return "#6b7280";
  if (v >= 100) return "#16a34a";
  if (v >= 70) return "#f97316";
  if (v < 0) return "#6b7280";
  return "#0ea5e9";
}

function cardBgByVolatility(vol) {
  let cardBg = "#0f172a";
  if (vol === null || vol === undefined) return cardBg;
  const v = Number(vol);
  if (!Number.isFinite(v)) return cardBg;
  if (v >= 100) return "#451a1a";
  return "#064e3b";
}

function buildCard(item) {
  const rate = item.revenue_achieve_rate;
  const color = achieveColor(rate);
  const cardBg = cardBgByVolatility(item.price_volatility);
  const statusText = item.is_latest ? "已公布最新月份" : "尚未公布最新月份";
  const statusColor = item.is_latest ? "#22c55e" : "#f97316";
  const monthText = item.update_month ? `營收更新至：${item.update_month}` : "營收更新月份：尚未公布";
  const priceDisplay = formatPrice(item.current_price);
  const volatilityDisplay = formatVolatility(item.price_volatility);

  const card = document.createElement("div");
  card.className = "card";
  card.style.background = cardBg;

  card.innerHTML = `
    <div class="left">
      <div class="subtle">${item.stock_id}</div>
      <div class="companyName">${item.company_name_short || ""}</div>
      <div class="achieveLabel">目前達成率</div>
      <div class="achieveValue" style="color:${color};">${formatAchieveRate(rate)}</div>
      <div class="monthText">${monthText}</div>
      <div class="statusText" style="color:${statusColor};">${statusText}</div>
    </div>
    <div class="right">
      <div class="subtle">最新股價</div>
      <div class="priceValue">${priceDisplay}</div>
      <div class="subtle">股價波動位階</div>
      <div style="font-size:14px; font-weight:700; color:#fbbf24;">${volatilityDisplay}</div>
      <div class="btnRow">
        <button class="detailBtn" data-sid="${item.stock_id}">查看詳細</button>
      </div>
    </div>
  `;

  card.querySelector("button[data-sid]").addEventListener("click", (e) => {
    const sid = e.currentTarget.getAttribute("data-sid");
    window.location.href = `stock.html?stock_id=${encodeURIComponent(sid)}`;
  });

  return card;
}

async function loadSummary() {
  const apiBase = getApiBase();
  const grid = $("grid");
  const loadingEl = $("loading");
  const topNotice = $("topNotice");
  const titleEl = $("pageTitle");
  const captionEl = $("pageCaption");

  grid.innerHTML = "";
  loadingEl.style.display = "block";
  topNotice.style.display = "none";

  try {
    const res = await fetch(`${apiBase}/api/stocks/summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const targetYear = data.global_target_year;
    titleEl.textContent = `台股營收達成率總覽`;
    captionEl.textContent = targetYear ? `${targetYear} 年度營收目標達成進度` : "載入失敗：沒有資料";
    topNotice.style.display = "block";
    topNotice.textContent = "點選下方「查看詳細」進入個股頁面";

    const items = data.items || [];
    if (!items.length) {
      loadingEl.textContent = "尚無足夠資料計算達成率。";
      return;
    }

    loadingEl.style.display = "none";
    for (const item of items) grid.appendChild(buildCard(item));
  } catch (err) {
    console.error(err);
    loadingEl.textContent = `載入失敗：${err?.message || err}`;
  }
}

function initApiBar() {
  const apiBaseInput = $("apiBaseInput");
  const saveBtn = $("saveApiBase");
  const current = getApiBase();
  apiBaseInput.value = current;

  saveBtn.addEventListener("click", () => {
    const v = apiBaseInput.value.trim();
    if (!v) return;
    setApiBase(v);
    loadSummary();
  });

  apiBaseInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveBtn.click();
  });
}

initApiBar();
loadSummary();

