import requests
import json
import time
from datetime import datetime
import logging
import sys
import os
from ai_property_evaluator import AIPropertyEvaluator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("property_lookup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# API Keys and endpoints
ATTOM_API_KEY = "415c239d52de7ba0d68a534bd87c760b"
RENTCAST_API_KEY = "95c71aebe82a4297bb2cb2af62bb2f60"
WALK_SCORE_API_KEY = "0ed2fd6542efff2531d1c690d3b52dcf"
OXYLABS_USER = "synergysize_0GcLz"
OXYLABS_PASS = "f1M6o1y2____"

# AI API keys - try to get from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ATTOM_ENDPOINT = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
RENTCAST_ENDPOINT = "https://api.rentcast.io/v1/properties"
WALK_SCORE_ENDPOINT = "http://api.walkscore.com/score"
OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"

# Use port 5001 for the live backend
# Check for environment variable, default to localhost in development
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5001")
FLASK_BACKEND_ENDPOINT = f"{BACKEND_URL}/update"
CURRENT_YEAR = datetime.now().year

headers_attom = {"apikey": ATTOM_API_KEY, "Accept": "application/json"}
headers_rentcast = {"X-Api-Key": RENTCAST_API_KEY}

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
        if intensity > 0.95:
            color_desc = "Red (Very Strong)"
        elif intensity > 0.8:
            color_desc = "Orange (Strong)"
        elif intensity > 0.65:
            color_desc = "Yellow (Neutral)"
        elif intensity > 0.4:
            color_desc = "Green (Weak)"
        else:
            color_desc = "Blue (Very Weak)"
        
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
    
    # Ensure we have identifier and vintage fields
    if 'identifier' not in prop:
        address = None
        if 'address' in prop and isinstance(prop['address'], str):
            address = prop['address']
        elif 'address' in prop and isinstance(prop['address'], dict) and 'oneLine' in prop['address']:
            address = prop['address']['oneLine']
            
        if address:
            prop['identifier'] = f"property_{address.replace(' ', '_').replace(',', '')}"
        else:
            import random
            prop['identifier'] = f"property_{random.randint(10000, 99999)}"
    
    if 'vintage' not in prop:
        if 'yearBuilt' in prop:
            prop['vintage'] = str(prop['yearBuilt'])
        else:
            prop['vintage'] = "unknown"
    
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

# Main execution - run continuously
def main():
    logging.info("Starting continuous property lookup script with AI property evaluation")
    
    # Use one city from each of the 50 states
    cities = [
        "Birmingham, AL",       # Alabama
        "Anchorage, AK",        # Alaska
        "Phoenix, AZ",          # Arizona
        "Little Rock, AR",      # Arkansas
        "Los Angeles, CA",      # California
        "Denver, CO",           # Colorado
        "Hartford, CT",         # Connecticut
        "Wilmington, DE",       # Delaware
        "Miami, FL",            # Florida
        "Atlanta, GA",          # Georgia
        "Honolulu, HI",         # Hawaii
        "Boise, ID",            # Idaho
        "Chicago, IL",          # Illinois
        "Indianapolis, IN",     # Indiana
        "Des Moines, IA",       # Iowa
        "Wichita, KS",          # Kansas
        "Louisville, KY",       # Kentucky
        "New Orleans, LA",      # Louisiana
        "Portland, ME",         # Maine
        "Baltimore, MD",        # Maryland
        "Boston, MA",           # Massachusetts
        "Detroit, MI",          # Michigan
        "Minneapolis, MN",      # Minnesota
        "Jackson, MS",          # Mississippi
        "Kansas City, MO",      # Missouri
        "Billings, MT",         # Montana
        "Omaha, NE",            # Nebraska
        "Las Vegas, NV",        # Nevada
        "Manchester, NH",       # New Hampshire
        "Newark, NJ",           # New Jersey
        "Albuquerque, NM",      # New Mexico
        "New York, NY",         # New York
        "Charlotte, NC",        # North Carolina
        "Fargo, ND",            # North Dakota
        "Columbus, OH",         # Ohio
        "Oklahoma City, OK",    # Oklahoma
        "Portland, OR",         # Oregon
        "Philadelphia, PA",     # Pennsylvania
        "Providence, RI",       # Rhode Island
        "Charleston, SC",       # South Carolina
        "Sioux Falls, SD",      # South Dakota
        "Nashville, TN",        # Tennessee
        "Houston, TX",          # Texas
        "Salt Lake City, UT",   # Utah
        "Burlington, VT",       # Vermont
        "Richmond, VA",         # Virginia
        "Seattle, WA",          # Washington
        "Charleston, WV",       # West Virginia
        "Milwaukee, WI",        # Wisconsin
        "Cheyenne, WY"          # Wyoming
    ]
    
    # Track which cities and APIs we've completed to cycle through them
    city_index = 0
    
    # Run indefinitely
    while True:
        try:
            # Get the current city to process
            city = cities[city_index]
            logging.info(f"Processing city: {city}")
            
            # Process ATTOM data
            attom_page = 1
            while True:
                attom_data = fetch_attom(city, attom_page)
                
                # If no more properties or API error, break and move to next API
                if not attom_data or 'property' not in attom_data or not attom_data['property']:
                    logging.info(f"No more ATTOM data for {city} at page {attom_page}")
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
            
            # Process Rentcast data
            rentcast_offset = 0
            while True:
                rentcast_data = fetch_rentcast(city, rentcast_offset)
                
                # If no more properties or API error, break and move to next API
                if not rentcast_data or 'properties' not in rentcast_data or not rentcast_data['properties']:
                    logging.info(f"No more Rentcast data for {city} at offset {rentcast_offset}")
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
            
            # Process Redfin data
            redfin_page = 1
            while True:
                redfin_data = fetch_redfin(city, city, redfin_page)
                
                # If no more properties or API error, break and move to next city
                if not redfin_data or 'results' not in redfin_data or not redfin_data['results']:
                    logging.info(f"No more Redfin data for {city} at page {redfin_page}")
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
            
            # Move to the next city, wrap around if we've processed all cities
            city_index = (city_index + 1) % len(cities)
            
            # Small pause between cities
            logging.info(f"Completed processing for {city}, moving to next city")
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            time.sleep(10)  # Wait a bit longer on errors
            continue  # Continue with the next iteration

if __name__ == "__main__":
    main()
