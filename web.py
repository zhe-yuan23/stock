import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定 (標題、寬度)
st.set_page_config(page_title="台股營收追蹤", layout="wide")
st.title("📈 台股營收追蹤儀表板")

# 2. 側邊欄：選擇股票
stock_ids = ["2882"]
selected_stock = st.sidebar.selectbox("請選擇要查看的股票代號", stock_ids)

# 3. 讀取與分析資料
try:
    # 讀取後台自動更新好的 CSV
    df = pd.read_csv(f"{selected_stock}_revenue.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    today = datetime.now()
    
    # 計算邏輯
    df_last_year = df[df['date'].dt.year == today.year - 1]
    last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
    
    df_this_year = df[df["date"].dt.year == today.year] 
    
    if not df_this_year.empty:
        newest_yoy = df_this_year['yoy'].iat[-1]
        esti_revenue = last_year_revenue * (1 + newest_yoy) 
        revenue_sum = df_this_year['revenue_mon(bil)'].sum()
        revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)

        # --- 以下是網頁視覺化呈現 ---
        st.subheader(f"📊 {selected_stock} 營收進度總覽")
        col1, col2, col3 = st.columns(3)
        col1.metric(label="推估今年總營收", value=f"{esti_revenue:,.2f} 億")
        col2.metric(label=f"{today.year}年目前總營收", value=f"{revenue_sum:,.2f} 億")
        col3.metric(label="目前達成率", value=f"{revenue_achie_rate} %")

        st.markdown("---")

        # 區塊 B：折線圖與資料表並排顯示
        col_chart, col_table = st.columns([2, 1]) 
        
        with col_chart:
            st.markdown("### 📈 每月營收趨勢圖")
            chart_data = df_this_year[['date', 'revenue_mon(bil)']].set_index('date')
            st.line_chart(chart_data)

        with col_table:
            st.markdown("### 📋 每月詳細數據")
            display_df = df_this_year[['date', 'revenue_mon(bil)', 'yoy']].copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            st.dataframe(display_df, hide_index=True)

    else:
        st.warning(f"目前還沒有 {today.year} 年的營收資料喔！")

except FileNotFoundError:
    st.error(f"找不到 {selected_stock}_revenue.csv！請確認後台資料有正確產生。")