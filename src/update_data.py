import os
import pandas as pd
import requests
from datetime import datetime
import numpy as np

def update(stock_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "..", "data", f"{stock_id}_revenue.csv")

    # 讀 CSV
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        # 統一將日期轉為 datetime 物件，方便 should_update 判斷
        df["date"] = pd.to_datetime(df["date"], errors='coerce')
    else:
        df = pd.DataFrame()

    def should_update(df):
        if df.empty:
            return True
        last_row = df.sort_values("date").iloc[-1]
        last_year = last_row["date"].year
        last_month = last_row["date"].month

        today = datetime.today()
        current_year = today.year
        current_month = today.month

        # 維持你原本的判斷邏輯
        return not (last_year == current_year and last_month == current_month-1)

    if not should_update(df):
        # 維持原本訊息
        print(f"{stock_id} 本月資料已存在，不需要更新")
    else:
        url = 'https://openapi.twse.com.tw/v1/opendata/t187ap05_L'
        try:
            resp = requests.get(url)
            # 確保 API 請求成功
            resp.raise_for_status() 
            new_data = resp.json()
        except Exception as e:
            print(f"連線出錯: {e}")
            return

        df_new = pd.DataFrame(new_data)
        df_new = df_new.loc[df_new['公司代號'] == stock_id, ['資料年月', '公司代號', '公司名稱', '營業收入-當月營收', '營業收入-去年同月增減(%)']]
        
        # 維持原本訊息
        if df_new.empty:
            print(f"⚠️ 警告：證交所 API (上市公司) 目前找不到 {stock_id} 的最新營收資料！")
            print("可能是 ETF、上櫃公司，或公司尚未公布。跳過此檔股票。")
            return
        
        df_new.columns = ['date', 'stock_id', 'name', 'revenue_mon(bil)', 'yoy%']

        # 數值轉換
        df_new['revenue_mon(bil)'] = pd.to_numeric(df_new['revenue_mon(bil)'], errors='coerce') / 1e5
        # yoy% 也轉成數字，避免後續計算出錯
        df_new['yoy%'] = pd.to_numeric(df_new['yoy%'], errors='coerce')

        # 民國轉西元
        raw_date = df_new['date'].iloc[0] 
        year = int(raw_date[:-2]) + 1911  
        month = raw_date[-2:]             
        clean_date = f"{year}-{month}-01"
        df_new['date'] = clean_date

        # 合併邏輯修正：讀取舊資料並與新資料合併
        # 注意：我們使用 drop_duplicates 確保同月份不重複
        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            df_final = pd.concat([df_new, df_old], ignore_index=True).drop_duplicates(subset=['date'])
        else:
            df_final = df_new

        # 確保存檔時日期格式整齊，不含分秒
        df_final['date'] = pd.to_datetime(df_final['date'], format='mixed').dt.strftime('%Y-%m-%d')
        
        # 自動建立資料夾並存檔
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df_final.to_csv(file_path, index=False)
        # 這裡可以補一個你想要的成功訊息
        print(f"{stock_id} 資料存檔成功")