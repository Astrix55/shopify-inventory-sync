from flask import Flask, request, render_template_string, redirect, url_for
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # טוען את המשתנים מקובץ .env

# הגדרות Shopify

ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
STORE_URL = 'chaplostyle.myshopify.com'
API_VERSION = '2024-04'
HEADERS = {
    'X-Shopify-Access-Token': ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

app = Flask(__name__)

# תבנית HTML בסיסית
HTML = """
<!doctype html>
<title>עדכון מלאי Shopify</title>
<h2>העלה קובץ אקסל עם מכירות יומיות</h2>
<form action="/upload" method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value="עדכן מלאי">
</form>
<p>{{ message }}</p>
"""

# שליפת מיקום
def get_location_id():
    url = f"https://{STORE_URL}/admin/api/{API_VERSION}/locations.json"
    res = requests.get(url, headers=HEADERS, verify=False)
    res.raise_for_status()
    return res.json()['locations'][0]['id']

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML, message="")

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if not file:
        return render_template_string(HTML, message="לא נבחר קובץ")

    df = pd.read_excel(file, skiprows=4)
    df = df[["ברקוד", "כמות פריטים שנמכרו"]].dropna()
    df.columns = ["Barcode", "SoldQty"]
    df["SoldQty"] = df["SoldQty"].astype(int)

    location_id = get_location_id()
    success_count = 0
    error_count = 0

    for _, row in df.iterrows():
        barcode = str(int(row["Barcode"]))
        sold_qty = row["SoldQty"]

        url = f"https://{STORE_URL}/admin/api/{API_VERSION}/variants.json?barcode={barcode}"
        response = requests.get(url, headers=HEADERS)
        data = response.json()
        variants = data.get("variants", [])

        if not variants:
            error_count += 1
            continue

        variant = variants[0]
        inventory_item_id = variant["inventory_item_id"]

        inventory_level_url = f"https://{STORE_URL}/admin/api/{API_VERSION}/inventory_levels.json?inventory_item_ids={inventory_item_id}&location_ids={location_id}"
        inventory_response = requests.get(inventory_level_url, headers=HEADERS)
        inventory_data = inventory_response.json()
        current_qty = inventory_data['inventory_levels'][0]['available']

        new_qty = max(current_qty - sold_qty, 0)

        update_url = f"https://{STORE_URL}/admin/api/{API_VERSION}/inventory_levels/set.json"
        payload = {
            "location_id": location_id,
            "inventory_item_id": inventory_item_id,
            "available": new_qty
        }

        update_response = requests.post(url, headers=HEADERS, json=payload, verify=False)
        if update_response.status_code == 200:
            success_count += 1
        else:
            error_count += 1

    message = f"עודכנו {success_count} מוצרים. נכשלו {error_count}."
    return render_template_string(HTML, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

