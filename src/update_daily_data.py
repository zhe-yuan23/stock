import os
import requests
import pandas as pd
from datetime import datetime
import time

DEFAULT_CONNECT_TIMEOUT_S = float(os.getenv("STOCK_API_CONNECT_TIMEOUT_S", "10"))
DEFAULT_READ_TIMEOUT_S = float(os.getenv("STOCK_API_READ_TIMEOUT_S", "60"))
DEFAULT_MAX_RETRIES = int(os.getenv("STOCK_API_MAX_RETRIES", "4"))
DEFAULT_BACKOFF_BASE_S = float(os.getenv("STOCK_API_BACKOFF_BASE_S", "1.0"))


def _http_get_json(
    url: str,
    *,
    timeout=(DEFAULT_CONNECT_TIMEOUT_S, DEFAULT_READ_TIMEOUT_S),
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
):
    """
    GitHub Actions 偶發網路抖動時，TWSE OpenAPI 可能會連線逾時。
    這裡用顯式 timeout + 重試(指數退避)讓更新更穩定。
    """
    headers = {
        "User-Agent": "stock_api/1.0 (+https://github.com)",
        "Accept": "application/json, text/json, */*",
    }

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(
                    f"HTTP {resp.status_code} from {url}", response=resp
                )
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_exc = e
            if attempt >= max_retries:
                break
            sleep_s = backoff_base_s * (2 ** (attempt - 1))
            print(f"⚠️ 連線不穩定，{attempt}/{max_retries} 失敗，{sleep_s:.1f}s 後重試：{e}")
            time.sleep(sleep_s)

    raise last_exc

# 股價
# 殖利率/本益比/淨值比
# 發行股數...

def get_real_latest_trading_date():
    """向官方大盤 API 查詢最近一個真實的交易日期"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
    try:
        data = _http_get_json(url)
        latest_record = data[-1]
        roc_date_str = latest_record['Date'] 
        year = int(roc_date_str[:-4]) + 1911
        month = roc_date_str[-4:-2]
        day = roc_date_str[-2:]
        return f"{year}-{month}-{day}"
    except Exception as e:
        print(f"⚠️ 抓取大盤日期失敗: {e}，改用當天日期")
        return datetime.today().strftime('%Y-%m-%d')

def safe_float(val):
    try:
        if not val or str(val).strip() in ["", "-"]:
            return 0.0
        return float(val)
    except ValueError:
        return 0.0

def update_daily_data(stock_ids, base_dir="data"):
    """
    主要執行函數：傳入股票代號清單，一次更新所有每日盤後資料
    參數:
        stock_ids (list): 股票代號清單，例如 ["2881", "2882"]
        base_dir (str): 存檔的主資料夾名稱，預設為 "data"
    """
    # 1. 確保資料夾存在
    for sid in stock_ids:
        os.makedirs(os.path.join(base_dir, str(sid)), exist_ok=True)
        
    trading_date = get_real_latest_trading_date()
    print(f"📢 準備更新每日資料，交易日為：{trading_date}")

    # ================= 抓取股價 =================
    try:
        print("正在抓取並更新股價...")
        data = _http_get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
        df = pd.DataFrame(data)
        df_target = df[df['Code'].isin(stock_ids)].copy()
        
        for _, row in df_target.iterrows():
            sid = row['Code']
            file_path = os.path.join(base_dir, str(sid), f"{sid}_price.csv")
            price = float(row['ClosingPrice']) if row['ClosingPrice'] else 0.0
            
            df_save = pd.DataFrame([{'Date': trading_date, 'stock_id': sid, 'name': row.get('Name', ''), 'price': price}])
            if os.path.exists(file_path):
                df_old = pd.read_csv(file_path)
                df_save = pd.concat([df_old, df_save], ignore_index=True).drop_duplicates(subset=['Date'], keep='last')
            df_save = df_save.sort_values(by='Date', ascending=True)
            df_save.to_csv(file_path, index=False)
        print("✅ 股價存檔完成！")
    except Exception as e:
        print(f"❌ 股價更新失敗: {e}")

    # ================= 抓取估值 =================
    try:
        print("正在抓取並更新估值(殖利率/本益比/淨值比)...")
        data = _http_get_json("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")
        df = pd.DataFrame(data)
        df_target = df[df['Code'].isin(stock_ids)].copy()
        
        for _, row in df_target.iterrows():
            sid = row['Code']
            file_path = os.path.join(base_dir, str(sid), f"{sid}_valuation.csv")
            
            df_save = pd.DataFrame([{
                'Date': trading_date, 
                'stock_id': sid, 
                'name': row.get('Name', ''), 
                'Yield(%)': safe_float(row.get('DividendYield')), # 殖利率
                'PE_Ratio': safe_float(row.get('PEratio')), # 本益比
                'PB_Ratio': safe_float(row.get('PBratio'))  # 淨值比
            }])
            if os.path.exists(file_path):
                df_old = pd.read_csv(file_path)
                df_save = pd.concat([df_old, df_save], ignore_index=True).drop_duplicates(subset=['Date'], keep='last')
            df_save = df_save.sort_values(by='Date', ascending=True)
            df_save.to_csv(file_path, index=False)
        print("✅ 估值資料存檔完成！")
    except Exception as e:
        print(f"❌ 估值更新失敗: {e}")

    # ================= 抓取發行股數 =================
    try:
        print("正在抓取並更新發行股數...")
        data = _http_get_json("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
        df = pd.DataFrame(data)
        df_target = df[df['公司代號'].isin(stock_ids)].copy()
        
        for _, row in df_target.iterrows():
            sid = row['公司代號']
            file_path = os.path.join(base_dir, str(sid), f"{sid}_basic_info.csv")
            try:
                raw_str = str(row.get('已發行普通股數或TDR原股發行股數', '0')).replace(',', '').strip()
                clean_str = '0' if not raw_str or raw_str == '-' else raw_str
                shares = float(clean_str) / 100000000
            except:
                shares = 0.0
                
            df_save = pd.DataFrame([{'stock_id': sid, 'name': row.get('公司名稱', ''), 'shares_outstanding(億股)': round(shares, 2)}])
            df_save.to_csv(file_path, index=False)
        print("✅ 發行股數存檔完成！")
    except Exception as e:
        print(f"❌ 股數更新失敗: {e}")


# ================= 抓取加權指數 =================
def update_taiex_data(base_dir="data"):
    """
    從 TWSE 官方 MI_INDEX API 抓取加權指數收盤價，
    累積存至 data/taiex/taiex_price.csv。
    後端可讀此檔計算歷史最高點與 drawdown。
    """
    taiex_dir = os.path.join(base_dir, "taiex")
    os.makedirs(taiex_dir, exist_ok=True)
    file_path = os.path.join(taiex_dir, "taiex_price.csv")

    try:
        print("正在抓取並更新加權指數...")
        trading_date = get_real_latest_trading_date()
        data = _http_get_json("https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX")

        # 找出「發行量加權股價指數」那一筆
        taiex_row = next(
            (row for row in data if row.get("指數") == "發行量加權股價指數"),
            None
        )
        if taiex_row is None:
            print("⚠️ 找不到加權指數資料，略過。")
            return

        close_str = taiex_row.get("收盤指數", "").replace(",", "").strip()
        if not close_str or close_str == "-":
            print("⚠️ 加權指數收盤值為空，略過。")
            return

        close = float(close_str)
        df_save = pd.DataFrame([{"date": trading_date, "close": close}])

        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            df_save = pd.concat([df_old, df_save], ignore_index=True).drop_duplicates(subset=["date"], keep="last")

        df_save = df_save.sort_values(by="date", ascending=True)
        df_save.to_csv(file_path, index=False)
        print(f"✅ 加權指數存檔完成！{trading_date} 收盤：{close:.2f}")

    except Exception as e:
        print(f"❌ 加權指數更新失敗: {e}")


# ================= 當作主程式單獨執行時 =================
if __name__ == "__main__":
    my_stocks = ["2881", "2882", "2883", "2884", "2885", "2887", "2890", "2891", "2892"]
    my_dir = "data"
    
    print(f"=== 開始執行台股每日資料更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    update_daily_data(stock_ids=my_stocks, base_dir=my_dir)
    update_taiex_data(base_dir=my_dir)
    print("=== 全部品項更新完畢 ===")
