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

    # 🌟 修改核心 1：在這裡動態建立股票專屬資料夾與檔案路徑
    stock_dir = os.path.join(MANUAL_DIR, stock_id)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, f"{stock_id}_monthly_eps.csv")

    # 3. 輸入數值並防呆
    def get_float_input(prompt):
        while True:
            val = input(prompt).strip()
            try:
                return float(val)
            except ValueError:
                print("❌ 只能輸入數字喔！請重試。")

    net_income_mon = get_float_input("請輸入 [當月稅後淨利] (億元): ")
    net_income_ytd = get_float_input("請輸入 [累計稅後淨利] (億元): ")
    eps_ytd = get_float_input("請輸入 [累計 EPS] (元): ")

    # 4. 準備寫入資料
    new_data = pd.DataFrame([{
        "date": valid_date,
        "stock_id": stock_id,
        "net_income_mon": net_income_mon,
        "net_income_ytd": net_income_ytd,
        "eps_ytd": eps_ytd
    }])

    # 5. 存檔 (若有舊資料則合併，遇到同月則覆蓋更新)
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_old['stock_id'] = df_old['stock_id'].astype(str)
        
        df_final = pd.concat([df_old, new_data], ignore_index=True)
        # 🌟 修改核心 2：單一個股檔案，只需針對 date 去重複
        df_final = df_final.drop_duplicates(subset=['date'], keep='last')
    else:
        df_final = new_data

    # 🌟 修改核心 3：單一個股檔案，只需針對 date 排序 (確保新資料在最下面)
    df_final = df_final.sort_values(by='date', ascending=True)
    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {valid_date} 盈餘資料已成功存放到 data/manual_data/{stock_id}/ 裡面！\n")


def input_dividend():
    """輸入歷年股利資料"""
    print("\n--- 📝 進入 [歷年股利] 輸入模式 ---")
    
    year = input("請輸入財報年度 (例如 2024): ").strip()
    stock_id = input("請輸入股票代號 (例如 2881): ").strip()

    # 🌟 修改核心 1：動態建立股票專屬資料夾與檔案路徑
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
        # 🌟 修改核心 2：單一個股檔案，只需針對 year 去重複
        df_final = df_final.drop_duplicates(subset=['year'], keep='last')
    else:
        df_final = new_data

    # 🌟 修改核心 3：單一個股檔案，只需針對 year 排序 (確保新年份在最下面)
    df_final = df_final.sort_values(by='year', ascending=True)
    df_final.to_csv(file_path, index=False)
    print(f"✅ {stock_id} 的 {year} 年股利資料已成功存放到 data/manual_data/{stock_id}/ 裡面！\n")

# ================= 主程式選單 =================
if __name__ == "__main__":
    while True:
        print("========== 手動資料建檔系統 ==========")
        print("1. 輸入 [金控每月自結盈餘] (EPS)")
        print("2. 輸入 [歷年股利與盈餘] (配息)")
        print("3. 離開程式")
        print("======================================")
        
        choice = input("請選擇要執行的項目 (1/2/3): ").strip()
        
        if choice == '1':
            input_monthly_eps()
        elif choice == '2':
            input_dividend()
        elif choice == '3':
            print("👋 離開程式，記得將變更 git push 到 GitHub 喔！")
            break
        else:
            print("❌ 輸入錯誤，請輸入 1, 2 或 3。")