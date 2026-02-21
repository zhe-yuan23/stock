import streamlit as st
import pandas as pd
from datetime import datetime
import os

# 1. 網頁基本設定 (標題、寬度)
st.set_page_config(page_title="台股營收追蹤", layout="wide")

# ==========================================
# 區塊 A：側邊欄導覽列與自動掃描資料夾
# ==========================================
st.sidebar.title("導覽選單")
page = st.sidebar.radio("請選擇頁面", ["🏠 總覽首頁", "📈 個股詳細資料"])
st.sidebar.markdown("---")

# 自動掃描 data 資料夾下的所有 CSV 檔
try:
    data_files = [f for f in os.listdir("data") if f.endswith("_revenue.csv")]
    stock_list = sorted([f.split("_")[0] for f in data_files])
except FileNotFoundError:
    st.error("找不到 data 資料夾，請確認路徑。")
    stock_list = []

# 建立顯示用的標籤 (預設先用代號)
stock_display = {}
for sid in stock_list:
    try:
        temp_df = pd.read_csv(f"data/{sid}_revenue.csv", nrows=1)
        name = temp_df['name'].iloc[0] if 'name' in temp_df.columns else "未知"
        stock_display[sid] = name
    except:
        stock_display[sid] = "讀取失敗"

# ==========================================
# 區塊 B：🏠 總覽首頁
# ==========================================
if page == "🏠 總覽首頁":
    st.title("🏠 台股營收達成率總覽")
    
    if not stock_list:
        st.warning("目前沒有任何股票資料。")
    else:
        summary_data = []
        today = datetime.now()
        
        for sid in stock_list:
            try:
                df = pd.read_csv(f"data/{sid}_revenue.csv")
                df["date"] = df["date"].astype(str).str.replace("/", "-")
                df["date"] = pd.to_datetime(df["date"])
                
                df_last_year = df[df['date'].dt.year == today.year - 1]
                last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
                
                df_this_year = df[df["date"].dt.year == today.year]
                
                if not df_this_year.empty and last_year_revenue > 0:
                    newest_yoy = df_this_year['yoy%'].iat[-1]
                    esti_revenue = last_year_revenue * (1 + newest_yoy/100)
                    revenue_sum = df_this_year['revenue_mon(bil)'].sum()
                    revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)
                    
                    stock_name = stock_display.get(sid, "")
                    
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        "目前達成率 (%)": f"{revenue_achie_rate} % "
                    })
            except Exception as e:
                continue
                
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            # 依達成率由高到低排序
            summary_df = summary_df.sort_values("目前達成率 (%)", ascending=False)
            st.write(f"### {today.year} 年度營收目標達成進度")
            st.dataframe(summary_df, hide_index=True, use_container_width=True)
        else:
            st.info("尚無足夠資料計算達成率（需有去年整年及今年資料）。")

# ==========================================
# 區塊 C：📈 個股詳細資料
# ==========================================
elif page == "📈 個股詳細資料":
    st.title("📈 個股營收追蹤")
    
    # 側邊欄選單 (只在個股詳細資料頁面顯示)
    selected_stock = st.sidebar.selectbox(
        "請選擇要查看的股票",
        options=stock_list,
        format_func=lambda x: f"{x} {stock_display.get(x, '')}"
    )

    try:
        df = pd.read_csv(f"data/{selected_stock}_revenue.csv")
        stock_name = df['name'].iloc[0] if 'name' in df.columns else ""

        df["date"] = df["date"].astype(str).str.replace("/", "-")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        today = datetime.now()
        
        df_last_year = df[df['date'].dt.year == today.year - 1]
        last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
        
        df_this_year = df[df["date"].dt.year == today.year] 
        
        if not df_this_year.empty:
            newest_yoy = df_this_year['yoy%'].iat[-1]
            esti_revenue = last_year_revenue * (1 + newest_yoy/100) 
            revenue_sum = df_this_year['revenue_mon(bil)'].sum()
            revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)

            st.subheader(f"📊 {selected_stock} {stock_name} 營收進度")
            col1, col2, col3 = st.columns(3)
            col1.metric(label="推估今年總營收", value=f"{esti_revenue:,.2f} 億")
            col2.metric(label=f"{today.year}年目前總營收", value=f"{revenue_sum:,.2f} 億")
            col3.metric(label="目前達成率", value=f"{revenue_achie_rate} %")

            st.markdown("---")

            col_chart, col_table = st.columns([2, 1]) 
            
            with col_chart:
                st.markdown("### 📈 月營收趨勢圖")
                chart_data = df_this_year[['date', 'revenue_mon(bil)']].set_index('date')
                st.line_chart(chart_data)

            with col_table:
                st.markdown("### 📋 每月詳細數據")
                display_df = df_this_year[['date', 'revenue_mon(bil)', 'yoy%']].copy()
                display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                st.dataframe(display_df, hide_index=True)
        else:
            st.warning(f"目前還沒有 {today.year} 年的營收資料喔！")

    except FileNotFoundError:
        st.error(f"找不到 {selected_stock}_revenue.csv！")