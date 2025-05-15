import requests
import json
import time
from datetime import datetime
import logging
import sys
import os
from ai_property_evaluator import AIPropertyEvaluator
import collections
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("property_lookup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables if not already loaded
from dotenv import load_dotenv
load_dotenv()

# API Keys from environment variables
ATTOM_API_KEY = os.environ.get("ATTOM_API_KEY", "")
RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "")
WALK_SCORE_API_KEY = os.environ.get("WALK_SCORE_API_KEY", "")
OXYLABS_USER = os.environ.get("OXYLABS_USER", "")
OXYLABS_PASS = os.environ.get("OXYLABS_PASS", "")

# AI API keys from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ATTOM_ENDPOINT = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address"
RENTCAST_ENDPOINT = "https://api.rentcast.io/v1/properties"
WALK_SCORE_ENDPOINT = "http://api.walkscore.com/score"
OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"

# Backend configuration
# Check for environment variable, use proper Render URL in production
BACKEND_URL = os.environ.get("BACKEND_URL", "https://flipr-backend.onrender.com")
FLASK_BACKEND_ENDPOINT = f"{BACKEND_URL}/update"

# For local development, uncomment the line below
# BACKEND_URL = "http://localhost:5001"
CURRENT_YEAR = datetime.now().year

# Rate limiting configuration for each API
RATE_LIMITS = {
    "attom": {"calls": 5, "period": 60},         # 5 calls per minute
    "rentcast": {"calls": 10, "period": 60},     # 10 calls per minute
    "walkscore": {"calls": 15, "period": 60},    # 15 calls per minute
    "oxylabs": {"calls": 3, "period": 60}        # 3 calls per minute
}

# Property cache to avoid duplicate processing
property_cache = {}
property_cache_lock = threading.Lock()

class RateLimiter:
    """Rate limiter using token bucket algorithm"""
    def __init__(self, rate_limits):
        self.rate_limits = rate_limits
        self.tokens = {api: collections.deque(maxlen=limit["calls"]) for api, limit in rate_limits.items()}
        self.locks = {api: threading.Lock() for api in rate_limits}
    
    def get_wait_time(self, api):
        """Calculate wait time needed before next API call"""
        if api not in self.rate_limits:
            return 0
        
        limit = self.rate_limits[api]
        with self.locks[api]:
            if len(self.tokens[api]) < limit["calls"]:
                return 0
            
            oldest_call = self.tokens[api][0]
            time_passed = time.time() - oldest_call
            if time_passed >= limit["period"]:
                return 0
            
            return limit["period"] - time_passed + 0.1  # Add a small buffer
    
    def make_request(self, api, func, *args, **kwargs):
        """Make a rate-limited API request with exponential backoff for errors"""
        wait_time = self.get_wait_time(api)
        
        if wait_time > 0:
            logging.info(f"Rate limit reached for {api}, waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
        
        # Record this call
        with self.locks[api]:
            self.tokens[api].append(time.time())
        
        # Make the actual request with exponential backoff for errors
        max_retries = 3
        for retry in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if retry < max_retries:
                    wait_time = (2 ** retry) + (retry * 0.1)
                    logging.warning(f"{api} API call failed, retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    logging.error(f"{api} API call failed after {max_retries} retries: {str(e)}")
                    raise

# Initialize the rate limiter
rate_limiter = RateLimiter(RATE_LIMITS)

# Initialize headers with API keys
headers_attom = {"apikey": ATTOM_API_KEY, "Accept": "application/json"}
headers_rentcast = {"X-Api-Key": RENTCAST_API_KEY}

# Initialize the AI property evaluator with API key
ai_evaluator = AIPropertyEvaluator(api_key=OPENAI_API_KEY or ANTHROPIC_API_KEY)

# Property deduplication function
def get_property_fingerprint(prop):
    """Generate a unique identifier for a property to detect duplicates"""
    # Extract key identifying fields
    address = ""
    if 'address' in prop:
        if isinstance(prop['address'], str):
            address = prop['address']
        elif isinstance(prop['address'], dict) and 'oneLine' in prop['address']:
            address = prop['address']['oneLine']
    
    # Get coordinates
    lat = prop.get('lat') or prop.get('latitude') or (
        prop.get('location', {}).get('latitude') if isinstance(prop.get('location'), dict) else None
    )
    
    lng = prop.get('lng') or prop.get('longitude') or (
        prop.get('location', {}).get('longitude') if isinstance(prop.get('location'), dict) else None
    )
    
    # Create a unique fingerprint
    fingerprint = f"{address}_{lat}_{lng}"
    return fingerprint

def fetch_attom(city, page):
    def _fetch():
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
            # Raise exception to trigger retry logic
            raise Exception(f"ATTOM API error: Status code {response.status_code}, Response: {response.text}")
    
    try:
        # Use rate limiter for the API call
        return rate_limiter.make_request("attom", _fetch)
    except Exception as e:
        logging.error(f"Error fetching ATTOM data after retries: {str(e)}")
        return None

def fetch_rentcast(city, offset):
    def _fetch():
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
            # Raise exception to trigger retry logic
            raise Exception(f"Rentcast API error: Status code {response.status_code}, Response: {response.text}")
    
    try:
        # Use rate limiter for the API call
        return rate_limiter.make_request("rentcast", _fetch)
    except Exception as e:
        logging.error(f"Error fetching Rentcast data after retries: {str(e)}")
        return None

def fetch_walkscore(address, lat, lon):
    def _fetch():
        logging.info(f"Fetching WalkScore for {address}")
        params = {"format": "json", "address": address, "lat": lat, "lon": lon, "wsapikey": WALK_SCORE_API_KEY}
        response = requests.get(WALK_SCORE_ENDPOINT, params=params, timeout=30)
        
        if response.status_code == 200:
            logging.info(f"Successfully fetched WalkScore for {address}")
            return response.json()
        else:
            # Raise exception to trigger retry logic
            raise Exception(f"WalkScore API error: Status code {response.status_code}, Response: {response.text}")
    
    try:
        # Use rate limiter for the API call
        return rate_limiter.make_request("walkscore", _fetch)
    except Exception as e:
        logging.error(f"Error fetching WalkScore data after retries: {str(e)}")
        return None

def fetch_redfin(query, location, page):
    def _fetch():
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
            # Raise exception to trigger retry logic
            raise Exception(f"Redfin API error: Status code {response.status_code}, Response: {response.text}")
    
    try:
        # Use rate limiter for the API call
        return rate_limiter.make_request("oxylabs", _fetch)
    except Exception as e:
        logging.error(f"Error fetching Redfin data after retries: {str(e)}")
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
    # Standardize the property data
    prop = standardize_property(prop)
    
    # Add coordinates if needed
    prop = add_coordinates_to_property(prop)
    
    # Skip properties without coordinates
    if 'lat' not in prop and 'lng' not in prop and 'latitude' not in prop and 'longitude' not in prop:
        logging.warning("Skipping property without coordinates")
        return False
    
    # Check if we've already processed this property to avoid duplicates
    fingerprint = get_property_fingerprint(prop)
    with property_cache_lock:
        if fingerprint in property_cache:
            logging.info(f"Skipping duplicate property: {fingerprint}")
            return False
        
        # Mark property as processed
        property_cache[fingerprint] = time.time()
        
        # Clean up old cache entries (older than 24 hours)
        current_time = time.time()
        old_entries = [fp for fp, timestamp in property_cache.items() 
                       if current_time - timestamp > 86400]  # 24 hours
        for fp in old_entries:
            del property_cache[fp]
    
    # Extract address and coordinates
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
    
    # Add walk score if coordinates are available
    if address and lat and lon:
        walk_score_data = fetch_walkscore(address, lat, lon)
        if walk_score_data:
            prop['walk_score'] = walk_score_data
    
    # Post to backend
    return post_property(prop)

def standardize_property(prop):
    """Standardize property object to ensure consistent data structure"""
    # Create a copy to avoid modifying the original
    standardized = prop.copy() if isinstance(prop, dict) else {}
    
    # Ensure consistent lat/lng fields
    if 'latitude' in standardized and 'lat' not in standardized:
        standardized['lat'] = standardized['latitude']
    if 'longitude' in standardized and 'lng' not in standardized:
        standardized['lng'] = standardized['longitude']
    
    # Extract coordinates from nested location object if present
    if ('lat' not in standardized or 'lng' not in standardized) and 'location' in standardized:
        loc = standardized.get('location', {})
        if isinstance(loc, dict):
            if 'latitude' in loc and 'lat' not in standardized:
                standardized['lat'] = loc['latitude']
            if 'longitude' in loc and 'lng' not in standardized:
                standardized['lng'] = loc['longitude']
    
    # Ensure numeric fields are properly typed
    for field in ['price', 'lat', 'lng', 'bedrooms', 'bathrooms', 'square_feet', 'year_built']:
        if field in standardized and standardized[field] is not None:
            try:
                if field in ['bedrooms']:
                    standardized[field] = int(float(standardized[field]))
                elif field in ['price', 'lat', 'lng', 'bathrooms', 'square_feet']:
                    standardized[field] = float(standardized[field])
                elif field == 'year_built':
                    standardized[field] = int(float(standardized[field]))
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails
    
    # Add timestamp if missing
    if 'timestamp' not in standardized:
        standardized['timestamp'] = int(time.time())
    
    return standardized

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
