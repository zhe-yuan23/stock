# 匯入我們寫好的兩支模組
import update_monthly_data
import update_daily_data
from datetime import datetime

# 統一設定股票清單與存檔資料夾
stock_ids = ["2330", "2881", "2882", "2883", "2884", "2885", "2887", "2890", "2891", "2892"]
base_dir = "data"

print(f"=== 🚀 開始執行台股排程總任務 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
print(f"🎯 追蹤名單: {stock_ids}")

# 1. 執行每日盤後資料更新 (股價、估值、股數)
try:
    print("\n--- 執行任務 1：更新每日盤後資料 ---")
    update_daily_data.update_daily_data(stock_ids, base_dir)
except Exception as e:
    print(f"⚠️ 每日盤後任務發生錯誤: {e}")

# 2. 執行月營收更新
try:
    print("\n--- 執行任務 2：更新每月營收資料 ---")
    # 注意：剛剛我們把函數名稱改成 update_revenue_data 了
    update_monthly_data.update_revenue_data(stock_ids, base_dir) 
except Exception as e:
    print(f"⚠️ 月營收任務發生錯誤: {e}")

print("\n=== 🎉 所有自動更新任務執行完畢 ===")