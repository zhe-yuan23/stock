const TOKEN_KEY = 'stockAdminToken';
const API_KEY = 'apiBase';
const DEFAULT_API_BASE = '';

const DATASET_FIELDS = {
  monthly_eps: [
    { name: 'date', label: '資料日期', type: 'date' },
    { name: 'eps_mon', label: '當月 EPS（元）', type: 'number', step: '0.01' },
  ],
  yearly_revenue: [
    { name: 'year', label: '年度', type: 'number', min: '1900', max: '2100', step: '1' },
    { name: 'revenue_yearly', label: '全年總營收（億元）', type: 'number', step: '0.01' },
  ],
  dividend_history: [
    { name: 'year', label: '年度', type: 'number', min: '1900', max: '2100', step: '1' },
    { name: 'eps', label: '全年 EPS（元）', type: 'number', step: '0.01' },
    { name: 'cash_div', label: '現金股利（元）', type: 'number', step: '0.001' },
    { name: 'stock_div', label: '股票股利（元）', type: 'number', step: '0.001' },
  ],
  historical_valuation: [
    { name: 'year', label: '年度', type: 'number', min: '1900', max: '2100', step: '1' },
    { name: 'lowest_pe', label: '最低本益比', type: 'number', min: '0', step: '0.01' },
    { name: 'highest_pe', label: '最高本益比', type: 'number', min: '0', step: '0.01' },
    { name: 'annual_yield_pct', label: '年殖利率（%）', type: 'number', min: '0', step: '0.01' },
  ],
};

const $ = id => document.getElementById(id);
let currentRecords = {};

function apiBase() { return localStorage.getItem(API_KEY) || ''; }
function token() { return localStorage.getItem(TOKEN_KEY) || ''; }
function headers(json = false) {
  const result = { Authorization: `Bearer ${token()}` };
  if (json) result['Content-Type'] = 'application/json';
  return result;
}

function setMessage(id, text, kind = '') {
  const el = $(id); el.textContent = text; el.className = `message ${kind}`;
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: { ...headers(Boolean(options.body)), ...(options.headers || {}) },
  });
  let body = null;
  try { body = await response.json(); } catch { /* empty response */ }
  if (!response.ok) throw new Error(body?.detail || `HTTP ${response.status}`);
  return body;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
}

async function loadStocks() {
  const response = await fetch(`${apiBase()}/api/stocks/summary`);
  if (!response.ok) throw new Error(`股票清單載入失敗（HTTP ${response.status}）`);
  const data = await response.json();
  const items = (data.items || []).slice().sort((a, b) => String(a.stock_id).localeCompare(String(b.stock_id), 'en', { numeric: true }));
  $('stockSelect').innerHTML = items.map(item => `<option value="${escapeHtml(item.stock_id)}">${escapeHtml(item.stock_id)} ${escapeHtml(item.company_name_short || '')}</option>`).join('');
  if (!items.length) throw new Error('找不到股票資料');
}

function renderForm() {
  const dataset = $('datasetSelect').value;
  $('dataForm').innerHTML = DATASET_FIELDS[dataset].map(field => `
    <label>${field.label}<input required name="${field.name}" type="${field.type}" step="${field.step || ''}" min="${field.min || ''}" max="${field.max || ''}"></label>
  `).join('');
  renderRecords();
}

function renderRecords() {
  const dataset = $('datasetSelect').value;
  const fields = DATASET_FIELDS[dataset];
  const key = fields[0].name;
  const rows = (currentRecords[dataset] || []).slice().sort((a, b) =>
    String(b[key] ?? '').localeCompare(String(a[key] ?? ''), 'en', { numeric: true })
  );
  $('recordsPanel').style.display = 'block';
  $('recordsHead').innerHTML = `<tr>${fields.map(field => `<th>${field.label}</th>`).join('')}</tr>`;
  $('recordsBody').innerHTML = rows.map(row => `<tr>${fields.map(field => `<td>${escapeHtml(row[field.name])}</td>`).join('')}</tr>`).join('') || '<tr><td colspan="10">尚無資料</td></tr>';
}

async function loadManualData() {
  const stockId = $('stockSelect').value;
  const data = await request(`/api/admin/stocks/${encodeURIComponent(stockId)}/manual`);
  currentRecords = data.datasets || {};
  $('storageLabel').textContent = `儲存方式：${data.storage}`;
  renderRecords();
}

async function login() {
  const base = $('apiBase').value.trim().replace(/\/$/, '');
  if (base) localStorage.setItem(API_KEY, base); else localStorage.removeItem(API_KEY);
  const value = $('adminToken').value.trim();
  if (!value) return setMessage('loginMessage', '請輸入管理員 Token', 'error');
  localStorage.setItem(TOKEN_KEY, value);
  $('loginBtn').disabled = true;
  try {
    const info = await request('/api/admin/verify');
    await loadStocks();
    $('loginPanel').style.display = 'none';
    $('app').style.display = 'block';
    $('datasetSelect').dispatchEvent(new Event('change'));
    await loadManualData();
    $('storageLabel').textContent = `儲存方式：${info.storage}`;
  } catch (error) {
    sessionStorage.removeItem(TOKEN_KEY);
    setMessage('loginMessage', error.message, 'error');
  } finally { $('loginBtn').disabled = false; }
}

async function save(event) {
  event.preventDefault();
  const dataset = $('datasetSelect').value;
  const payload = Object.fromEntries(new FormData($('dataForm')).entries());
  for (const field of DATASET_FIELDS[dataset]) {
    if (field.type === 'number') {
      payload[field.name] = Number(payload[field.name]);
      if (!Number.isFinite(payload[field.name])) {
        return setMessage('saveMessage', `${field.label} 必須是數字`, 'error');
      }
    }
  }
  $('saveBtn').disabled = true;
  setMessage('saveMessage', '儲存中……');
  try {
    const result = await request(`/api/admin/stocks/${encodeURIComponent($('stockSelect').value)}/manual/${dataset}`, { method: 'PUT', body: JSON.stringify(payload) });
    setMessage('saveMessage', `已儲存 ${result.key}（${result.storage}）`, 'success');
    $('dataForm').reset();
    await loadManualData();
  } catch (error) { setMessage('saveMessage', error.message, 'error'); }
  finally { $('saveBtn').disabled = false; }
}

async function addStock() {
  const stockId = $('newStockId').value.trim();
  if (!/^\d{4}$/.test(stockId)) return setMessage('saveMessage', '股票代號必須是 4 位數字', 'error');
  $('addStockBtn').disabled = true;
  setMessage('saveMessage', '新增股票中……');
  try {
    const result = await request('/api/admin/stocks', { method: 'POST', body: JSON.stringify({ stock_id: stockId }) });
    setMessage('saveMessage', `已新增 ${result.stock_id}，下一次資料更新會開始抓取`, 'success');
    $('newStockId').value = '';
    await loadStocks();
    if (![...$('stockSelect').options].some(option => option.value === stockId)) {
      $('stockSelect').add(new Option(`${stockId}（等待資料更新）`, stockId));
    }
    $('stockSelect').value = stockId;
    await loadManualData();
  } catch (error) { setMessage('saveMessage', error.message, 'error'); }
  finally { $('addStockBtn').disabled = false; }
}

function logout() { localStorage.removeItem(TOKEN_KEY); window.location.reload(); }

$('apiBase').value = localStorage.getItem(API_KEY) || '';
$('loginBtn').addEventListener('click', login);
$('dataForm').addEventListener('submit', save);
$('stockSelect').addEventListener('change', loadManualData);
$('datasetSelect').addEventListener('change', renderForm);
$('addStockBtn').addEventListener('click', addStock);
$('logoutBtn').addEventListener('click', logout);
