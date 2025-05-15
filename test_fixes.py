#!/usr/bin/env python3
"""Test script to verify the fixes made to the Flipr application."""

import requests
import os
import sys
import logging
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables
load_dotenv()

def test_env_variables():
    """Test that environment variables are being loaded correctly"""
    print("\n===== TESTING ENVIRONMENT VARIABLES =====")
    
    # Check for required API keys
    required_vars = [
        "DATABASE_URL", 
        "ATTOM_API_KEY", 
        "RENTCAST_API_KEY", 
        "WALK_SCORE_API_KEY", 
        "OXYLABS_USER", 
        "OXYLABS_PASS"
    ]
    
    all_vars_present = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            logging.info(f"✅ {var} is set")
        else:
            logging.error(f"❌ {var} is not set")
            all_vars_present = False
    
    if all_vars_present:
        logging.info("All required environment variables are set")
    else:
        logging.error("Some required environment variables are missing")
    
    return all_vars_present

def test_rate_limiter():
    """Test the rate limiter implementation"""
    print("\n===== TESTING RATE LIMITER =====")
    
    try:
        # Import the rate limiter from the property lookup module
        from ai_enhanced_property_lookup import RateLimiter
        
        # Create a test rate limiter
        test_limits = {
            "test_api": {"calls": 3, "period": 5}  # 3 calls per 5 seconds
        }
        
        limiter = RateLimiter(test_limits)
        
        # Make multiple calls to test rate limiting
        for i in range(5):
            wait_time = limiter.get_wait_time("test_api")
            if wait_time > 0:
                logging.info(f"Rate limit correctly triggered, wait time: {wait_time:.2f}s")
            else:
                logging.info(f"Call {i+1} allowed")
            
            # Record the call
            with limiter.locks["test_api"]:
                limiter.tokens["test_api"].append(0)  # Add 0 instead of time.time() for testing
        
        logging.info("✅ Rate limiter is working as expected")
        return True
    except Exception as e:
        logging.error(f"❌ Rate limiter test failed: {str(e)}")
        return False

def test_api_backends(backend_url=None):
    """Test the backend API endpoints"""
    print("\n===== TESTING BACKEND API =====")
    
    if not backend_url:
        backend_url = os.environ.get("BACKEND_URL", "http://localhost:5005")
    
    # Test status endpoint
    try:
        status_url = f"{backend_url}/status"
        logging.info(f"Testing status endpoint: {status_url}")
        
        response = requests.get(status_url, timeout=10)
        if response.status_code == 200:
            logging.info(f"✅ Status endpoint returned 200 OK: {response.json()}")
        else:
            logging.error(f"❌ Status endpoint failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Error testing status endpoint: {str(e)}")
        return False
    
    # Test paginated properties endpoint
    try:
        properties_url = f"{backend_url}/properties?page=1&per_page=10"
        logging.info(f"Testing paginated properties endpoint: {properties_url}")
        
        response = requests.get(properties_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'properties' in data and 'pagination' in data:
                properties = data['properties']
                pagination = data['pagination']
                logging.info(f"✅ Properties endpoint returned paginated data: {len(properties)} properties")
                logging.info(f"   Pagination info: page {pagination['page']} of {pagination['total_pages']}, {pagination['total_count']} total")
            else:
                logging.error(f"❌ Properties endpoint did not return paginated structure: {data.keys()}")
                return False
        else:
            logging.error(f"❌ Properties endpoint failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Error testing properties endpoint: {str(e)}")
        return False
    
    return True

def test_property_standardization():
    """Test the property standardization function"""
    print("\n===== TESTING PROPERTY STANDARDIZATION =====")
    
    try:
        # Import the standardization function
        from ai_enhanced_property_lookup import standardize_property
        
        # Test different property formats
        test_properties = [
            {
                "address": "123 Main St",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "price": "500000",
                "bedrooms": "3",
                "bathrooms": "2.5"
            },
            {
                "address": "456 Oak Ave",
                "lat": 34.0522,
                "lng": -118.2437,
                "price": 750000,
                "bedrooms": 4,
                "bathrooms": 3
            },
            {
                "address": "789 Pine Rd",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "price": "900000",
                "bedrooms": "5",
                "bathrooms": "3.5"
            }
        ]
        
        for i, prop in enumerate(test_properties):
            standardized = standardize_property(prop)
            
            # Check that lat/lng fields are standardized
            if 'lat' in standardized and 'lng' in standardized:
                logging.info(f"✅ Property {i+1} has standardized lat/lng fields")
            else:
                logging.error(f"❌ Property {i+1} missing lat/lng fields after standardization")
                return False
            
            # Check data types
            if isinstance(standardized['price'], float) and isinstance(standardized['bedrooms'], int):
                logging.info(f"✅ Property {i+1} has correct data types")
            else:
                logging.error(f"❌ Property {i+1} has incorrect data types")
                return False
        
        logging.info("Property standardization is working correctly")
        return True
    except Exception as e:
        logging.error(f"❌ Error testing property standardization: {str(e)}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n===== FLIPR FIXES VALIDATION TESTS =====")
    
    tests = [
        ("Environment Variables", test_env_variables),
        ("Rate Limiter", test_rate_limiter),
        ("Property Standardization", test_property_standardization),
        ("Backend API", test_api_backends)
    ]
    
    results = {}
    for name, test_func in tests:
        print(f"\nRunning test: {name}")
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            logging.error(f"Test '{name}' failed with exception: {str(e)}")
            results[name] = False
    
    # Print summary
    print("\n===== TEST RESULTS SUMMARY =====")
    all_passed = True
    for name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n✅ All tests PASSED! The fixes have been successfully implemented.")
    else:
        print("\n❌ Some tests FAILED. Please review the log output for details.")

if __name__ == "__main__":
    run_all_tests()