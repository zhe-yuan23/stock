import update_data

stock_ids = ["2881","2882","2883","2884","2885","2887","2890","2891","2892"]
print("start auto update")
for stock_id in stock_ids:
    print(f"updating {stock_id} ...")
    update_data.update(stock_id)
print("updated")