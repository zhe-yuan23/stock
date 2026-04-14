import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response

import difflib
import re


# Ensure we can import `src/*` when running on Zeabur or locally.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from src.calculator import calculate_valuation  # noqa: E402


DATA_DIR = REPO_ROOT / "data"
MANUAL_DIR = DATA_DIR / "manual_data"


def _to_jsonable(x: Any) -> Any:
    """Convert numpy/pandas types and NaN into plain JSON-friendly Python types."""
    try:
        # numpy float/int -> Python float/int
        if hasattr(x, "item"):
            x = x.item()
    except Exception:
        pass

    # NaN -> None
    try:
        if isinstance(x, float) and pd.isna(x):
            return None
    except Exception:
        pass

    return x


def _sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _to_jsonable(v) for k, v in d.items()}


def _parse_revenue_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))

    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"Missing `date` column in {path}")

    # Normalize date strings like `YYYY/MM/DD` -> `YYYY-MM-DD`, then parse.
    df["date"] = (
        df["date"]
        .astype(str)
        .str.replace("/", "-", regex=False)
    )
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def _get_baseline_revenue_for_estimate(
    stock_id: str,
    target_year: int,
    df_revenue: pd.DataFrame,
) -> tuple[Optional[int], Optional[float]]:
    """
    Same logic as `web.py`:
    - Prefer last year's revenue total from the automatic `*_revenue.csv`.
    - Fallback to `data/manual_data/{stock_id}/{stock_id}_yearly_revenue.csv`.
    """
    baseline_year = target_year - 1

    # 1) Prefer last year's revenue from df_revenue
    try:
        df_last_year = df_revenue[df_revenue["date"].dt.year == baseline_year]
        last_year_revenue = float(df_last_year["revenue_mon(bil)"].sum())
    except Exception:
        last_year_revenue = 0.0

    if last_year_revenue > 0:
        return baseline_year, last_year_revenue

    # 2) Fallback to manual yearly revenue
    try:
        manual_path = MANUAL_DIR / stock_id / f"{stock_id}_yearly_revenue.csv"
        df_yearly = pd.read_csv(manual_path)
        if "year" in df_yearly.columns and "revenue_yearly" in df_yearly.columns and not df_yearly.empty:
            df_yearly["year"] = pd.to_numeric(df_yearly["year"], errors="coerce")
            df_yearly = df_yearly.dropna(subset=["year"]).sort_values("year")

            row_exact = df_yearly[df_yearly["year"] == baseline_year]
            if not row_exact.empty:
                v = float(row_exact["revenue_yearly"].iloc[-1])
                if v > 0:
                    return baseline_year, v

            row_latest = df_yearly.iloc[-1]
            y = int(row_latest["year"])
            v = float(row_latest["revenue_yearly"])
            if v > 0:
                return y, v
    except Exception:
        pass

    return None, None


def _list_stock_ids() -> List[str]:
    if not DATA_DIR.exists():
        return []
    out: List[str] = []
    for p in DATA_DIR.iterdir():
        if p.is_dir() and p.name != "manual_data":
            out.append(p.name)
    return sorted(out)


def _get_stock_name_from_revenue(df_revenue: pd.DataFrame, fallback: str = "") -> str:
    if "name" in df_revenue.columns and not df_revenue.empty:
        try:
            return str(df_revenue["name"].iloc[0])
        except Exception:
            return fallback
    return fallback


app = FastAPI(title="Stock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # GitHub Pages + local dev; keep simple for now.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stocks/summary")
def get_stocks_summary() -> Dict[str, Any]:
    stock_ids = _list_stock_ids()
    if not stock_ids:
        return {"global_target_year": None, "items": []}

    # Determine global target year as max year across all stocks.
    all_years: List[int] = []
    revenue_dfs: Dict[str, pd.DataFrame] = {}

    for sid in stock_ids:
        revenue_path = DATA_DIR / sid / f"{sid}_revenue.csv"
        try:
            df = _parse_revenue_df(revenue_path)
            revenue_dfs[sid] = df
            if not df.empty:
                all_years.append(int(df["date"].dt.year.max()))
        except Exception:
            continue

    global_target_year = max(all_years) if all_years else pd.Timestamp.now().year

    summary_items: List[Dict[str, Any]] = []
    for sid in stock_ids:
        df = revenue_dfs.get(sid)
        if df is None or df.empty:
            # Keep consistent fields for sorting/rendering.
            summary_items.append(
                {
                    "stock_id": sid,
                    "company_name_full": f"{sid}",
                    "company_name_short": "",
                    "revenue_achieve_rate": None,
                    "update_month": None,
                    "latest_month_number": None,
                    "price_volatility": None,
                    "current_price": None,
                    "band_low": None,
                    "band_mid": None,
                    "band_high": None,
                    "est_fair_price": None,
                    "is_latest": False,
                    "has_data": False,
                }
            )
            continue

        df_this_year = df[df["date"].dt.year == global_target_year]
        stock_name = _get_stock_name_from_revenue(df, fallback="未知")

        # Estimation + pricing info (may fail if manual files are incomplete).
        price_volatility = None
        current_price = None
        band_low = None
        band_mid = None
        band_high = None
        est_fair_price = None
        try:
            valuation_result = calculate_valuation(sid)
            price_volatility = valuation_result.get("price_volatility")
            current_price = valuation_result.get("current_price")
            band_low = valuation_result.get("band_low")
            band_mid = valuation_result.get("band_mid")
            band_high = valuation_result.get("band_high")
            est_fair_price = valuation_result.get("est_fair_price")
        except Exception:
            pass

        baseline_year, last_year_revenue = _get_baseline_revenue_for_estimate(
            stock_id=sid,
            target_year=global_target_year,
            df_revenue=df,
        )

        if not df_this_year.empty and last_year_revenue and last_year_revenue > 0:
            last_date = df_this_year["date"].max()
            last_month_num = int(last_date.month)
            last_month_display = last_date.strftime("%Y-%m")

            newest_ytd_yoy = float(df_this_year["ytd_yoy(%)"].iat[-1])
            esti_revenue = last_year_revenue * (1 + newest_ytd_yoy / 100)
            revenue_sum = float(df_this_year["revenue_ytd(bil)"].iat[-1])

            revenue_achieve_rate = round(revenue_sum / esti_revenue * 100, 2) if esti_revenue else None

            summary_items.append(
                {
                    "stock_id": sid,
                    "company_name_full": f"{sid} {stock_name}".strip(),
                    "company_name_short": stock_name,
                    "revenue_achieve_rate": revenue_achieve_rate,
                    "update_month": last_month_display,
                    "latest_month_number": last_month_num,
                    "price_volatility": price_volatility,
                    "current_price": current_price,
                    "band_low": band_low,
                    "band_mid": band_mid,
                    "band_high": band_high,
                    "est_fair_price": est_fair_price,
                    "is_latest": False,
                    "has_data": revenue_achieve_rate is not None,
                }
            )
        else:
            summary_items.append(
                {
                    "stock_id": sid,
                    "company_name_full": f"{sid} {stock_name}".strip(),
                    "company_name_short": stock_name,
                    "revenue_achieve_rate": None,
                    "update_month": None,
                    "latest_month_number": None,
                    "price_volatility": price_volatility,
                    "current_price": current_price,
                    "band_low": band_low,
                    "band_mid": band_mid,
                    "band_high": band_high,
                    "est_fair_price": est_fair_price,
                    "is_latest": False,
                    "has_data": False,
                }
            )

    valid_months = [i["latest_month_number"] for i in summary_items if i["latest_month_number"] is not None]
    global_latest_month = max(valid_months) if valid_months else None
    for item in summary_items:
        item["is_latest"] = global_latest_month is not None and item["latest_month_number"] == global_latest_month

    def sort_key(item: Dict[str, Any]):
        v = item.get("revenue_achieve_rate")
        try:
            v_num = float(v) if v is not None else -1.0
        except Exception:
            v_num = -1.0
        has_data = item.get("has_data", False) or v_num >= 0
        return (has_data, v_num)

    summary_items.sort(key=sort_key, reverse=True)

    return {
        "global_target_year": global_target_year,
        "items": [_sanitize_dict(i) for i in summary_items],
    }


@app.get("/api/stocks/{stock_id}/valuation")
def get_stock_valuation(stock_id: str) -> Dict[str, Any]:
    try:
        result = calculate_valuation(stock_id)
        return _sanitize_dict(result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Missing valuation files: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{stock_id}/detail")
def get_stock_detail(stock_id: str) -> Dict[str, Any]:
    revenue_path = DATA_DIR / stock_id / f"{stock_id}_revenue.csv"
    if not revenue_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing file: {revenue_path}")

    try:
        df = _parse_revenue_df(revenue_path)
        if df.empty:
            raise HTTPException(status_code=404, detail="Empty revenue data")

        target_year = int(df["date"].dt.year.max())
        df_this_year = df[df["date"].dt.year == target_year]
        stock_name = _get_stock_name_from_revenue(df, fallback="")

        baseline_year = None
        esti_revenue = None
        revenue_sum = None
        revenue_achieve_rate = None
        latest_points: List[Dict[str, Any]] = []
        table_rows: List[Dict[str, Any]] = []

        if not df_this_year.empty:
            baseline_year, last_year_revenue = _get_baseline_revenue_for_estimate(
                stock_id=stock_id,
                target_year=target_year,
                df_revenue=df,
            )
            newest_ytd_yoy = float(df_this_year["ytd_yoy(%)"].iat[-1])
            revenue_sum = float(df_this_year["revenue_ytd(bil)"].iat[-1])

            if last_year_revenue and last_year_revenue > 0:
                esti_revenue = last_year_revenue * (1 + newest_ytd_yoy / 100)
                revenue_achieve_rate = round(revenue_sum / esti_revenue * 100, 2) if esti_revenue else None

            # Chart: month-by-month
            chart_df = df_this_year[["date", "revenue_mon(bil)"]].copy().sort_values("date")
            latest_points = [
                {"date": d.strftime("%Y-%m-%d"), "revenue_mon_bil": _to_jsonable(v)}
                for d, v in zip(chart_df["date"], chart_df["revenue_mon(bil)"])
            ]

            # Table: last 2 years
            df_two_years = df[df["date"].dt.year >= target_year - 1].copy()
            display_df = df_two_years[
                ["date", "revenue_mon(bil)", "yoy(%)", "revenue_ytd(bil)", "ytd_yoy(%)"]
            ].copy()
            display_df = display_df.sort_values("date", ascending=True)
            table_rows = [
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "revenue_mon_bil": _to_jsonable(r),
                    "yoy_percent": _to_jsonable(y),
                    "revenue_ytd_bil": _to_jsonable(ry),
                    "ytd_yoy_percent": _to_jsonable(yy),
                }
                for d, r, y, ry, yy in zip(
                    display_df["date"],
                    display_df["revenue_mon(bil)"],
                    display_df["yoy(%)"],
                    display_df["revenue_ytd(bil)"],
                    display_df["ytd_yoy(%)"],
                )
            ]

        # Valuation metrics (optional; may fail if manual files incomplete)
        valuation: Optional[Dict[str, Any]] = None
        try:
            valuation = calculate_valuation(stock_id)
            valuation = _sanitize_dict(valuation)
        except Exception:
            valuation = None

        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "target_year": target_year,
            "metrics": {
                "baseline_year": baseline_year,
                "estimated_total_revenue": esti_revenue,
                "current_total_revenue": revenue_sum,
                "revenue_achieve_rate": revenue_achieve_rate,
            },
            "chart": {
                "points": latest_points,
            },
            "table_rows": table_rows,
            "valuation": valuation,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live-prices")
def get_live_prices(ids: str = Query(..., description="逗號分隔的股票代號，例如 2330,2881")) -> Dict[str, Any]:
    """Fetch live prices for multiple stocks concurrently."""
    import json
    from concurrent.futures import ThreadPoolExecutor, as_completed

    stock_ids = [s.strip() for s in ids.split(",") if s.strip()]

    def fetch_one(stock_id: str):
        symbol = f"{stock_id}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1m&range=1d"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return stock_id, float(price)
        except Exception:
            return stock_id, None

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_one, sid): sid for sid in stock_ids}
        for future in as_completed(futures):
            sid, price = future.result()
            if price is not None:
                results[sid] = price

    return {"prices": results}


@app.get("/api/live-price/{stock_id}")
def get_live_price(stock_id: str) -> Dict[str, Any]:
    """Proxy Yahoo Finance to avoid CORS issues in the browser."""
    import json
    symbol = f"{stock_id}.TW"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1m&range=1d"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return {"stock_id": stock_id, "price": float(price)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch live price: {e}")

import logging

# 設定 logging，方便在 Vercel Function Log 中查看除錯訊息
logger = logging.getLogger(__name__)


def clean_title_for_compare(title: str) -> str:
    """
    清洗新聞標題，只保留核心主題部分，用來提升去重的準確度。
    遇到 " - "、" | "、"_" 或 "(" 就從那裡截斷，只取前半段。
    例如：「台積電法說會重點 - 財經新聞」→「台積電法說會重點」
    """
    parts = re.split(r'\s*[-|_|(]', title)
    return parts[0].strip()


def get_special_keywords(title: str) -> set:
    """
    從標題中擷取「有意義的英文關鍵字」（長度 > 4），轉小寫方便比對。
    刻意過濾掉短字（如 AI、ETF、USD），避免這類通用詞彙造成誤判重複。
    例如：「Apple 營收創高」→ {'apple'}，而非 {'apple', 'ai'} 這類雜訊。
    """
    return {w for w in re.findall(r'[a-zA-Z]+', title.lower()) if len(w) > 4}


@app.get("/api/news/{stock_id}")
def get_stock_news(
    stock_id: str,
    response: Response,                  # FastAPI 依賴注入，用來設定回應 Header（如快取）
    name: str = Query(default=""),       # 可選的公司名稱，用來加強搜尋精準度
    days: int = Query(default=14),       # 搜尋幾天內的新聞，預設 14 天
) -> Dict[str, Any]:
    """
    透過 Google News RSS 抓取指定股票的相關新聞。
    支援黑名單過濾（技術分析類雜訊）、基礎去重與進階相似度去重。
    結果會由 Vercel Edge Cache 快取 5 分鐘，降低對 Google 的請求頻率。
    """

    # --- 1. 組合搜尋關鍵字 ---
    # 如果有提供公司名稱，使用 OR 邏輯同時搜尋代號與名稱，提高召回率
    if name:
        target = f'("{stock_id}" OR "{name}")'
    else:
        target = f'"{stock_id}"'

    # 可選：加入財經事件關鍵字過濾，只留下重大新聞（預設關閉）
    # key_events = "(營收 OR 財報 OR 法說會 OR 股利 OR 訂單 OR 漲停 OR 跌停)"
    # target = f'{target} {key_events}'

    # --- 2. 限定來源網站（台灣主流財經媒體）---
    sites = (
        "(site:moneydj.com OR site:money.udn.com OR site:ctee.com.tw OR site:cna.com.tw OR "
        "site:cnyes.com OR site:ec.ltn.com.tw OR site:tw.stock.yahoo.com OR "
        "site:businesstoday.com.tw OR site:wealth.com.tw OR site:technews.tw)"
    )

    # --- 3. 加入時間範圍過濾（when:Nd 代表最近 N 天）---
    time_filter = f"when:{days}d"

    # 組合最終送給 Google News RSS 的完整查詢字串
    query = f"{target} {sites} {time_filter}"

    rss_url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"})
    )

    try:
        req = urllib.request.Request(
            rss_url,
            # 使用完整的 Chrome User-Agent，降低被 Google 擋下的機率
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_bytes = resp.read()

        root = ET.fromstring(xml_bytes)
        channel = root.find("channel")
        if channel is None:
            return {"items": []}

        # --- 4. 黑名單過濾：排除技術分析類雜訊新聞 ---
        # 可依實際觀察到的雜訊標題隨時擴充這份清單
        blacklist = ["K線", "均線", "盤中速報", "技術面", "KD", "MACD", "黃金交叉", "死亡交叉"]

        items = []
        seen_titles: set = set()  # 第一道防線：完全相同標題直接跳過

        for item in channel.findall("item"):
            title = item.findtext("title") or ""

            # 過濾一：黑名單關鍵字檢查
            if any(bad_word in title for bad_word in blacklist):
                continue

            # 過濾二：完全相同標題去重
            if title in seen_titles:
                continue

            # 過濾三：進階相似度去重
            is_duplicate = False
            current_clean_title = clean_title_for_compare(title)
            current_keywords = get_special_keywords(current_clean_title)

            for existing_item in items:
                existing_clean_title = clean_title_for_compare(existing_item["title"])
                existing_keywords = get_special_keywords(existing_clean_title)

                # 條件 A：核心標題相似度超過 75%，視為同一則新聞
                similarity = difflib.SequenceMatcher(None, current_clean_title, existing_clean_title).ratio()
                if similarity > 0.75:
                    is_duplicate = True
                    break

                # 條件 B：標題中有相同的「有意義英文關鍵字」（長度 > 4），視為同一則新聞
                # 注意：AI、ETF 等短字已在 get_special_keywords 中濾除，不會誤觸此條件
                if current_keywords and (current_keywords & existing_keywords):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            # --- 5. 通過所有過濾，加入結果清單 ---
            link = item.findtext("link") or ""
            pub = item.findtext("pubDate") or ""
            source_el = item.find("source")
            source = source_el.text if source_el is not None else ""

            items.append({
                "title":   title,
                "link":    link,
                "pubDate": pub,
                "source":  source,
            })

            seen_titles.add(title)

            # 最多回傳 10 筆，避免回應過大
            if len(items) >= 10:
                break

        # --- 6. 設定 Vercel Edge Cache ---
        # s-maxage=300：Vercel CDN 快取 5 分鐘，同一時段的大量前端請求不會重複打爬蟲
        # stale-while-revalidate=60：快取過期後，背景更新期間仍先回傳舊快取，避免卡頓
        response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"

        return {"items": items}

    except Exception as e:
        # 使用 logger 記錄完整錯誤，可在 Vercel Dashboard → Functions → Logs 中查看
        logger.error("抓取新聞失敗 | stock_id=%s | url=%s | error=%s", stock_id, rss_url, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch news: {str(e)}")