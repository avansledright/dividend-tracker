from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
import requests
import csv
import io
import os
import time
import logging
import re
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['APPLICATION_ROOT'] = '/finance'
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Symbol validation regex - only alphanumeric, 1-10 chars
SYMBOL_PATTERN = re.compile(r'^[A-Z0-9]{1,10}$')

def validate_symbol(symbol):
    """Validate stock symbol format"""
    if not symbol or not SYMBOL_PATTERN.match(symbol):
        return None
    return symbol

def generate_csrf_token():
    """Generate or retrieve CSRF token"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def verify_csrf_token():
    """Verify CSRF token from request header"""
    token = request.headers.get('X-CSRF-Token')
    if not token or token != session.get('csrf_token'):
        return False
    return True

mongo_uri = os.environ.get('MONGO_URI', 'mongodb://mongo:27017/')
client = MongoClient(mongo_uri)
db = client.dividend_tracker
assets = db.assets

# Optional Alpha Vantage API key for fallback (free tier: 25 requests/day)
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', '')

cache = {'data': {}, 'timestamp': 0}
CACHE_TTL = 300  # 5 minutes

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_yahoo(symbol):
    """Primary source: Yahoo Finance"""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d&events=div'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data['chart']['result'] is None:
            return None

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

        return {'price': price, 'dividend': annual_div, 'div_months': sorted(div_months), 'valid': True, 'source': 'yahoo'}
    except Exception as e:
        logger.warning(f'{symbol} Yahoo fetch failed: {e}')
        return None

def fetch_alpha_vantage(symbol):
    """Fallback source: Alpha Vantage (requires API key)"""
    if not ALPHA_VANTAGE_KEY:
        return None

    try:
        # Get quote data
        quote_url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}'
        resp = requests.get(quote_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'Global Quote' not in data or not data['Global Quote']:
            return None

        price = float(data['Global Quote'].get('05. price', 0))

        # Get dividend data (monthly adjusted includes dividends)
        div_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}'
        div_resp = requests.get(div_url, timeout=10)
        div_resp.raise_for_status()
        div_data = div_resp.json()

        annual_div = 0
        div_months = []

        if 'Monthly Adjusted Time Series' in div_data:
            from datetime import datetime
            now = datetime.now()
            one_year_ago = now.replace(year=now.year - 1)

            for date_str, values in div_data['Monthly Adjusted Time Series'].items():
                date = datetime.strptime(date_str, '%Y-%m-%d')
                if date >= one_year_ago:
                    div_amount = float(values.get('7. dividend amount', 0))
                    if div_amount > 0:
                        annual_div += div_amount
                        if date.month not in div_months:
                            div_months.append(date.month)

        return {'price': price, 'dividend': annual_div, 'div_months': sorted(div_months), 'valid': True, 'source': 'alphavantage'}
    except Exception as e:
        logger.warning(f'{symbol} Alpha Vantage fetch failed: {e}')
        return None

def fetch_symbol(symbol):
    """Fetch symbol data with fallback"""
    # Try Yahoo Finance first
    result = fetch_yahoo(symbol)
    if result:
        return result

    # Fallback to Alpha Vantage
    result = fetch_alpha_vantage(symbol)
    if result:
        logger.info(f'{symbol} fetched from Alpha Vantage fallback')
        return result

    # Symbol not found in any source
    logger.warning(f'{symbol} not found in any data source')
    return {'price': 0, 'dividend': 0, 'div_months': [], 'valid': False, 'source': None}

def get_live_data(symbols):
    if not symbols:
        return {}

    now = time.time()
    if now - cache['timestamp'] < CACHE_TTL and all(s in cache['data'] for s in symbols):
        return {s: cache['data'][s] for s in symbols}

    data = {}
    for symbol in symbols:
        result = fetch_symbol(symbol)
        data[symbol] = result
        source = result.get('source', 'cache')
        status = 'valid' if result.get('valid', True) else 'not found'
        logger.info(f'{symbol}: price={result["price"]}, dividend={result["dividend"]}, source={source}, status={status}')

    cache['data'].update(data)
    cache['timestamp'] = now
    return data

@app.route('/finance/')
def index():
    return render_template('index.html', csrf_token=generate_csrf_token())

@app.route('/finance/api/assets', methods=['GET'])
def get_assets():
    asset_list = list(assets.find({}, {'_id': 0}))
    symbols = [a['symbol'] for a in asset_list]
    live_data = get_live_data(symbols)

    for asset in asset_list:
        symbol = asset['symbol']
        data = live_data.get(symbol, {'price': 0, 'dividend': 0, 'valid': False})
        asset['price'] = data['price']
        asset['value'] = data['price'] * asset['quantity']
        asset['annual_dividend'] = data['dividend'] * asset['quantity']
        asset['monthly_dividend'] = asset['annual_dividend'] / 12
        asset['valid'] = data.get('valid', True)
    return jsonify(asset_list)

@app.route('/finance/api/assets', methods=['POST'])
def add_asset():
    if not verify_csrf_token():
        return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

    data = request.json
    symbol = validate_symbol(data.get('symbol', '').upper())
    if not symbol:
        return jsonify({'status': 'error', 'message': 'Invalid symbol'}), 400

    try:
        quantity = float(data.get('quantity', 0))
        if quantity <= 0:
            return jsonify({'status': 'error', 'message': 'Invalid quantity'}), 400
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid quantity'}), 400

    existing = assets.find_one({'symbol': symbol})
    if existing:
        assets.update_one({'symbol': symbol}, {'$set': {'quantity': quantity}})
    else:
        assets.insert_one({'symbol': symbol, 'quantity': quantity})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/assets/<symbol>', methods=['PUT'])
def update_asset(symbol):
    if not verify_csrf_token():
        return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

    symbol = validate_symbol(symbol.upper())
    if not symbol:
        return jsonify({'status': 'error', 'message': 'Invalid symbol'}), 400

    data = request.json
    try:
        quantity = float(data.get('quantity', 0))
        if quantity <= 0:
            return jsonify({'status': 'error', 'message': 'Invalid quantity'}), 400
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid quantity'}), 400

    assets.update_one({'symbol': symbol}, {'$set': {'quantity': quantity}})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/assets/<symbol>', methods=['DELETE'])
def delete_asset(symbol):
    if not verify_csrf_token():
        return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

    symbol = validate_symbol(symbol.upper())
    if not symbol:
        return jsonify({'status': 'error', 'message': 'Invalid symbol'}), 400

    assets.delete_one({'symbol': symbol})
    return jsonify({'status': 'ok'})

@app.route('/finance/api/import', methods=['POST'])
def import_csv():
    if not verify_csrf_token():
        return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

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
                    symbol = validate_symbol(row[key].strip().upper())
                elif key_lower in ['quantity', 'qty', 'shares', 'amount']:
                    try:
                        quantity = float(row[key].strip())
                        if quantity <= 0:
                            quantity = None
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
        return jsonify({'status': 'error', 'message': 'Failed to process CSV file'}), 400

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
    app.run(host='0.0.0.0', port=5000, debug=False)
