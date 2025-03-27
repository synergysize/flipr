
import requests
import time
import os
from ai_property_evaluator import AIPropertyEvaluator

# Get API key from environment variables
API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")

BACKEND_URL = "http://127.0.0.1:5001"
evaluator = AIPropertyEvaluator(api_key=API_KEY)

def fetch_unevaluated_properties():
    properties = requests.get(f"{BACKEND_URL}/properties").json()
    unevaluated = [p for p in properties if "intensity" not in p]
    return unevaluated

def evaluate_and_update(property):
    intensity = evaluator.evaluate_property(property)
    if intensity > 0.8:
        deal_rating = "Red (Best Deal)"
    elif intensity > 0.6:
        deal_rating = "Orange (Good Deal)"
    elif intensity > 0.4:
        deal_rating = "Yellow (Average Deal)"
    elif intensity > 0.2:
        deal_rating = "Green (Below Average Deal)"
    else:
        deal_rating = "Blue (Weak Deal)"

    update_data = {
        "intensity": intensity,
        "deal_rating": deal_rating,
        "ai_evaluation_reasoning": property.get("ai_evaluation_reasoning", "")
    }
    
    response = requests.post(f"{BACKEND_URL}/property/{property['id']}/ai-evaluate", json=update_data)
    if response.status_code != 200:
        print(f"Failed to update property {property['id']}: {response.status_code} - {response.text}")

def main_loop():
    while True:
        properties = fetch_unevaluated_properties()
        if properties:
            for prop in properties:
                evaluate_and_update(prop)
                print(f"Evaluated property ID {prop['id']}")
                time.sleep(5)  # Delay to create the trickle-in effect
        else:
            print("No properties to evaluate. Waiting...")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
