import os
import pandas as pd
import requests
from datetime import datetime

def update_revenue(stock_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 🌟 修改這裡：在 data 與檔名之間，加入 str(stock_id) 作為獨立資料夾
    file_path = os.path.join(current_dir, "..", "data", str(stock_id), f"{stock_id}_revenue.csv")

    # 讀 CSV
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
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

        return not (last_year == current_year and last_month == current_month-1)

    if not should_update(df):
        print(f"{stock_id} 本月資料已存在，不需要更新")
    else:
        url = 'https://openapi.twse.com.tw/v1/opendata/t187ap05_L'
        try:
            resp = requests.get(url)
            resp.raise_for_status() 
            new_data = resp.json()
        except Exception as e:
            print(f"連線出錯: {e}")
            return

        df_new = pd.DataFrame(new_data)
        
        target_columns = [
            '資料年月', '公司代號', '公司名稱', 
            '營業收入-當月營收', '營業收入-去年同月增減(%)',
            '累計營業收入-當月累計營收', '累計營業收入-前期比較增減(%)' 
        ]
        
        available_columns = [col for col in target_columns if col in df_new.columns]
        df_new = df_new.loc[df_new['公司代號'] == str(stock_id), available_columns]
        
        if df_new.empty:
            print(f"⚠️ 警告：證交所 API 目前找不到 {stock_id} 的最新營收資料！")
            return
        
        df_new.columns = ['date', 'stock_id', 'name', 'revenue_mon(bil)', 'yoy(%)', 'revenue_ytd(bil)', 'ytd_yoy(%)']

        df_new['revenue_mon(bil)'] = pd.to_numeric(df_new['revenue_mon(bil)'], errors='coerce') / 1e5
        df_new['yoy(%)'] = pd.to_numeric(df_new['yoy(%)'], errors='coerce')
        df_new['revenue_ytd(bil)'] = pd.to_numeric(df_new['revenue_ytd(bil)'], errors='coerce') / 1e5
        df_new['ytd_yoy(%)'] = pd.to_numeric(df_new['ytd_yoy(%)'], errors='coerce')

        raw_date = df_new['date'].iloc[0] 
        year = int(raw_date[:-2]) + 1911  
        month = raw_date[-2:]             
        clean_date = f"{year}-{month}-01"
        df_new['date'] = clean_date

        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            df_final = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=['date'])
        else:
            df_final = df_new

        df_final['date'] = pd.to_datetime(df_final['date'], format='mixed').dt.strftime('%Y-%m-%d')
        
        # 這裡會自動建立該檔股票的資料夾
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df_final.to_csv(file_path, index=False)
        print(f"{stock_id} 資料存檔成功 (已建立獨立資料夾)")