import update_data

stock_ids = ["2882"]
print("start auto update")
for stock_id in stock_ids:
    print(f"updating {stock_id} ...")
    update_data.update(stock_id)
print("updated")