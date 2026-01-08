from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import hashlib
import json
from datetime import datetime
from pathlib import Path
import threading
import time
import os

app = Flask(__name__)

WEBSITES = [
    {"name": "Simply Mary", "url": "https://simplymary.co/"},
    {"name": "Hello Mary", "url": "https://shophellomary.com/"},
    {"name": "Crysp", "url": "https://crysp.co/"},
    {"name": "Southern Harvest Hemp", "url": "https://southernharvesthemp.com/"},
    {"name": "Quantum Exotics", "url": "https://www.quantumexotics.com/"},
    {"name": "JGrows 420", "url": "https://jgrows420.com/"},
    {"name": "BR Bubble", "url": "https://brbubble.com/"},
    {"name": "Kache Shop", "url": "https://kache.shop/"}
]

CHECK_INTERVAL = 1800
DATA_DIR = Path("web_tracker_data")
DATA_DIR.mkdir(exist_ok=True)

tracker_data = {
    "last_check": None,
    "websites": {},
    "recent_changes": []
}

class WebStockTracker:
    def __init__(self, websites):
        self.websites = websites
        self.data_file = DATA_DIR / "tracker_state.json"
        self.load_state()
    
    def load_state(self):
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    tracker_data.update(data)
        except:
            pass
    
    def save_state(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(tracker_data, f)
        except:
            pass
    
    def fetch_website(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=15)
            return response.text
        except:
            return None
    
    def extract_info(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            products = []
            for selector in ['div.product', '.product-item', 'article.product']:
                elements = soup.select(selector)
                if elements:
                    for elem in elements:
                        name = elem.select_one('h2, h3, h4')
                        if name:
                            products.append(name.get_text(strip=True))
            text = soup.get_text(strip=True)
            return {
                'product_count': len(products),
                'products': products[:20],
                'content_hash': hashlib.md5(text.encode()).hexdigest()
            }
        except:
            return {'product_count': 0, 'products': [], 'content_hash': ''}
    
    def check_site(self, site):
        url = site['url']
        name = site['name']
        print(f"Checking {name}...")
        
        html = self.fetch_website(url)
        if not html:
            return
        
        current = self.extract_info(html)
        previous = tracker_data['websites'].get(url, {})
        
        changes = []
        if previous:
            if previous.get('content_hash') != current['content_hash']:
                changes.append('Content updated')
            diff = current['product_count'] - previous.get('product_count', 0)
            if diff > 0:
                changes.append(f'{diff} new products')
            elif diff < 0:
                changes.append(f'{abs(diff)} products removed')
        
        tracker_data['websites'][url] = {
            'name': name,
            'url': url,
            'product_count': current['product_count'],
            'products': current['products'],
            'content_hash': current['content_hash'],
            'last_checked': datetime.now().isoformat(),
            'status': 'ok'
        }
        
        if changes:
            tracker_data['recent_changes'].insert(0, {
                'name': name,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'changes': changes
            })
            tracker_data['recent_changes'] = tracker_data['recent_changes'][:50]
    
    def check_all_sites(self):
        print("Starting check...")
        try:
            for site in self.websites:
                self.check_site(site)
                time.sleep(2)
            tracker_data['last_check'] = datetime.now().isoformat()
            self.save_state()
            print("Check complete!")
        except Exception as e:
            print(f"Error: {e}")
    
    def run_background(self):
        while True:
            try:
                self.check_all_sites()
            except:
                pass
            time.sleep(CHECK_INTERVAL)

tracker = WebStockTracker(WEBSITES)

def start_tracker():
    print("Starting background tracker...")
    thread = threading.Thread(target=tracker.check_all_sites, daemon=True)
    thread.start()
    time.sleep(1)
    thread2 = threading.Thread(target=tracker.run_background, daemon=True)
    thread2.start()

start_tracker()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    return jsonify(tracker_data)

@app.route('/api/refresh')
def api_refresh():
    thread = threading.Thread(target=tracker.check_all_sites, daemon=True)
    thread.start()
    return jsonify({"status": "refresh_started"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
