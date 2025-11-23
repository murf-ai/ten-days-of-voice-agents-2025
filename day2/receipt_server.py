from flask import Flask, render_template_string, abort
import glob, json, os

app = Flask(__name__)
ORDERS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "orders")

TEMPLATE = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Latest Receipt</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;padding:24px}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;max-width:420px;box-shadow:0 6px 18px rgba(0,0,0,0.06)}
.cup{width:120px;height:160px;border-radius:14px;background:#f5f3f2;margin:12px auto;position:relative}
.whip{position:absolute;left:18px;top:-24px;width:84px;height:40px;border-radius:40px 40px 20px 20px;background:#fff}
.field{margin:6px 0}
.kv{font-weight:600}
</style>
</head>
<body>
<div class="card">
  <h2>Latest Order Receipt</h2>
  <div class="cup"><div class="whip" style="{{whip}}"></div></div>
  <div class="field"><span class="kv">Name:</span> {{order.name}}</div>
  <div class="field"><span class="kv">Drink:</span> {{order.drinkType}}</div>
  <div class="field"><span class="kv">Size:</span> {{order.size}}</div>
  <div class="field"><span class="kv">Milk:</span> {{order.milk}}</div>
  <div class="field"><span class="kv">Extras:</span> {{order.extras}}</div>
</div>
</body>
</html>
'''

def load_latest_order():
    files = glob.glob(os.path.join(ORDERS_DIR, '*.json'))
    if not files:
        return None, None
    files.sort(key=os.path.getmtime, reverse=True)
    with open(files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)
    whip_style = 'display:none;' if not any('whip' in e.lower() or 'whipped' in e.lower() for e in data.get('extras', [])) else ''
    return data, whip_style

@app.route('/receipt/latest')
def latest():
    order, whip_style = load_latest_order()
    if not order:
        abort(404, 'No orders found')
    return render_template_string(TEMPLATE, order=order, whip=whip_style)

if __name__ == '__main__':
    # run on port 8000
    app.run(port=8000, host='127.0.0.1', debug=False)
