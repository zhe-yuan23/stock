import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt

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
    st.title("台股營收達成率總覽")
    
    if not stock_list:
        st.warning("目前沒有任何股票資料。")
    else:
        summary_data = []
        
        # 1. 掃描所有資料，決定「全域最新年份」 (例如現在會抓到 2026)
        all_years = []
        for sid in stock_list:
            try:
                temp_df = pd.read_csv(f"data/{sid}_revenue.csv")
                temp_df["date"] = temp_df["date"].astype(str).str.replace("/", "-")
                temp_df["date"] = pd.to_datetime(temp_df["date"])
                all_years.append(temp_df['date'].dt.year.max())
            except:
                pass
        
        # 決定全表統一比較的年份
        global_target_year = max(all_years) if all_years else datetime.now().year
        
        # 2. 開始計算每檔股票在 global_target_year 的表現
        for sid in stock_list:
            try:
                df = pd.read_csv(f"data/{sid}_revenue.csv")
                df["date"] = df["date"].astype(str).str.replace("/", "-")
                df["date"] = pd.to_datetime(df["date"])
                
                df_last_year = df[df['date'].dt.year == global_target_year - 1]
                last_year_revenue = df_last_year['revenue_mon(bil)'].sum()
                
                df_this_year = df[df["date"].dt.year == global_target_year]
                stock_name = stock_display.get(sid, "")
                
                # 如果該公司今年已經有資料
                if not df_this_year.empty and last_year_revenue > 0:
                    newest_yoy = df_this_year['yoy%'].iat[-1]
                    esti_revenue = last_year_revenue * (1 + newest_yoy/100)
                    revenue_sum = df_this_year['revenue_mon(bil)'].sum()
                    revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)
                    
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        "排序數值": revenue_achie_rate, # 這個隱藏欄位只用來純數字排序
                        "目前達成率 (%)": f"{revenue_achie_rate} %"
                    })
                # 如果該公司今年還沒有資料 (還沒公布)
                else:
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        "排序數值": -1.0, # 給一個負數，讓它在排序時墊底
                        "目前達成率 (%)": "尚未公布"
                    })
            except Exception as e:
                continue
                
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            
            # 3. 依照「排序數值」由高到低進行真正的數學排序
            summary_df = summary_df.sort_values("排序數值", ascending=False)
            
            # 排序完後，把這個用不到的工具欄位刪掉，保持畫面乾淨
            summary_df = summary_df.drop(columns=["排序數值"])
            
            st.write(f"### {global_target_year} 年度營收目標達成進度")
            st.table(summary_df)
        else:
            st.info("尚無足夠資料計算達成率。")

# ==========================================
# 區塊 C：📈 個股詳細資料
# ==========================================
elif page == "📈 個股詳細資料":
    st.title("個股營收追蹤")
    
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

        # 取得這檔股票最新的財報年份
        target_year = df['date'].dt.year.max()

        df_last_year = df[df['date'].dt.year == target_year - 1]
        last_year_revenue = df_last_year['revenue_mon(bil)'].sum()

        df_this_year = df[df["date"].dt.year == target_year] 

        if not df_this_year.empty:
            newest_yoy = df_this_year['yoy%'].iat[-1]
            esti_revenue = last_year_revenue * (1 + newest_yoy/100) 
            revenue_sum = df_this_year['revenue_mon(bil)'].sum()
            revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)

            st.subheader(f"📊 {selected_stock} {stock_name} 營收進度")
            col1, col2, col3 = st.columns(3)
            col1.metric(label=f"推估 {target_year} 年總營收", value=f"{esti_revenue:,.2f} 億")
            # 這裡的標籤也改成 target_year
            col2.metric(label=f"{target_year} 年目前總營收", value=f"{revenue_sum:,.2f} 億") 
            col3.metric(label="目前達成率", value=f"{revenue_achie_rate} %")

            st.markdown("---")

            col_chart, col_table = st.columns([2, 1]) 
            
            with col_chart:
                st.markdown("### 📈 月營收趨勢圖")
                # chart_data = df_this_year[['date', 'revenue_mon(bil)']].set_index('date')
                # st.line_chart(chart_data)

                # 使用 Altair 繪製折線圖 (預設為固定不可縮放)
                # 順便加上 point=True，讓每個月份的數據點有小圓圈標示，視覺更清楚
                chart = alt.Chart(df_this_year).mark_line(point=True).encode(
                    x=alt.X('date:T', title='日期'),
                    y=alt.Y('revenue_mon(bil):Q')
                ).properties(
                    height=350 # 這裡可以微調圖表高度，讓它跟旁邊的表格更對齊
                )
                
                # 將畫好的圖表顯示在網頁上，並設定自動填滿欄位寬度
                st.altair_chart(chart, use_container_width=True)                

            with col_table:
                st.markdown(f"### 📋 近二年詳細數據")
                
                # 抓出符合「目標年」與「前一年」的資料
                df_two_years = df[df['date'].dt.year >= target_year - 1].copy()
                
                # 整理要顯示的欄位
                display_df = df_two_years[['date', 'revenue_mon(bil)', 'yoy%']].copy()
                display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                
                # 💡 實務技巧：建議將表格「反向排序」(由新到舊)，這樣最新的資料就會在最上面，不用每次都往下滑
                display_df = display_df.sort_values("date", ascending=True)
                
                # 顯示表格並隱藏 index
                st.dataframe(display_df, hide_index=True)
        else:
            st.warning(f"目前還沒有 {target_year} 年的營收資料喔！")

    except FileNotFoundError:
        st.error(f"找不到 {selected_stock}_revenue.csv！")