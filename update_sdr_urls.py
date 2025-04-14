#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import yaml
import random
import json
import re
import websocket
import time
import os
import argparse
from bs4 import BeautifulSoup

# Disable warnings
import warnings
warnings.filterwarnings("ignore")

def fetch_kiwisdr_directory(url="https://kiwisdr.com/public/apiv1/geo.json"):
    """
    Fetch the KiwiSDR directory from the specified URL.
    
    Args:
        url (str): URL for the KiwiSDR directory
        
    Returns:
        list: List of KiwiSDR receivers or None if fetching fails
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # KiwiSDR directory is typically in JSON format
        kiwi_data = response.json()
        
        # Process KiwiSDR directory data
        if not kiwi_data:
            print("Empty response from KiwiSDR directory")
            return None
            
        # The geo.json endpoint returns a dictionary with 'rx_list' containing the receivers
        if isinstance(kiwi_data, dict):
            # Check if it has rx_list (geo.json format)
            if "rx_list" in kiwi_data:
                return kiwi_data.get("rx_list", [])
            # Check if it has rxs (older format)
            elif "rxs" in kiwi_data:
                return kiwi_data.get("rxs", [])
        
        # If it's already a list, return it directly
        if isinstance(kiwi_data, list):
            return kiwi_data
            
        print(f"Unexpected KiwiSDR directory format: {type(kiwi_data)}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching KiwiSDR directory: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing KiwiSDR directory JSON: {e}")
        return None
    except Exception as e:
        print(f"Error processing KiwiSDR directory: {e}")
        return None

def test_websocket_connection(receiver_url, timeout=5):
    """Test if a KiwiSDR WebSocket connection works"""
    try:
        # Convert to WebSocket URL if needed
        if not receiver_url.startswith("ws://") and not receiver_url.startswith("wss://"):
            # Check if the URL has a protocol
            if "://" not in receiver_url:
                receiver_url = f"ws://{receiver_url}"
            else:
                receiver_url = receiver_url.replace("http://", "ws://").replace("https://", "wss://")
        
        # Ensure the URL ends with /kiwi
        if not receiver_url.endswith("/kiwi"):
            receiver_url = f"{receiver_url}/kiwi"
        
        # Try to connect
        ws = websocket.create_connection(receiver_url, timeout=timeout)
        
        # Send authentication
        ws.send('SET auth t=kiwi p= need_status=1')
        
        # Wait for response
        response = ws.recv()
        if isinstance(response, bytes):
            response = response.decode('utf-8', errors='ignore')
        
        # Check if the response is valid
        if response.startswith('MSG'):
            ws.close()
            return True, receiver_url
        
        ws.close()
        return False, receiver_url
    except Exception as e:
        return False, receiver_url

def extract_location_from_grid(grid):
    """
    Extract latitude and longitude from a Maidenhead grid locator
    
    Args:
        grid (str): Maidenhead grid locator string
        
    Returns:
        tuple: (latitude, longitude) or (None, None) if conversion fails
    """
    if not grid or not isinstance(grid, str):
        return None, None
    
    try:
        # Clean and standardize the grid locator
        grid = grid.strip().upper()
        if len(grid) < 4:
            return None, None
        
        # First pair encodes longitude
        lon = ((ord(grid[0]) - ord('A')) * 20) - 180
        lon += ((ord(grid[2]) - ord('0')) * 2)
        
        # Add decimal precision if available
        if len(grid) >= 6:
            lon += ((ord(grid[4]) - ord('A')) * 2 / 24) + (1/24)
        else:
            # Center of the grid square
            lon += 1
        
        # Second pair encodes latitude
        lat = ((ord(grid[1]) - ord('A')) * 10) - 90
        lat += (ord(grid[3]) - ord('0'))
        
        # Add decimal precision if available
        if len(grid) >= 6:
            lat += ((ord(grid[5]) - ord('A')) / 24) + (1/48)
        else:
            # Center of the grid square
            lat += 0.5
        
        return lat, lon
    except Exception:
        return None, None

def create_config_entry(rx_data):
    """
    Create a configuration entry for a receiver.
    
    Args:
        rx_data (dict): Receiver data from KiwiSDR directory
        
    Returns:
        dict: Configuration entry with rx_url, name, lat, lon, and optionally, height
    """
    entry = {
        "rx_url": rx_data.get("url"),
        "name": rx_data.get("name"),
        "lat": rx_data.get("lat"),
        "lon": rx_data.get("lng")
    }
    
    # Add height if available
    if "alt" in rx_data:
        entry["height"] = rx_data.get("alt")
        
    return entry

def update_config_file(working_receivers, config_path='config.yaml'):
    """Update the config.yaml file with working receivers"""
    try:
        # Load existing config
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Update receivers
        config['receivers'] = working_receivers
        
        # Create backup of current config
        backup_path = f"{config_path}.bak"
        if os.path.exists(config_path):
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f)
            print(f"Created backup of config file at {backup_path}")
        
        # Write updated config
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, default_flow_style=False)
        
        print(f"✅ Updated config file with {len(working_receivers)} working receivers")
        return True
    except Exception as e:
        print(f"❌ Error updating config file: {e}")
        return False

def fetch_websdr_directory(url="http://websdr.org/"):
    """
    Fetch the WebSDR directory from the specified URL.
    
    Args:
        url (str): URL to fetch WebSDR directory from
        
    Returns:
        list: List of WebSDR receivers or None if fetching fails
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # WebSDR info is in HTML, we need to parse it
        soup = BeautifulSoup(response.text, 'html.parser')
        receivers = []
        
        # Extract WebSDR listings from the table
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and (href.startswith('http://') or href.startswith('https://')) and 'websdr' in href:
                receivers.append({
                    'url': href,
                    'name': link.text.strip() or "Unknown WebSDR"
                })
        
        return receivers
    except requests.RequestException as e:
        print(f"Error fetching WebSDR directory: {e}")
        return None
    except Exception as e:
        print(f"Error processing WebSDR directory: {e}")
        return None

def process_websdr_data(receivers):
    """
    Process WebSDR data into a consistent format.
    
    Args:
        receivers (list): List of raw WebSDR receiver data
        
    Returns:
        list: List of processed receivers with consistent format
    """
    processed_receivers = []
    
    for receiver in receivers:
        processed_receiver = {
            "url": receiver.get("url", ""),
            "name": receiver.get("name", "Unknown WebSDR"),
            "type": "websdr",
            "lat": 0,  # WebSDR HTML doesn't provide coordinates
            "lon": 0,
            "users_connected": 0,
            "users_limit": 0,
            "status": "online"  # Assume online since it's in the directory
        }
        
        # Try to geocode the receiver
        processed_receiver = geocode_websdr(processed_receiver)
        
        processed_receivers.append(processed_receiver)
    
    return processed_receivers

def process_kiwisdr_data(receivers):
    """
    Process KiwiSDR data into a consistent format.
    
    Args:
        receivers (list): List of raw KiwiSDR receiver data
        
    Returns:
        list: List of processed receivers with consistent format
    """
    processed_receivers = []
    
    for receiver in receivers:
        # Skip invalid entries
        if not receiver or not isinstance(receiver, dict):
            continue
            
        # Get the URL (can be in different fields depending on API version)
        url = receiver.get('url', '')
        if not url and 'sdr_url' in receiver:
            url = receiver.get('sdr_url', '')
        
        # Ensure URL has http:// prefix
        if url and not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
            
        # Get coordinates (can be in different formats)
        lat = 0
        lon = 0
        
        # Try direct lat/lon fields
        if 'lat' in receiver:
            try:
                lat = float(receiver.get('lat', 0))
            except (ValueError, TypeError):
                lat = 0
                
        if 'lon' in receiver:
            try:
                lon = float(receiver.get('lon', 0))
            except (ValueError, TypeError):
                lon = 0
                
        # Try lng instead of lon
        if lon == 0 and 'lng' in receiver:
            try:
                lon = float(receiver.get('lng', 0))
            except (ValueError, TypeError):
                lon = 0
                
        # Process grid locator if present
        if lat == 0 and lon == 0 and 'grid' in receiver:
            grid_lat, grid_lon = extract_location_from_grid(receiver.get('grid', ''))
            if grid_lat is not None and grid_lon is not None:
                lat = grid_lat
                lon = grid_lon
        
        # Create the processed receiver entry
        processed_receiver = {
            "url": url,
            "name": receiver.get('name', 'Unknown KiwiSDR'),
            "type": "kiwisdr",
            "lat": lat,
            "lon": lon,
            "users_connected": int(receiver.get('users', 0)),
            "users_limit": int(receiver.get('users_max', 0)),
            "status": "online" if receiver.get('status', 0) == 1 else "offline"
        }
        processed_receivers.append(processed_receiver)
    
    return processed_receivers

def test_websdr_connection(websdr_url, timeout=5):
    """
    Test if a WebSDR connection works by sending a request to the URL.
    
    Args:
        websdr_url (str): The URL of the WebSDR to test
        timeout (int): Timeout in seconds for the request
        
    Returns:
        bool: True if the connection is successful, False otherwise
    """
    try:
        # Ensure URL has http:// prefix
        if not websdr_url.startswith('http://') and not websdr_url.startswith('https://'):
            websdr_url = f"http://{websdr_url}"
            
        response = requests.get(websdr_url, timeout=timeout)
        
        # Check if the response contains typical WebSDR content
        if response.status_code == 200:
            content = response.text.lower()
            if 'websdr' in content and ('radio' in content or 'receiver' in content):
                return True
        
        return False
    except requests.RequestException:
        return False
    except Exception:
        return False

def generate_yaml_config(receivers, output_file='config.yaml'):
    """
    Generate a YAML configuration file from the SDR directory.
    
    Args:
        receivers (list): List of SDR receivers
        output_file (str): Output YAML file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create config structure
        config = {
            'receivers': []
        }
        
        # Convert receivers to config format
        for rx in receivers:
            if rx.get('status', '') != 'online':
                continue
                
            config_entry = {
                'rx_url': rx.get('url', ''),
                'name': rx.get('name', 'Unknown SDR'),
                'lat': float(rx.get('lat', 0)),
                'lon': float(rx.get('lon', 0))
            }
            
            # Add additional fields if available
            if 'users_connected' in rx and rx['users_connected'] > 0:
                config_entry['users'] = rx['users_connected']
                
            if 'users_limit' in rx and rx['users_limit'] > 0:
                config_entry['max_users'] = rx['users_limit']
                
            # Add receiver type
            config_entry['type'] = rx.get('type', 'unknown')
            
            config['receivers'].append(config_entry)
        
        # Create backup of existing file
        if os.path.exists(output_file):
            backup_path = f"{output_file}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                if os.path.exists(output_file):
                    with open(output_file, 'r', encoding='utf-8') as original:
                        f.write(original.read())
            print(f"Created backup of existing config at {backup_path}")
        
        # Write the config file
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
        print(f"✅ Generated YAML config with {len(config['receivers'])} receivers at {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error generating YAML config: {e}")
        return False

def geocode_websdr(receiver):
    """
    Attempt to geocode a WebSDR receiver based on its name or URL.
    
    Args:
        receiver (dict): WebSDR receiver data
        
    Returns:
        dict: Receiver with updated lat/lon if geocoding was successful
    """
    # List of location keywords that might be in the receiver name
    location_patterns = [
        r"(in|at|near) ([A-Za-z\s]+)",  # "in City", "at Location", "near Place"
        r"([A-Za-z]+), *([A-Za-z]{2})",  # "City, State" pattern (US)
        r"([A-Za-z\s]+) \(([A-Za-z]{2})\)"  # "City (State)" pattern
    ]
    
    # Simple geocoding database for common SDR locations
    # In a real implementation, you might use a proper geocoding service
    location_db = {
        "twente": (52.2387, 6.8518),      # Twente, Netherlands
        "netherlands": (52.1326, 5.2913), # Netherlands
        "amsterdam": (52.3676, 4.9041),   # Amsterdam, Netherlands
        "bonaire": (12.1784, -68.2385),   # Bonaire
        "university": (40.4237, -86.9212), # Default for universities if no other location
        "tokyo": (35.6762, 139.6503),     # Tokyo, Japan
        "switzerland": (46.8182, 8.2275), # Switzerland
        "zurich": (47.3769, 8.5417),      # Zurich, Switzerland
        "norway": (60.4720, 8.4689),      # Norway
        "trondheim": (63.4305, 10.3951),  # Trondheim, Norway
        "uk": (55.3781, -3.4360),         # United Kingdom
        "london": (51.5074, -0.1278),     # London, UK
        "germany": (51.1657, 10.4515),    # Germany
        "sweden": (60.1282, 18.6435),     # Sweden
        "finland": (61.9241, 25.7482),    # Finland
        "australia": (-25.2744, 133.7751), # Australia
        "sydney": (-33.8688, 151.2093),   # Sydney, Australia
        "canada": (56.1304, -106.3468),   # Canada
        "usa": (37.0902, -95.7129),       # United States
        "denmark": (56.2639, 9.5018),     # Denmark
        "italy": (41.8719, 12.5674),      # Italy
        "spain": (40.4637, -3.7492),      # Spain
        "portugal": (39.3999, -8.2245),   # Portugal
        "france": (46.2276, 2.2137),      # France
        "paris": (48.8566, 2.3522),       # Paris, France
        "belgium": (50.5039, 4.4699),     # Belgium
        "poland": (51.9194, 19.1451),     # Poland
        "austria": (47.5162, 14.5501),    # Austria
        "hungary": (47.1625, 19.5033),    # Hungary
        "greece": (39.0742, 21.8243),     # Greece
        "russia": (61.5240, 105.3188),    # Russia
        "brazil": (-14.2350, -51.9253),   # Brazil
    }
    
    try:
        name = receiver.get("name", "").lower()
        url = receiver.get("url", "").lower()
        
        location_found = None
        
        # First check for location names in the receiver name or URL
        for keyword, coords in location_db.items():
            if keyword in name or keyword in url:
                receiver["lat"] = coords[0]
                receiver["lon"] = coords[1]
                location_found = keyword
                break
                
        # Try to extract location using patterns if not found yet
        if not location_found:
            for pattern in location_patterns:
                for text in [name, url]:
                    match = re.search(pattern, text)
                    if match:
                        # Get the last group which likely contains the location
                        location = match.group(match.lastindex).lower()
                        if location in location_db:
                            receiver["lat"] = location_db[location][0]
                            receiver["lon"] = location_db[location][1]
                            location_found = location
                            break
                if location_found:
                    break
        
        # Print message if geocoding was successful
        if location_found:
            print(f"📍 Geocoded WebSDR '{receiver.get('name')}' to {location_found.title()} ({receiver['lat']}, {receiver['lon']})")
        
        return receiver
    except Exception as e:
        print(f"Error geocoding {receiver.get('name', 'unknown')}: {e}")
        return receiver

def create_sample_data():
    """
    Create sample SDR data for testing when online directories are unavailable.
    
    Returns:
        tuple: (kiwisdr_sample, websdr_sample) with sample data
    """
    kiwisdr_sample = [
        {
            "name": "KiwiSDR Twente",
            "url": "http://twente.kiwisdr.com:8073/",
            "lat": 52.2387,
            "lng": 6.8518,
            "users": 20,
            "users_max": 50,
            "status": 1
        },
        {
            "name": "KiwiSDR Tokyo",
            "url": "http://tokyo.kiwisdr.com:8073/",
            "lat": 35.6762,
            "lng": 139.6503,
            "users": 15,
            "users_max": 40,
            "status": 1
        },
        {
            "name": "KiwiSDR Sydney",
            "url": "http://sydney.kiwisdr.com:8073/",
            "lat": -33.8688,
            "lng": 151.2093,
            "users": 10,
            "users_max": 30,
            "status": 1
        },
        {
            "name": "KiwiSDR London",
            "url": "http://london.kiwisdr.com:8073/",
            "lat": 51.5074,
            "lng": -0.1278,
            "users": 12,
            "users_max": 35,
            "status": 1
        },
        {
            "name": "KiwiSDR New York",
            "url": "http://newyork.kiwisdr.com:8073/",
            "lat": 40.7128,
            "lng": -74.0060,
            "users": 18,
            "users_max": 45,
            "status": 1
        }
    ]
    
    websdr_sample = [
        {
            "name": "Twente WebSDR",
            "url": "http://websdr.ewi.utwente.nl:8901/"
        },
        {
            "name": "University of Eindhoven WebSDR",
            "url": "http://websdr.tue.nl:8901/"
        },
        {
            "name": "Swiss WebSDR",
            "url": "http://websdr.he.swiss:8901/"
        },
        {
            "name": "Norway WebSDR",
            "url": "http://websdr.norway.com:8901/"
        },
        {
            "name": "UK WebSDR London",
            "url": "http://websdr.london.uk:8901/"
        }
    ]
    
    return kiwisdr_sample, websdr_sample

def main():
    """Main function to fetch SDR directories and create configuration file."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch and process SDR receiver directories')
    parser.add_argument('--output', '-o', default='sdr_directory.json', help='Output JSON file path')
    parser.add_argument('--yaml-config', '-y', help='Generate YAML config file at specified path')
    parser.add_argument('--kiwi-url', default='https://kiwisdr.com/public/apiv1/geo.json', help='KiwiSDR directory URL')
    parser.add_argument('--websdr-url', default='http://websdr.org/', help='WebSDR directory URL')
    parser.add_argument('--verify', '-v', action='store_true', help='Verify receiver connections')
    parser.add_argument('--timeout', '-t', type=int, default=5, help='Connection timeout in seconds')
    parser.add_argument('--kiwi-only', action='store_true', help='Only process KiwiSDR receivers')
    parser.add_argument('--websdr-only', action='store_true', help='Only process WebSDR receivers')
    parser.add_argument('--use-sample-data', '-s', action='store_true', help='Use sample data instead of fetching from directories')
    
    args = parser.parse_args()
    
    all_receivers = []
    use_sample_data = args.use_sample_data
    
    # Fetch or create KiwiSDR data
    if not args.websdr_only:
        if use_sample_data:
            kiwisdr_sample, _ = create_sample_data()
            kiwi_receivers = kiwisdr_sample
            print(f"Using {len(kiwi_receivers)} sample KiwiSDR receivers")
        else:
            kiwi_receivers = fetch_kiwisdr_directory(args.kiwi_url)
        
        if kiwi_receivers:
            kiwi_receivers = process_kiwisdr_data(kiwi_receivers)
            if not use_sample_data:
                print(f"Fetched {len(kiwi_receivers)} KiwiSDR receivers")
            all_receivers.extend(kiwi_receivers)
        else:
            print("Failed to fetch KiwiSDR directory, using sample data")
            kiwisdr_sample, _ = create_sample_data()
            kiwi_receivers = process_kiwisdr_data(kiwisdr_sample)
            all_receivers.extend(kiwi_receivers)
            print(f"Using {len(kiwi_receivers)} sample KiwiSDR receivers")
    
    # Fetch or create WebSDR data
    if not args.kiwi_only:
        if use_sample_data:
            _, websdr_sample = create_sample_data()
            websdr_receivers = websdr_sample
            print(f"Using {len(websdr_receivers)} sample WebSDR receivers")
        else:
            websdr_receivers = fetch_websdr_directory(args.websdr_url)
        
        if websdr_receivers:
            websdr_receivers = process_websdr_data(websdr_receivers)
            if not use_sample_data:
                print(f"Fetched {len(websdr_receivers)} WebSDR receivers")
            all_receivers.extend(websdr_receivers)
        else:
            print("Failed to fetch WebSDR directory, using sample data")
            _, websdr_sample = create_sample_data()
            websdr_receivers = process_websdr_data(websdr_sample)
            all_receivers.extend(websdr_receivers)
            print(f"Using {len(websdr_receivers)} sample WebSDR receivers")
    
    print(f"Total receivers: {len(all_receivers)}")
    
    # Skip verification when using sample data if not explicitly requested
    if args.verify and not (use_sample_data and not args.verify):
        verified_receivers = []
        print("\nTesting receiver connections...")
        
        for receiver in all_receivers:
            try:
                if receiver["type"] == "kiwisdr":
                    # Use sample data status for sample data
                    if use_sample_data:
                        receiver["status"] = "online"
                        verified_receivers.append(receiver)
                        print(f"✅ KiwiSDR simulation: {receiver['name']}")
                    else:
                        # Test KiwiSDR WebSocket connection
                        status, _ = test_websocket_connection(receiver["url"], timeout=args.timeout)
                        if status:
                            receiver["status"] = "online"
                            verified_receivers.append(receiver)
                            print(f"✅ KiwiSDR online: {receiver['name']}")
                        else:
                            print(f"❌ KiwiSDR offline: {receiver['name']}")
                elif receiver["type"] == "websdr":
                    # Use sample data status for sample data
                    if use_sample_data:
                        receiver["status"] = "online"
                        verified_receivers.append(receiver)
                        print(f"✅ WebSDR simulation: {receiver['name']}")
                    else:
                        # Test WebSDR HTTP connection
                        if test_websdr_connection(receiver["url"], timeout=args.timeout):
                            receiver["status"] = "online"
                            verified_receivers.append(receiver)
                            print(f"✅ WebSDR online: {receiver['name']}")
                        else:
                            print(f"❌ WebSDR offline: {receiver['name']}")
            except Exception as e:
                print(f"❌ Error testing {receiver['name']}: {e}")
        
        print(f"\nVerified online receivers: {len(verified_receivers)} out of {len(all_receivers)}")
        output_receivers = verified_receivers
    else:
        # When using sample data without verification, mark all as online
        if use_sample_data:
            for receiver in all_receivers:
                receiver["status"] = "online"
        output_receivers = all_receivers
    
    # Write receivers to a JSON file
    with open(args.output, 'w') as f:
        json.dump(output_receivers, f, indent=2)
    
    print(f"Saved SDR directory to {args.output}")
    
    # Generate YAML config if requested
    if args.yaml_config:
        generate_yaml_config(output_receivers, args.yaml_config)

if __name__ == "__main__":
    main() 