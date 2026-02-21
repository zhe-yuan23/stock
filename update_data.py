import os
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np

# 需存入預設資料 (date,stock_id,revenue_mon(bil),yoy,name)
# 檔名 stock_id_revenue.csv

def update(stock_id):
    file_name = f"{stock_id}_revenue.csv"

    # 讀 CSV
    if os.path.exists(file_name):
        df = pd.read_csv(file_name)
        df["date"] = pd.to_datetime(df["date"])
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

        # 如果最後一筆資料是「最新月份」就不用更新
        return not (last_year == current_year and last_month == current_month-1)
    # 判斷
    if not should_update(df):
        print(f"{stock_id} 本月資料已存在，不需要更新")
    else:
        url = 'https://openapi.twse.com.tw/v1/opendata/t187ap05_L'
        # 上市公司每月營業收入彙總表
        resp = requests.get(url)
        new_data = resp.json()
        df_new = pd.DataFrame(new_data)
        df_new = df_new.loc[df_new['公司代號'] == stock_id, ['資料年月', '公司代號', '公司名稱', '營業收入-當月營收', '營業收入-去年同月增減(%)']]
        df_new.columns = ['date', 'stock_id', 'name', 'revenue_mon(bil)', 'yoy']

        #先把欄位轉換成數字型態 (errors='coerce' 會把髒資料轉成空值，比較安全)
        cols = ['revenue_mon(bil)']

        # 使用 apply 讓 pd.to_numeric 逐欄執行
        df_new[cols] = df_new[cols].apply(pd.to_numeric, errors='coerce')
        df_new['revenue_mon(bil)'] = df_new['revenue_mon(bil)']/1e5

        # 民國轉西元
        raw_date = df_new['date'].iloc[0] 
        year = int(raw_date[:-2]) + 1911  # 切出 115 並轉 2026
        month = raw_date[-2:]             # 切出 01
        clean_date = f"{year}-{month}-01"
        df_new['date'] = clean_date
        # 上年度營收
        # initial_input = input(f"請輸入{stock_id}去年營收 (格式: yyyy-mm-dd, revenue): ")
        # data_list = [x.strip() for x in initial_input.split(',')]
        # if len(data_list) == 2:
        #     initial_row = pd.DataFrame({
        #         'date': [data_list[0]],
        #         'stock_id': stock_id,
        #         'revenue_mon(bil)': [float(data_list[1])],
        #         'yoy': [np.nan],
        #         'name':[np.nan]
        #     })
            
            # 轉換日期格式
        #     initial_row['date'] = pd.to_datetime(initial_row['date']).dt.strftime('%Y-%m-%d')
        #     print("success")
        #     print(initial_row)
        # else:
        #     print("error")
        
        # if not os.path.exists(file_name):
        #     print(f"{stock_id} 沒有本地資料，開始完整下載")
        #     df_final = pd.concat([initial_row, df_new])
        # else:
        #     df_old = pd.read_csv(file_name)
        #     df_final = pd.concat([df_old,df_new])

        df_old = pd.read_csv(file_name)
        df_final = pd.concat([df_old,df_new])   
        df_final.to_csv(file_name, index=False)
    