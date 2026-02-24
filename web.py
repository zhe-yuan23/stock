import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt

st.set_page_config(page_title="台股營收追蹤", layout="wide")

# ==========================================
# 區塊 A：側邊欄導覽列與自動掃描資料夾
# ==========================================
st.sidebar.title("導覽選單")
page = st.sidebar.radio("請選擇頁面", ["🏠 總覽首頁", "📈 個股詳細資料"])
st.sidebar.markdown("---")

# 🌟 修改掃描邏輯：改為抓取 data 目錄下的所有「子資料夾名稱」
try:
    stock_list = sorted([d for d in os.listdir("data") if os.path.isdir(os.path.join("data", d))])
except FileNotFoundError:
    st.error("找不到 data 資料夾，請確認路徑。")
    stock_list = []

stock_display = {}
for sid in stock_list:
    try:
        # 🌟 修改讀取路徑
        temp_df = pd.read_csv(f"data/{sid}/{sid}_revenue.csv", nrows=1)
        name = temp_df['name'].iloc[0] if 'name' in temp_df.columns else "未知"
        stock_display[sid] = name
    except:
        stock_display[sid] = "讀取失敗"

# ==========================================
# 區塊 B：🏠 總覽首頁
# ==========================================
if page == "🏠 總覽首頁":
    st.title("台股營收達成率總覽")
    
    if not stock_list:
        st.warning("目前沒有任何股票資料。")
    else:
        summary_data = []
        
        all_years = []
        for sid in stock_list:
            try:
                # 🌟 修改讀取路徑
                temp_df = pd.read_csv(f"data/{sid}/{sid}_revenue.csv")
                temp_df["date"] = temp_df["date"].astype(str).str.replace("/", "-")
                temp_df["date"] = pd.to_datetime(temp_df["date"])
                all_years.append(temp_df['date'].dt.year.max())
            except:
                pass
        
        global_target_year = max(all_years) if all_years else datetime.now().year
        
        for sid in stock_list:
            try:
                # 🌟 修改讀取路徑
                df = pd.read_csv(f"data/{sid}/{sid}_revenue.csv")
                df["date"] = df["date"].astype(str).str.replace("/", "-")
                df["date"] = pd.to_datetime(df["date"])
                
                df_last_year = df[df['date'].dt.year == global_target_year - 1]
                last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
                
                df_this_year = df[df["date"].dt.year == global_target_year]
                stock_name = stock_display.get(sid, "")
                
                if not df_this_year.empty and last_year_revenue > 0:
                    newest_ytd_yoy = df_this_year['ytd_yoy(%)'].iat[-1]
                    esti_revenue = last_year_revenue * (1 + newest_ytd_yoy/100)
                    revenue_sum = df_this_year['revenue_ytd(bil)'].iat[-1]
                    revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)
                    
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        "排序數值": revenue_achie_rate, 
                        "目前達成率 (%)": f"{revenue_achie_rate} %"
                    })
                else:
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        "排序數值": -1.0, 
                        "目前達成率 (%)": "尚未公布"
                    })
            except Exception as e:
                continue
                
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values("排序數值", ascending=False)
            summary_df = summary_df.drop(columns=["排序數值"])
            
            st.write(f"### {global_target_year} 年度營收目標達成進度")
            st.dataframe(summary_df, hide_index=True, use_container_width=True)
        else:
            st.info("尚無足夠資料計算達成率。")

# ==========================================
# 區塊 C：📈 個股詳細資料
# ==========================================
elif page == "📈 個股詳細資料":
    st.title("個股營收追蹤")
    
    selected_stock = st.sidebar.selectbox(
        "請選擇要查看的股票",
        options=stock_list,
        format_func=lambda x: f"{x} {stock_display.get(x, '')}"
    )

    try:
        # 🌟 修改讀取路徑
        df = pd.read_csv(f"data/{selected_stock}/{selected_stock}_revenue.csv")
        stock_name = df['name'].iloc[0] if 'name' in df.columns else ""

        df["date"] = df["date"].astype(str).str.replace("/", "-")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        target_year = df['date'].dt.year.max()

        df_last_year = df[df['date'].dt.year == target_year - 1]
        last_year_revenue = df_last_year['revenue_mon(bil)'].sum()

        df_this_year = df[df["date"].dt.year == target_year] 

        if not df_this_year.empty:
            newest_ytd_yoy = df_this_year['ytd_yoy(%)'].iat[-1]
            esti_revenue = last_year_revenue * (1 + newest_ytd_yoy/100) 
            revenue_sum = df_this_year['revenue_ytd(bil)'].iat[-1]
            revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)

            st.subheader(f"📊 {selected_stock} {stock_name} 營收進度")
            col1, col2, col3 = st.columns(3)
            col1.metric(label=f"推估 {target_year} 年總營收", value=f"{esti_revenue:,.2f} 億")
            col2.metric(label=f"{target_year} 年目前總營收", value=f"{revenue_sum:,.2f} 億") 
            col3.metric(label="目前達成率", value=f"{revenue_achie_rate} %")

            st.markdown("---")

            col_chart, col_table = st.columns([2, 1]) 
            
            with col_chart:
                st.markdown("### 📈 月營收趨勢圖")
                chart = alt.Chart(df_this_year).mark_line(point=True).encode(
                    x=alt.X('date:T', title='日期'),
                    y=alt.Y('revenue_mon(bil):Q', title='', scale=alt.Scale(zero=True))
                ).properties(
                    height=350 
                )
                st.altair_chart(chart, use_container_width=True)                

            with col_table:
                st.markdown(f"### 📋 近二年詳細數據")
                
                df_two_years = df[df['date'].dt.year >= target_year - 1].copy()
                
                display_df = df_two_years[['date', 'revenue_mon(bil)', 'yoy(%)', 'revenue_ytd(bil)', 'ytd_yoy(%)']].copy()
                display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                
                display_df = display_df.sort_values("date", ascending=False)
                
                display_df = display_df.rename(columns={
                    "date": "日期",
                    "revenue_mon(bil)": "月營收 (億)",
                    "yoy(%)": "單月年增率 (%)",
                    "revenue_ytd(bil)": "累計營收 (億)",
                    "ytd_yoy(%)": "累計年增率 (%)"
                })

                st.dataframe(
                    display_df, 
                    hide_index=True, 
                    use_container_width=True,
                    selection_mode="disabled"  
                )
        else:
            st.warning(f"目前還沒有 {target_year} 年的營收資料喔！")

    except FileNotFoundError:
        st.error(f"找不到 {selected_stock}_revenue.csv！")