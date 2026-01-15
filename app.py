from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import requests
import csv
import io
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['APPLICATION_ROOT'] = '/finance'

mongo_uri = os.environ.get('MONGO_URI', 'mongodb://mongo:27017/')
client = MongoClient(mongo_uri)
db = client.dividend_tracker
assets = db.assets

cache = {'data': {}, 'timestamp': 0}
CACHE_TTL = 300  # 5 minutes

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_symbol(symbol):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d&events=div'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = data['chart']['result'][0]
        price = result['meta']['regularMarketPrice']

        divs = result.get('events', {}).get('dividends', {})
        annual_div = 0
        div_months = []

        if divs:
            from datetime import datetime
            for ts, d in divs.items():
                annual_div += d['amount']
                month = datetime.fromtimestamp(int(ts)).month
                if month not in div_months:
                    div_months.append(month)

        return {'price': price, 'dividend': annual_div, 'div_months': sorted(div_months)}
    except Exception as e:
        logger.error(f'{symbol} fetch error: {e}')
        return None

def get_live_data(symbols):
    if not symbols:
        return {}

    now = time.time()
    if now - cache['timestamp'] < CACHE_TTL and all(s in cache['data'] for s in symbols):
        return {s: cache['data'][s] for s in symbols}

    data = {}
    for symbol in symbols:
        result = fetch_symbol(symbol)
        if result:
            data[symbol] = result
            logger.info(f'{symbol}: price={result["price"]}, dividend={result["dividend"]}, months={result["div_months"]}')
        else:
            data[symbol] = cache['data'].get(symbol, {'price': 0, 'dividend': 0, 'div_months': []})

    cache['data'].update(data)
    cache['timestamp'] = now
    return data

@app.route('/finance/')
def index():
    return render_template('index.html')

@app.route('/finance/api/assets', methods=['GET'])
def get_assets():
    asset_list = list(assets.find({}, {'_id': 0}))
    symbols = [a['symbol'] for a in asset_list]
    live_data = get_live_data(symbols)

    for asset in asset_list:
        symbol = asset['symbol']
        data = live_data.get(symbol, {'price': 0, 'dividend': 0})
        asset['price'] = data['price']
        asset['value'] = data['price'] * asset['quantity']
        asset['annual_dividend'] = data['dividend'] * asset['quantity']
        asset['monthly_dividend'] = asset['annual_dividend'] / 12
    return jsonify(asset_list)

@app.route('/finance/api/assets', methods=['POST'])
def add_asset():
    data = request.json
    symbol = data.get('symbol', '').upper()
    quantity = float(data.get('quantity', 0))

    existing = assets.find_one({'symbol': symbol})
    if existing:
        assets.update_one({'symbol': symbol}, {'$set': {'quantity': quantity}})
    else:
        assets.insert_one({'symbol': symbol, 'quantity': quantity})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/assets/<symbol>', methods=['PUT'])
def update_asset(symbol):
    data = request.json
    quantity = float(data.get('quantity', 0))
    assets.update_one({'symbol': symbol.upper()}, {'$set': {'quantity': quantity}})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/assets/<symbol>', methods=['DELETE'])
def delete_asset(symbol):
    assets.delete_one({'symbol': symbol.upper()})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/import', methods=['POST'])
def import_csv():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'status': 'error', 'message': 'File must be CSV'}), 400

    try:
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        imported = 0
        for row in reader:
            symbol = None
            quantity = None

            for key in row:
                key_lower = key.lower().strip()
                if key_lower in ['symbol', 'ticker', 'stock']:
                    symbol = row[key].strip().upper()
                elif key_lower in ['quantity', 'qty', 'shares', 'amount']:
                    try:
                        quantity = float(row[key].strip())
                    except ValueError:
                        continue

            if symbol and quantity:
                existing = assets.find_one({'symbol': symbol})
                if existing:
                    assets.update_one({'symbol': symbol}, {'$inc': {'quantity': quantity}})
                else:
                    assets.insert_one({'symbol': symbol, 'quantity': quantity})
                imported += 1

        cache['timestamp'] = 0  # Clear cache
        return jsonify({'status': 'ok', 'imported': imported})
    except Exception as e:
        logger.error(f'Import error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/finance/api/summary', methods=['GET'])
def get_summary():
    asset_list = list(assets.find({}, {'_id': 0}))
    symbols = [a['symbol'] for a in asset_list]
    live_data = get_live_data(symbols)

    yearly_total = 0
    portfolio_value = 0

    for asset in asset_list:
        data = live_data.get(asset['symbol'], {'price': 0, 'dividend': 0})
        yearly_total += data['dividend'] * asset['quantity']
        portfolio_value += data['price'] * asset['quantity']

    return jsonify({
        'yearly': yearly_total,
        'portfolio_value': portfolio_value
    })

@app.route('/finance/api/monthly', methods=['GET'])
def get_monthly():
    asset_list = list(assets.find({}, {'_id': 0}))
    symbols = [a['symbol'] for a in asset_list]
    live_data = get_live_data(symbols)

    months = {i: {'total': 0, 'assets': []} for i in range(1, 13)}
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for asset in asset_list:
        symbol = asset['symbol']
        data = live_data.get(symbol, {'price': 0, 'dividend': 0, 'div_months': []})
        div_months = data.get('div_months', [])
        annual_div = data['dividend'] * asset['quantity']

        if div_months:
            per_payment = annual_div / len(div_months)
            for m in div_months:
                months[m]['total'] += per_payment
                months[m]['assets'].append({'symbol': symbol, 'amount': per_payment})

    result = []
    for i in range(1, 13):
        result.append({
            'month': i,
            'name': month_names[i],
            'total': months[i]['total'],
            'assets': months[i]['assets']
        })

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
