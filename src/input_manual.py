import os
import pandas as pd
from datetime import datetime

# ================= 🌟 路徑設定區 =================
# 取得目前程式所在位置 (也就是 src/ 資料夾)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 往上一層找，指向 ../data/manual_data/
MANUAL_DIR = os.path.join(current_dir, "..", "data", "manual_data")
os.makedirs(MANUAL_DIR, exist_ok=True)
# =================================================

def input_monthly_eps():
    """輸入金控每月自結盈餘"""
    print("\n--- 📝 進入 [每月自結盈餘] 輸入模式 ---")
    
    # 1. 先取得使用者輸入的日期與代號
    while True:
        date_str = input("請輸入資料年月 (格式 YYYY-MM-01，例如 2026-01-01): ").strip()
        try:
            valid_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            break
        except ValueError:
            print("❌ 格式錯誤！請務必輸入像是 2026-01-01 這樣的格式。")

    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    # 動態建立股票專屬資料夾與檔案路徑
    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_monthly_eps.csv")

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    # 取得當月 EPS
    eps_mon = get_float_input(f"請輸入 {stock_id} 在 {valid_date[:7]} 的 [當月 EPS] (元): ")

    # 準備寫入資料
    new_data = pd.DataFrame([{
        "date": valid_date,
        "stock_id": stock_id,
        "eps_mon": eps_mon
    }])

    # 存檔 (若有舊資料則合併，遇到同月則覆蓋更新)
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_old['stock_id'] = df_old['stock_id'].astype(str)
        
        df_final = pd.concat([df_old, new_data], ignore_index=True)
        # 單一個股檔案，只需針對 date 去重複
        df_final = df_final.drop_duplicates(subset=['date'], keep='last')
    else:
        df_final = new_data

    # 自動計算「累計 EPS」
    df_final['date'] = pd.to_datetime(df_final['date'])
    df_final = df_final.sort_values(by='date', ascending=True)
    df_final['year'] = df_final['date'].dt.year
    df_final['eps_ytd'] = df_final.groupby('year')['eps_mon'].cumsum()
    df_final = df_final.drop(columns=['year'])
    df_final['date'] = df_final['date'].dt.strftime('%Y-%m-%d')

    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {valid_date} 盈餘資料已成功存檔！系統已自動幫您結算累計 EPS。\n")


def input_dividend():
    """輸入歷年股利資料"""
    print("\n--- 📝 進入 [歷年股利] 輸入模式 ---")
    
    year = input("請輸入財報年度 (例如 2024): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_dividend_history.csv")

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    eps = get_float_input(f"請輸入 {stock_id} 在 {year} 年的全年 EPS: ")
    cash_div = get_float_input("請輸入 [現金股利]: ")
    stock_div = get_float_input("請輸入 [股票股利]: ")

    new_data = pd.DataFrame([{
        "year": year,
        "stock_id": stock_id,
        "eps": eps,
        "cash_div": cash_div,
        "stock_div": stock_div
    }])

    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_old['stock_id'] = df_old['stock_id'].astype(str)
        df_old['year'] = df_old['year'].astype(str)
        
        df_final = pd.concat([df_old, new_data], ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['year'], keep='last')
    else:
        df_final = new_data

    df_final = df_final.sort_values(by='year', ascending=True)
    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年股利資料已成功存放到 data/manual_data/{stock_id}/ 裡面！\n")


def input_yearly_revenue():
    """輸入歷年總營收"""
    print("\n--- 📝 進入 [歷年總營收] 輸入模式 ---")
    
    year = input("請輸入財報年度 (例如 2024): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_yearly_revenue.csv")

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    revenue_yearly = get_float_input(f"請輸入 {stock_id} 在 {year} 年的 [全年總營收] (單位: 億元): ")

    new_data = pd.DataFrame([{
        "year": year,
        "stock_id": stock_id,
        "revenue_yearly": revenue_yearly
    }])

    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_old['stock_id'] = df_old['stock_id'].astype(str)
        df_old['year'] = df_old['year'].astype(str)
        
        df_final = pd.concat([df_old, new_data], ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['year'], keep='last')
    else:
        df_final = new_data

    df_final = df_final.sort_values(by='year', ascending=True)
    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年總營收資料已成功存放到 data/manual_data/{stock_id}/ 裡面！\n")


def input_3yr_avg_yield():
    """輸入近三年平均殖利率"""
    print("\n--- 📝 進入 [近三年平均殖利率] 輸入模式 ---")
    
    year = input("請輸入更新年度 (例如 2026): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_3yr_yield.csv")

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    avg_yield = get_float_input(f"請輸入 {stock_id} 在 {year} 年的 [近三年平均殖利率] (%): ")

    new_data = pd.DataFrame([{
        "year": year,
        "stock_id": stock_id,
        "avg_yield": avg_yield
    }])

    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_old['stock_id'] = df_old['stock_id'].astype(str)
        df_old['year'] = df_old['year'].astype(str)
        
        df_final = pd.concat([df_old, new_data], ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['year'], keep='last')
    else:
        df_final = new_data

    df_final = df_final.sort_values(by='year', ascending=True)
    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年近三年平均殖利率已成功存放到 data/manual_data/{stock_id}/ 裡面！\n")

def input_historical_pe():
    """輸入歷年最高/最低本益比"""
    print("\n--- 📝 進入 [歷年本益比極值] 輸入模式 ---")
    
    year = input("請輸入資料年度 (例如 2023): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_historical_valuation.csv")

    # 🌟 欄位修正：殖利率只保留 annual_yield_pct 一個欄位
    STANDARD_COLS = ['year', 'stock_id', 'lowest_pe', 'highest_pe', 'annual_yield_pct']

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    lowest_pe = get_float_input(f"請輸入 {stock_id} 在 {year} 年的 [最低本益比]: ")
    highest_pe = get_float_input(f"請輸入 {stock_id} 在 {year} 年的 [最高本益比]: ")

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df['year'] = df['year'].astype(str)
        df['stock_id'] = df['stock_id'].astype(str)
    else:
        df = pd.DataFrame(columns=STANDARD_COLS)

    if year in df['year'].values:
        df.loc[df['year'] == year, 'lowest_pe'] = lowest_pe
        df.loc[df['year'] == year, 'highest_pe'] = highest_pe
    else:
        # 新增時，殖利率欄位先補空值
        new_row = pd.DataFrame([{
            "year": year, 
            "stock_id": stock_id, 
            "lowest_pe": lowest_pe, 
            "highest_pe": highest_pe,
            "annual_yield_pct": None
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.sort_values(by='year', ascending=True)
    df = df[STANDARD_COLS]
    df.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年 [本益比] 資料已成功更新至 historical_valuation.csv！\n")


def input_historical_yield():
    """輸入歷年殖利率"""
    print("\n--- 📝 進入 [歷年年殖利率] 輸入模式 ---")
    
    year = input("請輸入資料年度 (例如 2023): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_historical_valuation.csv")

    # 🌟 欄位修正：殖利率只保留 annual_yield_pct 一個欄位
    STANDARD_COLS = ['year', 'stock_id', 'lowest_pe', 'highest_pe', 'annual_yield_pct']

    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    # 🌟 改為只詢問當年度單一殖利率
    annual_yield = get_float_input(f"請輸入 {stock_id} 在 {year} 年的 [年殖利率] (%): ")

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df['year'] = df['year'].astype(str)
        df['stock_id'] = df['stock_id'].astype(str)
    else:
        df = pd.DataFrame(columns=STANDARD_COLS)

    if year in df['year'].values:
        df.loc[df['year'] == year, 'annual_yield_pct'] = annual_yield
    else:
        # 新增時，本益比欄位先補空值
        new_row = pd.DataFrame([{
            "year": year, 
            "stock_id": stock_id, 
            "lowest_pe": None, 
            "highest_pe": None,
            "annual_yield_pct": annual_yield
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.sort_values(by='year', ascending=True)
    df = df[STANDARD_COLS]
    df.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年 [殖利率] 資料已成功更新至 historical_valuation.csv！\n")

# ================= 主程式選單 =================
if __name__ == "__main__":
    while True:
        print("========== 手動資料建檔系統 ==========")
        print("1. 輸入 [金控每月自結盈餘] (每月查新聞)")
        print("2. 輸入 [歷年股利與盈餘] (查股利政策)")
        print("3. 輸入 [歷年總營收] (損益表-本業獲利)")  
        print("4. 輸入 [近三年平均殖利率] (查股利政策-近三年發放取平均)")  # 🌟 新增選項
        print("5. 輸入 [歷年本益比極值] (每年最低與最高本益比)") 
        print("6. 輸入 [歷年殖利率]")
        print("7. 離開程式")
        print("======================================")
        
        choice = input("請選擇要執行的項目 (1/2/3/4/5/6/7): ").strip()
        
        if choice == '1':
            input_monthly_eps()
        elif choice == '2':
            input_dividend()
        elif choice == '3':
            input_yearly_revenue()
        elif choice == '4':
            input_3yr_avg_yield()
        elif choice == '5':
            input_historical_pe()
        elif choice == '6':
            input_historical_yield()
        elif choice == '7':
            print("👋 離開程式，記得將變更 git push 到 GitHub 喔！")
            break
        else:
            print("❌ 輸入錯誤，請輸入 1, 2, 3, 4, 5, 6 或 7。")