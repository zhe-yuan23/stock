import os
import pandas as pd

# ================= 🌟 路徑設定區 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
AUTO_DIR = os.path.join(current_dir, "..", "data")
MANUAL_DIR = os.path.join(current_dir, "..", "data", "manual_data")
# =================================================

def calculate_valuation(stock_id):
    """
    核心估價計算函式。
    傳入股票代號，回傳一個包含所有計算結果的 dict，
    方便在 CLI 或網站 (Streamlit) 上重複使用。
    """
    try:
        # 📂 1. 讀取所有需要的資料
        # --- 自動抓取區 ---
        df_price = pd.read_csv(os.path.join(AUTO_DIR, stock_id, f"{stock_id}_price.csv"))
        df_valuation = pd.read_csv(os.path.join(AUTO_DIR, stock_id, f"{stock_id}_valuation.csv"))
        df_revenue = pd.read_csv(os.path.join(AUTO_DIR, stock_id, f"{stock_id}_revenue.csv"))
        df_basic = pd.read_csv(os.path.join(AUTO_DIR, stock_id, f"{stock_id}_basic_info.csv"))
        
        # --- 手動建檔區 ---
        df_yearly_rev = pd.read_csv(os.path.join(MANUAL_DIR, stock_id, f"{stock_id}_yearly_revenue.csv"))
        df_monthly_eps = pd.read_csv(os.path.join(MANUAL_DIR, stock_id, f"{stock_id}_monthly_eps.csv"))
        df_div = pd.read_csv(os.path.join(MANUAL_DIR, stock_id, f"{stock_id}_dividend_history.csv"))
        df_3yr_yield = pd.read_csv(os.path.join(MANUAL_DIR, stock_id, f"{stock_id}_3yr_yield.csv"))

        # 🔍 2. 提取最新數值
        current_price = df_price.iloc[-1]['price']
        stock_name = df_price.iloc[-1]['name']  # 🌟 從股價檔案中提取股票名稱
        latest_date = df_price.iloc[-1]['Date']
        current_pe = df_valuation.iloc[-1]['PE_Ratio']
        shares_out = df_basic.iloc[-1]['shares_outstanding(億股)']
        
        last_year_rev = df_yearly_rev.iloc[-1]['revenue_yearly']
        ytd_yoy_percent = df_revenue.iloc[-1]['ytd_yoy(%)'] / 100  
        revenue_ytd = df_revenue.iloc[-1]['revenue_ytd(bil)']      
        
        eps_ytd = df_monthly_eps.iloc[-1]['eps_ytd']
        avg_yield_3yr = df_3yr_yield.iloc[-1]['avg_yield'] / 100   

        # 計算近 7 年平均盈餘分配率
        df_div_7yr = df_div.tail(7).copy()
        df_div_7yr['payout_ratio'] = (df_div_7yr['cash_div'] + df_div_7yr['stock_div']) / df_div_7yr['eps']
        avg_payout_ratio = df_div_7yr['payout_ratio'].mean()

        # 🧮 3. 開始執行 8 條基本面公式
        
        # (前置作業) 反推近四季稅後淨利率
        eps_4q = current_price / current_pe 
        net_income_4q = eps_4q * shares_out
        net_margin = net_income_4q / last_year_rev

        # 公式 1~9
        est_revenue = (1 + ytd_yoy_percent) * last_year_rev
        rev_achieve_rate = (revenue_ytd / est_revenue) * 100
        est_net_income = est_revenue * net_margin
        est_eps = est_net_income / shares_out
        eps_achieve_rate = (eps_ytd / est_eps) * 100
        est_dividend = est_eps * avg_payout_ratio
        est_fair_price = est_dividend / avg_yield_3yr
        est_current_yield = (est_dividend / current_price) * 100
        price_volatility = (current_price / est_fair_price) * 100

        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "latest_date": latest_date,
            "current_price": current_price,
            "current_pe": current_pe,
            "shares_outstanding": shares_out,
            "last_year_revenue": last_year_rev,
            "ytd_yoy_percent": ytd_yoy_percent * 100,
            "revenue_ytd": revenue_ytd,
            "eps_ytd": eps_ytd,
            "avg_yield_3yr": avg_yield_3yr * 100,
            "avg_payout_ratio": avg_payout_ratio * 100,
            "eps_4q": eps_4q,
            "net_income_4q": net_income_4q,
            "net_margin": net_margin * 100,
            "est_revenue": est_revenue,
            "rev_achieve_rate": rev_achieve_rate,
            "est_net_income": est_net_income,
            "est_eps": est_eps,
            "eps_achieve_rate": eps_achieve_rate,
            "est_dividend": est_dividend,
            "est_fair_price": est_fair_price,
            "est_current_yield": est_current_yield,
            "price_volatility": price_volatility,
            "is_undervalued": current_price < est_fair_price,
        }

    except Exception as e:
        # 讓呼叫端決定如何顯示錯誤（CLI、網站各自處理）
        raise e


def run_valuation(stock_id):
    """
    給終端機使用的包裝函式：呼叫 calculate_valuation 並以文字方式輸出。
    """
    try:
        result = calculate_valuation(stock_id)

        stock_name = result["stock_name"]
        latest_date = result["latest_date"]
        current_price = result["current_price"]
        current_pe = result["current_pe"]
        ytd_yoy_percent = result["ytd_yoy_percent"]
        revenue_ytd = result["revenue_ytd"]
        est_revenue = result["est_revenue"]
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

        # 印出帶有名稱的專屬標題
        print(f"\n========== 📈 啟動 {stock_id} {stock_name} 估價計算機 ==========")
        print(f"📅 資料日期: {latest_date} (依據最新收盤價)")
        print("-" * 40)

        # 📊 結果報告
        print(f"🔹 目前股價: {current_price} 元 | 最新本益比: {current_pe}")
        print("-" * 40)
        print(f"✅ 1. 推估今年營收: {est_revenue:.2f} 億元 (年增率設定: {ytd_yoy_percent:.2f}%)")
        print(f"✅ 2. 營收達成率:   {rev_achieve_rate:.2f} % (目前累計: {revenue_ytd:.2f} 億)")
        print(f"✅ 3. 推估稅後淨利: {est_net_income:.2f} 億元 (反推淨利率: {net_margin:.2f}%)")
        print(f"✅ 4. 推估全年 EPS: {est_eps:.2f} 元")
        print(f"✅ 5. EPS 達成率:   {eps_achieve_rate:.2f} % (目前累計 EPS: {eps_ytd})")
        print(f"✅ 6. 推估總股息:   {est_dividend:.2f} 元 (7年平均分配率: {avg_payout_ratio:.2f}%)")
        print(f"✅ 7. 推估基本面價: {est_fair_price:.2f} 元 (採用3年平均殖利率: {avg_yield_3yr:.2f}%)")
        print(f"✅ 8. 現價殖利率:   {est_current_yield:.2f} %")
        print(f"✅ 9. 股價波動位階: {price_volatility:.2f} % (現價佔基本面價的比例)")
        print("====================================================\n")

        # 結論判斷帶上股票名稱
        if is_undervalued:
            print(f"💡 【結論】：{stock_name} 目前股價 ({current_price}) 低於基本面推估價 ({est_fair_price:.2f})，屬於相對便宜區間！\n")
        else:
            print(f"💡 【結論】：{stock_name} 目前股價 ({current_price}) 高於基本面推估價 ({est_fair_price:.2f})，已反映基本面或偏貴。\n")

    except FileNotFoundError as e:
        print(f"\n========== 📈 啟動 {stock_id} 估價計算機 ==========")
        print(f"❌ 找不到檔案: {e.filename}")
        print("請確認自動抓取與手動建檔的資料都已經準備齊全！")
    except Exception as e:
        print(f"❌ 計算過程中發生錯誤: {e}")

if __name__ == "__main__":
    # stock_input = input("請輸入要估價的股票代號 (例如 2881): ").strip()
    # run_valuation(stock_input)
        while True:
            print("========== 股票查詢系統 ==========")
            print("q 離開程式")
            print("======================================")
            
            stock_input = input("請輸入要估價的股票代號 (例如 2881): ").strip()
            
            if stock_input == 'q':
                print("👋 離開程式")
                break
            else:
                run_valuation(stock_input)