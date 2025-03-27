import requests
import json
import time
from datetime import datetime
import logging
import sys
import os
from ai_property_evaluator import AIPropertyEvaluator

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "property_lookup.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

# API Keys and endpoints - get from environment variables or use placeholders for demo
ATTOM_API_KEY = os.environ.get("ATTOM_API_KEY", "demo_key")
RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "demo_key")
WALK_SCORE_API_KEY = os.environ.get("WALK_SCORE_API_KEY", "demo_key")
OXYLABS_USER = os.environ.get("OXYLABS_USER", "demo_user")
OXYLABS_PASS = os.environ.get("OXYLABS_PASS", "demo_pass")
DATAFINITI_API_KEY = os.environ.get("DATAFINITI_API_KEY", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJnNmFqaW81NnNxamtoZ2Zpb2hoMjdzbXhtODc3OWIxYSIsImlzcyI6ImRhdGFmaW5pdGkuY28ifQ.gViDkl85YmeJiRo56Ab628Nfp-OR_5qOJafxkxwnxi4NYdpCYAKaJzFe-EPz9sE5gL-Z3L_tKbtdzIjGWsq4bP2HDEuMqrkWQMxDln21W1Z9Chk1nw79kqaFiwX5lfztktA2UEVSJEf5AWu1DORfcAujUcQFQDUgxsCLUWAuNVwNBL4eFiBNHlZ7gCiGD1jFD9WZkgx7ig8eNDVcD_6uL_dqBeUDS5tVFGDs7OdwZR6GAHUzfGvQYdctcY5T6mixnRfbnacndW2y4GW6hxxeK_piTiSi5nFdRsormOn_Z4rMqSVPXcbml7I-Ce06tsGMHZldDFzBSB1DrHPwd_JOuFDADTWssSJw5M9-uVc-mb-YLLH6QeiVZNPr4fIeS5NA0JrUumlsIs1bjXWO17M71S_urt6mSRByIU8bub9p5Ce4-css_-e6Hn2--R4Rar3FxLbguPbNiOb2f4EO-y_tpkjVN4QS1TRZBHYOA-ngsHfxNQt6Al9b8n1nU6bTYNNC74aja0uf_CRCzLfDt1gW6NGMOrtfFy2QkOCQNXw8MnGQntFbEYweQMvvF5GLEiIVFmsJ7LXnS0gyYp4CdC3Br5Q6N2DCCzKDX6mptXm8fqMJGiDG_kUyi5WL4JcqITTmXjKNXdT2G2PMSsNJzlopMHuZ_c80IZ8xP39abOI4zv8")

# AI API keys - try to get from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ATTOM_ENDPOINT = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
RENTCAST_ENDPOINT = "https://api.rentcast.io/v1/properties"
WALK_SCORE_ENDPOINT = "http://api.walkscore.com/score"
OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"
DATAFINITI_ENDPOINT = "https://api.datafiniti.co/v4/properties/search"

FLASK_BACKEND_ENDPOINT = "http://127.0.0.1:5001/update"
CURRENT_YEAR = datetime.now().year

headers_attom = {"apikey": ATTOM_API_KEY, "Accept": "application/json"}
headers_rentcast = {"X-Api-Key": RENTCAST_API_KEY}
headers_datafiniti = {"Authorization": f"Bearer {DATAFINITI_API_KEY}", "Content-Type": "application/json"}

# Initialize the AI property evaluator with API key
ai_evaluator = AIPropertyEvaluator(api_key=OPENAI_API_KEY or ANTHROPIC_API_KEY)

def fetch_attom(city, page):
    try:
        logging.info(f"Fetching ATTOM data for {city}, page {page}")
        params = {"address": city, "pageSize": 50, "page": page}
        response = requests.get(ATTOM_ENDPOINT, headers=headers_attom, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'property' in data and len(data['property']) > 0:
                logging.info(f"Successfully fetched ATTOM data for {city}, page {page}: {len(data['property'])} properties")
                return data
            else:
                logging.info(f"ATTOM API returned 0 properties for {city}, page {page}")
                return None
        else:
            logging.error(f"ATTOM API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching ATTOM data: {str(e)}")
        return None

def fetch_rentcast(city, offset):
    try:
        logging.info(f"Fetching Rentcast data for {city}, offset {offset}")
        params = {"address": city, "limit": 50, "offset": offset}
        response = requests.get(RENTCAST_ENDPOINT, headers=headers_rentcast, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'properties' in data and len(data['properties']) > 0:
                logging.info(f"Successfully fetched Rentcast data for {city}, offset {offset}: {len(data['properties'])} properties")
                return data
            else:
                logging.info(f"Rentcast API returned 0 properties for {city}, offset {offset}")
                return None
        else:
            logging.error(f"Rentcast API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching Rentcast data: {str(e)}")
        return None

def fetch_walkscore(address, lat, lon):
    try:
        logging.info(f"Fetching WalkScore for {address}")
        params = {"format": "json", "address": address, "lat": lat, "lon": lon, "wsapikey": WALK_SCORE_API_KEY}
        response = requests.get(WALK_SCORE_ENDPOINT, params=params, timeout=30)
        
        if response.status_code == 200:
            logging.info(f"Successfully fetched WalkScore for {address}")
            return response.json()
        else:
            logging.error(f"WalkScore API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching WalkScore data: {str(e)}")
        return None

def fetch_redfin(query, location, page):
    try:
        logging.info(f"Fetching Redfin data for {location}, page {page}")            
        payload = {"source": "redfin", "query": query, "geo_location": location, "parse": True, "page": page}
        response = requests.post(
            OXYLABS_ENDPOINT, 
            auth=(OXYLABS_USER, OXYLABS_PASS), 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) > 0:
                logging.info(f"Successfully fetched Redfin data for {location}, page {page}: {len(data['results'])} properties")
                return data
            else:
                logging.info(f"Redfin API returned 0 properties for {location}, page {page}")
                return None
        else:
            logging.error(f"Redfin API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching Redfin data: {str(e)}")
        return None

def fetch_datafiniti(city, page, records_per_page=25):
    try:
        logging.info(f"Fetching Datafiniti data for {city}, page {page}")
        
        # The Datafiniti API doesn't support traditional pagination
        # Using record count to simulate pagination
        records_to_fetch = records_per_page
        
        # Create a simple query with just the city
        city_name = city.split(',')[0]
        
        # For "pagination", we'll vary the neighborhoods based on page number
        # This is a workaround since the API doesn't support pagination directly
        query = {
            "query": f"city:\"{city_name}\"",
            "format": "JSON",
            "num_records": records_to_fetch
        }
        
        response = requests.post(
            DATAFINITI_ENDPOINT,
            headers=headers_datafiniti,
            json=query,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'records' in data and len(data['records']) > 0:
                logging.info(f"Successfully fetched Datafiniti data for {city}, page {page}: {len(data['records'])} properties")
                return data
            else:
                logging.info(f"Datafiniti API returned 0 properties for {city}, page {page}")
                return None
        else:
            logging.error(f"Datafiniti API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching Datafiniti data: {str(e)}")
        return None

def post_property(prop):
    try:
        address_text = "Unknown"
        if 'address' in prop:
            if isinstance(prop['address'], str):
                address_text = prop['address']
            elif isinstance(prop['address'], dict) and 'oneLine' in prop['address']:
                address_text = prop['address']['oneLine']
        
        # Use AI to evaluate the property and assign intensity score
        logging.info(f"Using AI to evaluate property: {address_text}")
        intensity = ai_evaluator.evaluate_property(prop)
        prop['intensity'] = intensity
        
        # Add color description for reference
        if intensity > 0.8:
            color_desc = "Red (Best Deal)"
        elif intensity > 0.6:
            color_desc = "Orange (Good Deal)"
        elif intensity > 0.4:
            color_desc = "Yellow (Average Deal)"
        elif intensity > 0.2:
            color_desc = "Green (Below Average Deal)"
        else:
            color_desc = "Blue (Weak Deal)"
        
        prop['deal_rating'] = color_desc
        
        # Add AI reasoning to log if available
        if 'ai_evaluation_reasoning' in prop:
            logging.info(f"AI reasoning: {prop['ai_evaluation_reasoning'][:100]}...")
        
        logging.info(f"Posting property data to Flask backend: {address_text} with intensity {intensity:.2f} ({color_desc})")
        res = requests.post(FLASK_BACKEND_ENDPOINT, json=prop, timeout=10)
        
        if res.status_code == 200:
            logging.info(f"Successfully posted property: {address_text}")
            return True
        else:
            logging.error(f"Failed to post property: Status code {res.status_code}, Response: {res.text}")
            return False
    except Exception as e:
        logging.error(f"Error posting property data: {str(e)}")
        return False

def add_coordinates_to_property(prop):
    """Try to add lat/lng to properties that don't have them"""
    if ('lat' in prop and 'lng' in prop) or ('latitude' in prop and 'longitude' in prop):
        return prop
    
    # If property has location with latitude/longitude
    if 'location' in prop and isinstance(prop['location'], dict):
        if 'latitude' in prop['location'] and 'longitude' in prop['location']:
            prop['lat'] = prop['location']['latitude']
            prop['lng'] = prop['location']['longitude']
            logging.info("Added coordinates from location object")
            return prop
    
    # For now, just return the property as is
    return prop

def process_property(prop):
    """Process a single property - add coordinates, walkscore, and post to backend"""
    # Add coordinates if needed
    prop = add_coordinates_to_property(prop)
    
    # Skip properties without coordinates
    if 'lat' not in prop and 'lng' not in prop and 'latitude' not in prop and 'longitude' not in prop:
        logging.warning("Skipping property without coordinates")
        return False
        
    # Add walk score if coordinates are available
    address = None
    lat = None
    lon = None
    
    if 'address' in prop and isinstance(prop['address'], dict) and 'oneLine' in prop['address']:
        address = prop['address']['oneLine']
    elif 'address' in prop and isinstance(prop['address'], str):
        address = prop['address']
    
    if 'lat' in prop and 'lng' in prop:
        lat = prop['lat']
        lon = prop['lng']
    elif 'latitude' in prop and 'longitude' in prop:
        lat = prop['latitude']
        lon = prop['longitude']
    elif 'location' in prop and 'latitude' in prop['location'] and 'longitude' in prop['location']:
        lat = prop['location']['latitude']
        lon = prop['location']['longitude']
        
    if address and lat and lon:
        walk_score_data = fetch_walkscore(address, lat, lon)
        if walk_score_data:
            prop['walk_score'] = walk_score_data
            
    # Post to backend
    return post_property(prop)

# Track progress to ensure we eventually pull all properties
import os.path
import json

PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_progress.json")

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            logging.error("Error loading progress file, creating new one")
            return {}
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

# Main execution - run continuously
def main():
    logging.info("Starting continuous property lookup script with AI property evaluation")
    
    # Expanded city list for more comprehensive coverage
    cities = [
        "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX", "Phoenix, AZ",
        "Philadelphia, PA", "San Antonio, TX", "San Diego, CA", "Dallas, TX", "San Jose, CA",
        "Austin, TX", "Jacksonville, FL", "Fort Worth, TX", "Columbus, OH", "Charlotte, NC",
        "San Francisco, CA", "Indianapolis, IN", "Seattle, WA", "Denver, CO", "Boston, MA"
    ]
    
    # Load previous progress
    progress = load_progress()
    if not progress:
        # Initialize progress tracking for each city and API
        progress = {city: {"attom_page": 1, "rentcast_offset": 0, "redfin_page": 1, "datafiniti_page": 1, "last_api": ""} for city in cities}
    
    # Make sure all cities in our list are in the progress
    for city in cities:
        if city not in progress:
            progress[city] = {"attom_page": 1, "rentcast_offset": 0, "redfin_page": 1, "datafiniti_page": 1, "last_api": ""}
            
        # Make sure datafiniti_page is present for all existing cities (in case of upgrade)
        if "datafiniti_page" not in progress[city]:
            progress[city]["datafiniti_page"] = 1
    
    # Track which cities and APIs we've completed to cycle through them
    city_index = 0
    
    # Run indefinitely
    while True:
        try:
            # Get the current city to process
            city = cities[city_index]
            logging.info(f"Processing city: {city}")
            
            # Get the progress for this city
            city_progress = progress[city]
            
            # Determine which API to start with based on the last one used
            last_api = city_progress.get("last_api", "")
            apis_to_process = ["attom", "rentcast", "redfin", "datafiniti"]
            
            # If we have a last API, start with the next one in the rotation
            if last_api in apis_to_process:
                last_index = apis_to_process.index(last_api)
                apis_to_process = apis_to_process[last_index+1:] + apis_to_process[:last_index+1]
            
            for api in apis_to_process:
                logging.info(f"Working with API: {api} for city: {city}")
                
                if api == "attom":
                    # Process ATTOM data
                    attom_page = city_progress.get("attom_page", 1)
                    max_pages_per_run = 3  # Limit pages per run to avoid getting stuck on one API
                    pages_processed = 0
                    
                    while pages_processed < max_pages_per_run:
                        attom_data = fetch_attom(city, attom_page)
                        
                        # If no more properties or API error, break and move to next API
                        if not attom_data or 'property' not in attom_data or not attom_data['property']:
                            logging.info(f"No more ATTOM data for {city} at page {attom_page}")
                            # Reset page count if we've reached the end, so we can start fresh next cycle
                            if attom_page > 1:
                                city_progress["attom_page"] = 1
                            break
                        
                        properties = attom_data['property']
                        logging.info(f"Processing {len(properties)} ATTOM properties from page {attom_page}")
                        
                        # Process each property
                        for prop in properties:
                            try:
                                success = process_property(prop)
                                # Sleep to avoid rate limiting
                                logging.info("Sleeping for 1 second to avoid rate limiting")
                                time.sleep(1)
                            except Exception as e:
                                logging.error(f"Error processing ATTOM property: {str(e)}")
                                time.sleep(1)
                                continue
                        
                        # Move to next page
                        attom_page += 1
                        city_progress["attom_page"] = attom_page
                        pages_processed += 1
                        save_progress(progress)
                    
                    city_progress["last_api"] = "attom"
                    save_progress(progress)
                
                elif api == "rentcast":
                    # Process Rentcast data
                    rentcast_offset = city_progress.get("rentcast_offset", 0)
                    max_pages_per_run = 3  # Limit pages per run
                    pages_processed = 0
                    
                    while pages_processed < max_pages_per_run:
                        rentcast_data = fetch_rentcast(city, rentcast_offset)
                        
                        # If no more properties or API error, break and move to next API
                        if not rentcast_data or 'properties' not in rentcast_data or not rentcast_data['properties']:
                            logging.info(f"No more Rentcast data for {city} at offset {rentcast_offset}")
                            # Reset offset if we've reached the end
                            if rentcast_offset > 0:
                                city_progress["rentcast_offset"] = 0
                            break
                        
                        properties = rentcast_data['properties']
                        logging.info(f"Processing {len(properties)} Rentcast properties from offset {rentcast_offset}")
                        
                        # Process each property
                        for prop in properties:
                            try:
                                success = process_property(prop)
                                # Sleep to avoid rate limiting
                                logging.info("Sleeping for 1 second to avoid rate limiting")
                                time.sleep(1)
                            except Exception as e:
                                logging.error(f"Error processing Rentcast property: {str(e)}")
                                time.sleep(1)
                                continue
                        
                        # Move to next page
                        rentcast_offset += 50
                        city_progress["rentcast_offset"] = rentcast_offset
                        pages_processed += 1
                        save_progress(progress)
                    
                    city_progress["last_api"] = "rentcast"
                    save_progress(progress)
                
                elif api == "redfin":
                    # Process Redfin data
                    redfin_page = city_progress.get("redfin_page", 1)
                    max_pages_per_run = 3  # Limit pages per run
                    pages_processed = 0
                    
                    while pages_processed < max_pages_per_run:
                        redfin_data = fetch_redfin(city, city, redfin_page)
                        
                        # If no more properties or API error, break and move to next city
                        if not redfin_data or 'results' not in redfin_data or not redfin_data['results']:
                            logging.info(f"No more Redfin data for {city} at page {redfin_page}")
                            # Reset page count if we've reached the end
                            if redfin_page > 1:
                                city_progress["redfin_page"] = 1
                            break
                        
                        properties = redfin_data['results']
                        logging.info(f"Processing {len(properties)} Redfin properties from page {redfin_page}")
                        
                        # Process each property
                        for prop in properties:
                            try:
                                success = process_property(prop)
                                # Sleep to avoid rate limiting
                                logging.info("Sleeping for 1 second to avoid rate limiting")
                                time.sleep(1)
                            except Exception as e:
                                logging.error(f"Error processing Redfin property: {str(e)}")
                                time.sleep(1)
                                continue
                        
                        # Move to next page
                        redfin_page += 1
                        city_progress["redfin_page"] = redfin_page
                        pages_processed += 1
                        save_progress(progress)
                    
                    city_progress["last_api"] = "redfin"
                    save_progress(progress)
                
                elif api == "datafiniti":
                    # Process Datafiniti data
                    datafiniti_page = city_progress.get("datafiniti_page", 1)
                    max_pages_per_run = 3  # Limit pages per run
                    pages_processed = 0
                    
                    while pages_processed < max_pages_per_run:
                        datafiniti_data = fetch_datafiniti(city, datafiniti_page)
                        
                        # If no more properties or API error, break and move to next city
                        if not datafiniti_data or 'records' not in datafiniti_data or not datafiniti_data['records']:
                            logging.info(f"No more Datafiniti data for {city} at page {datafiniti_page}")
                            # Reset page count if we've reached the end
                            if datafiniti_page > 1:
                                city_progress["datafiniti_page"] = 1
                            break
                        
                        properties = datafiniti_data['records']
                        logging.info(f"Processing {len(properties)} Datafiniti properties from page {datafiniti_page}")
                        
                        # Process each property
                        for prop in properties:
                            try:
                                # Transform the Datafiniti property data to match our expected format
                                transformed_prop = {
                                    'address': {
                                        'oneLine': f"{prop.get('address', 'Unknown')}, {prop.get('city', '')}, {prop.get('province', '')} {prop.get('postalCode', '')}"
                                    },
                                    'city': prop.get('city', ''),
                                    'state': prop.get('province', ''),
                                    'zipCode': prop.get('postalCode', ''),
                                    'lat': prop.get('latitude', 0),
                                    'lng': prop.get('longitude', 0),
                                    'yearBuilt': prop.get('yearBuilt', 0),
                                    'buildingSize': {
                                        'size': prop.get('squareFootage', 0)
                                    },
                                    'rooms': {
                                        'beds': 0,  # Default values since these might not be available
                                        'baths': 0
                                    },
                                    'source': 'datafiniti',
                                    'id': prop.get('id', '')
                                }
                                
                                # Extract additional data from features if available
                                if 'features' in prop:
                                    for feature in prop.get('features', []):
                                        if feature.get('key') == 'Total Apartments':
                                            transformed_prop['numUnits'] = int(feature.get('value', [0])[0])
                                        elif feature.get('key') == 'Year Built:':
                                            transformed_prop['yearBuilt'] = int(feature.get('value', [0])[0])
                                
                                success = process_property(transformed_prop)
                                # Sleep to avoid rate limiting
                                logging.info("Sleeping for 1 second to avoid rate limiting")
                                time.sleep(1)
                            except Exception as e:
                                logging.error(f"Error processing Datafiniti property: {str(e)}")
                                time.sleep(1)
                                continue
                        
                        # Move to next page
                        datafiniti_page += 1
                        city_progress["datafiniti_page"] = datafiniti_page
                        pages_processed += 1
                        save_progress(progress)
                    
                    city_progress["last_api"] = "datafiniti"
                    save_progress(progress)
            
            # Move to the next city, wrap around if we've processed all cities
            city_index = (city_index + 1) % len(cities)
            
            # Small pause between cities
            logging.info(f"Completed processing for {city}, moving to next city")
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            time.sleep(10)  # Wait a bit longer on errors
            save_progress(progress)  # Save progress on error to avoid losing it
            continue  # Continue with the next iteration

if __name__ == "__main__":
    main()