import csv
from io import StringIO

def parse_price_csv(text, price_column="close"):
    reader = csv.DictReader(StringIO(text))
    if price_column not in (reader.fieldnames or []):
        raise ValueError(f"missing '{price_column}' column")
    prices = []
    rows = []
    for row in reader:
        try:
            price = float(row[price_column])
        except (TypeError, ValueError):
            continue
        prices.append(price)
        rows.append(row)
    if not prices:
        raise ValueError("no valid prices found")
    return {"prices": prices, "rows_parsed": len(rows), "columns": reader.fieldnames or []}
