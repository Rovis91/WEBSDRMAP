#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import yaml
import json
import time
import ssl
import threading

# Disable excessive logging
websocket.enableTrace(False)

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_connection(url, name):
    print(f"Testing connection to {name} at {url}...")
    try:
        # Create WebSocket connection with no SSL verification
        ws = websocket.create_connection(url, timeout=10)
        
        # Send auth message
        auth_msg = 'SET auth t=kiwi p= need_status=1'
        print(f"Sending auth message...")
        ws.send(auth_msg)
        
        # Wait for response
        response = ws.recv()
        if isinstance(response, bytes):
            try:
                response = response.decode('utf-8', errors='ignore')
            except:
                response = str(response)
        
        print(f"Response received: {response[:100]}..." if len(str(response)) > 100 else f"Response received: {response}")
        
        # Check if response indicates success
        if response.startswith('MSG'):
            print(f"✅ Connection to {name} successful!")
            
            # Setup client identity
            setup_msg = {"name": "test_client", "ver": "1.0"}
            ident_msg = f'SET ident_user m="{json.dumps(setup_msg)}"'
            ws.send(ident_msg)
            
            # Close connection
            ws.close()
            return True
        else:
            print(f"❌ Connection to {name} failed: Unexpected response")
            ws.close()
            return False
            
    except Exception as e:
        print(f"❌ Connection to {name} failed: {e}")
        return False

def main():
    config = load_config()
    receivers = config.get('receivers', [])
    
    if not receivers:
        print("No receivers configured in config.yaml")
        return
    
    results = []
    
    print(f"Testing {len(receivers)} WebSocket connections...")
    print("-" * 50)
    
    # Test each receiver
    for receiver in receivers:
        name = receiver.get('name', "Unnamed receiver")
        url = receiver.get('url')
        
        if not url:
            print(f"Skipping {name}: No URL provided")
            results.append((name, url, False))
            continue
        
        success = test_connection(url, name)
        results.append((name, url, success))
        print("-" * 50)
    
    # Print summary
    print("\nCONNECTION TEST SUMMARY")
    print("=" * 50)
    working = 0
    for name, url, success in results:
        status = "✅ WORKING" if success else "❌ FAILED"
        if success:
            working += 1
        print(f"{name}: {status}")
    
    print(f"\n{working} out of {len(results)} receivers are working")
    
    if working == 0:
        print("\n⚠️ TROUBLESHOOTING TIPS:")
        print("1. Check if the KiwiSDR servers are online")
        print("2. Try different KiwiSDR servers from http://kiwisdr.com/public/")
        print("3. Some KiwiSDR servers may block programmatic access")
        print("4. Make sure your network allows WebSocket connections")

if __name__ == "__main__":
    main() 