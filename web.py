import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt

from src.calculator import calculate_valuation

st.set_page_config(page_title="台股營收追蹤", layout="wide")

def _get_baseline_revenue_for_estimate(stock_id: str, target_year: int, df_revenue: pd.DataFrame):
    """
    取得「推估年度營收」的基準（上一年度營收總額）。

    優先用 revenue.csv 內 target_year-1 的 12 個月加總；若缺資料，退回使用 manual_data 的 yearly_revenue。
    回傳 (baseline_year, baseline_revenue)；若都取不到則回傳 (None, None)。
    """
    baseline_year = target_year - 1

    try:
        df_last_year = df_revenue[df_revenue["date"].dt.year == baseline_year]
        last_year_revenue = float(df_last_year["revenue_mon(bil)"].sum())
    except Exception:
        last_year_revenue = 0.0

    if last_year_revenue > 0:
        return baseline_year, last_year_revenue

    try:
        df_yearly = pd.read_csv(f"data/manual_data/{stock_id}/{stock_id}_yearly_revenue.csv")
        if "year" in df_yearly.columns and "revenue_yearly" in df_yearly.columns and not df_yearly.empty:
            df_yearly["year"] = pd.to_numeric(df_yearly["year"], errors="coerce")
            df_yearly = df_yearly.dropna(subset=["year"]).sort_values("year")

            row_exact = df_yearly[df_yearly["year"] == baseline_year]
            if not row_exact.empty:
                v = float(row_exact["revenue_yearly"].iloc[-1])
                if v > 0:
                    return baseline_year, v

            row_latest = df_yearly.iloc[-1]
            y = int(row_latest["year"])
            v = float(row_latest["revenue_yearly"])
            if v > 0:
                return y, v
    except Exception:
        pass

    return None, None

# ==========================================
# 區塊 A：側邊欄導覽列與自動掃描資料夾
# ==========================================
st.sidebar.title("導覽選單")
page = st.sidebar.radio("請選擇頁面", ["🏠 總覽首頁", "📈 個股詳細資料", "💰 基本面估價觀測"])
st.sidebar.markdown("---")

# 🌟 修改掃描邏輯：改為抓取 data 目錄下的所有「子資料夾名稱」
# 並排除 manual_data 這種純手動設定用的資料夾
try:
    stock_list = sorted(
        [
            d
            for d in os.listdir("data")
            if os.path.isdir(os.path.join("data", d)) and d != "manual_data"
        ]
    )
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

                df_this_year = df[df["date"].dt.year == global_target_year]
                stock_name = stock_display.get(sid, "")
                
                baseline_year, last_year_revenue = _get_baseline_revenue_for_estimate(
                    stock_id=sid, target_year=global_target_year, df_revenue=df
                )

                if not df_this_year.empty and last_year_revenue and last_year_revenue > 0:
                    newest_ytd_yoy = df_this_year['ytd_yoy(%)'].iat[-1]
                    esti_revenue = last_year_revenue * (1 + newest_ytd_yoy/100)
                    revenue_sum = df_this_year['revenue_ytd(bil)'].iat[-1]
                    revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2)
                    
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        # "基準年度": baseline_year,
                        "排序數值": revenue_achie_rate, 
                        "目前達成率 (%)": f"{revenue_achie_rate} %"
                    })
                else:
                    summary_data.append({
                        "公司名稱": f"{sid} {stock_name}",
                        # "基準年度": baseline_year if baseline_year is not None else "",
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

        df_this_year = df[df["date"].dt.year == target_year] 

        if not df_this_year.empty:
            baseline_year, last_year_revenue = _get_baseline_revenue_for_estimate(
                stock_id=selected_stock, target_year=target_year, df_revenue=df
            )
            newest_ytd_yoy = df_this_year['ytd_yoy(%)'].iat[-1]
            esti_revenue = last_year_revenue * (1 + newest_ytd_yoy/100) if last_year_revenue else 0
            revenue_sum = df_this_year['revenue_ytd(bil)'].iat[-1]
            revenue_achie_rate = (revenue_sum / esti_revenue * 100).round(2) if esti_revenue else None

            st.subheader(f"📊 {selected_stock} {stock_name} 營收進度")
            col1, col2, col3 = st.columns(3)
            if revenue_achie_rate is None:
                col1.metric(label=f"推估 {target_year} 年總營收", value="尚未公布")
            else:
                label_suffix = f"（基準 {baseline_year} 年）" if baseline_year else ""
                col1.metric(label=f"推估 {target_year} 年總營收{label_suffix}", value=f"{esti_revenue:,.2f} 億")
            col2.metric(label=f"{target_year} 年目前總營收", value=f"{revenue_sum:,.2f} 億") 
            col3.metric(label="目前達成率", value="尚未公布" if revenue_achie_rate is None else f"{revenue_achie_rate} %")

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

# ==========================================
# 區塊 D：💰 基本面估價觀測（使用 calculator.py）
# ==========================================
elif page == "💰 基本面估價觀測":
    st.title("基本面估價觀測")

    if not stock_list:
        st.warning("目前沒有任何股票資料，無法進行估價。")
    else:
        selected_stock = st.selectbox(
            "請選擇要估價的股票",
            options=stock_list,
            format_func=lambda x: f"{x} {stock_display.get(x, '')}",
        )

        try:
            result = calculate_valuation(selected_stock)

            stock_name = result["stock_name"]
            latest_date = result["latest_date"]
            current_price = result["current_price"]
            current_pe = result["current_pe"]
            est_revenue = result["est_revenue"]
            ytd_yoy_percent = result["ytd_yoy_percent"]
            revenue_ytd = result["revenue_ytd"]
            rev_achieve_rate = result["rev_achieve_rate"]
            est_net_income = result["est_net_income"]
            net_margin = result["net_margin"]
            est_eps = result["est_eps"]
            eps_ytd = result["eps_ytd"]
            eps_achieve_rate = result["eps_achieve_rate"]
            est_dividend = result["est_dividend"]
            avg_payout_ratio = result["avg_payout_ratio"]
            est_fair_price = result["est_fair_price"]
            avg_yield_3yr = result["avg_yield_3yr"]
            est_current_yield = result["est_current_yield"]
            price_volatility = result["price_volatility"]
            is_undervalued = result["is_undervalued"]

            st.subheader(f"📈 {selected_stock} {stock_name} 估價結果")
            st.caption(f"資料日期：{latest_date}（依據最新收盤價）")

            col_price, col_pe, col_yield = st.columns(3)
            col_price.metric("目前股價", f"{current_price:.2f} 元")
            col_pe.metric("最新本益比", f"{current_pe:.2f} 倍")
            col_yield.metric("推估現價殖利率", f"{est_current_yield:.2f} %")

            st.markdown("---")

            col1, col2, col3 = st.columns(3)
            col1.metric("推估今年營收", f"{est_revenue:.2f} 億元", help=f"年增率設定：約 {ytd_yoy_percent:.2f} %")
            col2.metric("目前累計營收", f"{revenue_ytd:.2f} 億元")
            col3.metric("營收達成率", f"{rev_achieve_rate:.2f} %")

            col4, col5, col6 = st.columns(3)
            col4.metric("推估稅後淨利", f"{est_net_income:.2f} 億元", help=f"反推淨利率：約 {net_margin:.2f} %")
            col5.metric("推估全年 EPS", f"{est_eps:.2f} 元")
            col6.metric("EPS 達成率", f"{eps_achieve_rate:.2f} %", help=f"目前累計 EPS：{eps_ytd}")

            col7, col8, col9 = st.columns(3)
            col7.metric("推估總股息", f"{est_dividend:.2f} 元", help=f"近 7 年平均分配率：約 {avg_payout_ratio:.2f} %")
            col8.metric("推估基本面價", f"{est_fair_price:.2f} 元", help=f"採用近 3 年平均殖利率：約 {avg_yield_3yr:.2f} %")
            col9.metric("股價波動位階", f"{price_volatility:.2f} %", help="現價佔基本面價的比例")

            st.markdown("---")

            if is_undervalued:
                st.success(
                    f"【結論】{stock_name} 目前股價 ({current_price:.2f} 元) "
                    f"低於基本面推估價 ({est_fair_price:.2f} 元)，屬於相對便宜區間。"
                )
            else:
                st.info(
                    f"【結論】{stock_name} 目前股價 ({current_price:.2f} 元) "
                    f"高於或接近基本面推估價 ({est_fair_price:.2f} 元)，已反映基本面或偏貴。"
                )

        except FileNotFoundError as e:
            st.error(f"找不到必要資料檔案：{e.filename}")
            st.caption("請確認自動抓取與手動建檔的資料都已經準備齊全。")
        except Exception as e:
            st.error(f"估價過程中發生錯誤：{e}")