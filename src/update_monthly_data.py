import os
import pandas as pd
import requests
from datetime import datetime

# 月營收

def update_revenue_data(stock_ids, base_dir="data"):
    """
    主要執行函數：傳入股票代號清單，一次更新所有月營收資料
    參數:
        stock_ids (list): 股票代號清單，例如 ["2881", "2882"]
        base_dir (str): 存檔的主資料夾名稱，預設為 "data"
    """
    # 1. 確保資料夾存在
    for sid in stock_ids:
        os.makedirs(os.path.join(base_dir, str(sid)), exist_ok=True)
        
    print(f"📢 準備更新月營收資料...")

    # 2. 只向官方請求「一次」全市場營收總表
    url = 'https://openapi.twse.com.tw/v1/opendata/t187ap05_L'
    try:
        resp = requests.get(url)
        resp.raise_for_status() 
        new_data = resp.json()
    except Exception as e:
        print(f"❌ 連線出錯: {e}")
        return

    df_new = pd.DataFrame(new_data)
    
    # 準備要保留與重新命名的欄位對照表
    rename_mapping = {
        '資料年月': 'date',
        '公司代號': 'stock_id',
        '公司名稱': 'name',
        '營業收入-當月營收': 'revenue_mon(bil)',
        '營業收入-去年同月增減(%)': 'yoy(%)',
        '累計營業收入-當月累計營收': 'revenue_ytd(bil)',
        '累計營業收入-前期比較增減(%)': 'ytd_yoy(%)'
    }
    
    # 只保留 API 有回傳的目標欄位，避免報錯
    available_columns = [col for col in rename_mapping.keys() if col in df_new.columns]
    
    # 3. 針對我們關注的股票清單，進行資料切割與存檔
    for sid in stock_ids:
        sid_str = str(sid)
        file_path = os.path.join(base_dir, sid_str, f"{sid_str}_revenue.csv")
        
        # 從總表濾出單一股票的當月資料
        df_target = df_new.loc[df_new['公司代號'] == sid_str, available_columns].copy()
        
        if df_target.empty:
            print(f"⚠️ 警告：證交所 API 目前找不到 {sid_str} 的最新營收資料！")
            continue # 跳過這檔，繼續跑下一檔
            
        # 重新命名欄位
        df_target.rename(columns=rename_mapping, inplace=True)

        # 數值轉換 (除以 1e5 轉成億)
        df_target['revenue_mon(bil)'] = pd.to_numeric(df_target['revenue_mon(bil)'], errors='coerce') / 1e5
        df_target['yoy(%)'] = pd.to_numeric(df_target['yoy(%)'], errors='coerce')
        df_target['revenue_ytd(bil)'] = pd.to_numeric(df_target['revenue_ytd(bil)'], errors='coerce') / 1e5
        df_target['ytd_yoy(%)'] = pd.to_numeric(df_target['ytd_yoy(%)'], errors='coerce')

        # 日期轉換 (民國年月 -> 西元年-月-01)
        raw_date = str(df_target['date'].iloc[0])
        year = int(raw_date[:-2]) + 1911  
        month = raw_date[-2:]             
        df_target['date'] = f"{year}-{month}-01"

        # 讀取舊資料並合併
        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            # 利用 date 去重複 (keep='last')，確保當月資料若有更新能成功覆蓋
            df_final = pd.concat([df_old, df_target], ignore_index=True).drop_duplicates(subset=['date'], keep='last')
        else:
            df_final = df_target

        # 統一日期格式
        df_final['date'] = pd.to_datetime(df_final['date'], format='mixed').dt.strftime('%Y-%m-%d')
        
        # 存檔
        df_final.to_csv(file_path, index=False)
        print(f"✅ [{sid_str}] 營收資料存檔成功")

# ================= 當作主程式單獨執行時 =================
if __name__ == "__main__":
    my_stocks = ["2881", "2882", "2883", "2884", "2885", "2887", "2890", "2891", "2892"]
    my_dir = "data"
    
    print(f"=== 開始執行台股月營收資料更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    update_revenue_data(stock_ids=my_stocks, base_dir=my_dir)
    print("=== 全部營收更新完畢 ===")