import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


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
        try:
            valuation_result = calculate_valuation(sid)
            price_volatility = valuation_result.get("price_volatility")
            current_price = valuation_result.get("current_price")
            band_low = valuation_result.get("band_low")
            band_mid = valuation_result.get("band_mid")
            band_high = valuation_result.get("band_high")
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

