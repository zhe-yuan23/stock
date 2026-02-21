import update_data
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 更新資料
stock_ids = ["2882"]
for stock_id in stock_ids:
    file_name = f"{stock_id}_revenue.csv"
    update_data.update(stock_id)


# Analyze
today = datetime.now()
for stock_id in stock_ids:
    df = pd.read_csv(f"{stock_id}_revenue.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    df_last_year = df[df['date'].dt.year == today.year - 1]
    last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
    df_this_year = df[df["date"].dt.year == today.year] 
    newest_yoy = df_this_year['yoy'].iat[-1]
    esti_revenue = last_year_revenue * (1+newest_yoy) # 推估今年營收
    revenue_sum = df_this_year['revenue_mon(bil)'].sum()
    revenue_achie_rate = (revenue_sum/esti_revenue*100).round(2)

    print("=====================" + f"{stock_id}_revenue.csv" + "=====================") 
    print(df_this_year)    
    print(f"推估今年營收：{esti_revenue}" + ' 億')
    print(f'{today.year}年總營收：'+(revenue_sum).astype(str) + ' 億')
    print(f"達成率：{revenue_achie_rate}" + '%\n')