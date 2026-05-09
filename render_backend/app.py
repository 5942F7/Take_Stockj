from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, time

app = Flask(__name__)
CORS(app)

@app.get('/')
def home():
    return jsonify({'ok': True, 'name': 'AI股神拍圖版 V10 API'})

@app.get('/api/quote')
def quote():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'error': 'missing code'}), 400
    channels = [f'tse_{code}.tw', f'otc_{code}.tw']
    for ch in channels:
        url = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp'
        try:
            r = requests.get(url, params={'ex_ch': ch, 'json': '1', '_': int(time.time()*1000)}, timeout=5, headers={'User-Agent':'Mozilla/5.0'})
            data = r.json()
            arr = data.get('msgArray') or []
            if arr:
                q = arr[0]
                price = float(q.get('z') or q.get('y') or q.get('o') or 0)
                y = float(q.get('y') or 0)
                high = float(q.get('h') or price)
                low = float(q.get('l') or price)
                if price and y:
                    return jsonify({
                        'code': code,
                        'name': q.get('n') or '自選股',
                        'price': price,
                        'yesterday': y,
                        'high': high,
                        'low': low,
                        'change': round(price-y, 2),
                        'source': 'TWSE' if ch.startswith('tse') else 'TPEx'
                    })
        except Exception:
            pass
    return jsonify({'error': 'quote failed or code not found'}), 502

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
