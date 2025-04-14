#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import yaml
import re

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_http_connection(wss_url):
    # Convert WebSocket URL to HTTP URL
    http_url = wss_url.replace('wss://', 'http://')
    http_url = re.sub(r'/kiwi$', '/', http_url)
    
    print(f"Testing HTTP connection to {http_url}...")
    try:
        response = requests.get(http_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ HTTP Connection successful! Status code: {response.status_code}")
            if "Kiwi" in response.text or "SDR" in response.text:
                print("✅ Content seems to be a KiwiSDR page")
            else:
                print("⚠️ Content doesn't appear to be a KiwiSDR page")
            return True
        else:
            print(f"❌ HTTP Connection failed. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    config = load_config()
    receivers = config.get('receivers', [])
    
    if not receivers:
        print("No receivers configured in config.yaml")
        return
    
    results = []
    working_urls = []
    
    print(f"Testing {len(receivers)} receivers using HTTP...")
    print("-" * 50)
    
    for i, receiver in enumerate(receivers):
        name = receiver.get('name', f"Receiver {i}")
        url = receiver.get('url')
        
        if not url:
            print(f"Skipping {name}: No URL provided")
            continue
        
        print(f"\nTesting {name}")
        success = test_http_connection(url)
        results.append((name, url, success))
        
        if success:
            # Create HTTP WebSocket URL (ws instead of wss)
            ws_url = url.replace('wss://', 'ws://')
            working_urls.append((name, ws_url))
        
        print("-" * 50)
    
    # Summary
    print("\n\nCONNECTION TEST SUMMARY")
    print("=" * 50)
    working = 0
    for name, url, success in results:
        status = "✅ WORKING" if success else "❌ FAILED"
        if success:
            working += 1
        print(f"{name}: {status}")
    
    print(f"\n{working} out of {len(results)} receivers are accessible via HTTP")
    
    # Print working URLs
    if working_urls:
        print("\nWorking URLs (updated to ws:// from wss://):")
        for name, url in working_urls:
            print(f"{name}: {url}")
        
        print("\nUpdated config.yaml receivers section:")
        print("receivers:")
        for name, url in working_urls:
            print(f"  - name: \"{name}\"")
            print(f"    url: \"{url}\"")
            # Find the original receiver to get location data
            for receiver in receivers:
                if receiver.get('name') == name:
                    loc = receiver.get('location', {})
                    print(f"    location:")
                    print(f"      latitude: {loc.get('latitude', 0)}")
                    print(f"      longitude: {loc.get('longitude', 0)}")
                    break

if __name__ == "__main__":
    main() 