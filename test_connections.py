#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import yaml
import json
import time
import ssl

# Disable SSL certificate verification if needed
websocket.enableTrace(True)

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_connection(url):
    print(f"Testing connection to {url}...")
    try:
        # Create WebSocket connection 
        ws = websocket.create_connection(url, timeout=10, sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # Send auth message
        auth_msg = 'SET auth t=kiwi p= need_status=1'
        print(f"Sending: {auth_msg}")
        ws.send(auth_msg)
        
        # Wait for response
        print("Waiting for response...")
        for _ in range(5):  # Try a few times
            response = ws.recv()
            print(f"Received: {response[:100]}..." if len(response) > 100 else f"Received: {response}")
            
            # Check if response indicates success
            if response.startswith('MSG'):
                print("✅ Connection successful!")
                break
            
            time.sleep(1)
        
        # Send additional setup
        setup_msg = {"name": "test_client", "ver": "1.0"}
        ident_msg = f'SET ident_user m="{json.dumps(setup_msg)}"'
        print(f"Sending: {ident_msg}")
        ws.send(ident_msg)
        
        # Close connection
        ws.close()
        return True
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
    
    print(f"Testing {len(receivers)} receivers...")
    print("-" * 50)
    
    for i, receiver in enumerate(receivers):
        name = receiver.get('name', f"Receiver {i}")
        url = receiver.get('url')
        
        if not url:
            print(f"Skipping {name}: No URL provided")
            results.append((name, url, False, "No URL provided"))
            continue
        
        print(f"\nTesting {name} at {url}")
        success = test_connection(url)
        results.append((name, url, success, ""))
        print("-" * 50)
    
    # Summary
    print("\n\nCONNECTION TEST SUMMARY")
    print("=" * 50)
    working = 0
    for name, url, success, error in results:
        status = "✅ WORKING" if success else "❌ FAILED"
        if success:
            working += 1
        print(f"{name}: {status}")
    
    print(f"\n{working} out of {len(results)} receivers are working")

if __name__ == "__main__":
    main() 