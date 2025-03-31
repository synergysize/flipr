import urllib.parse
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load .env file
load_dotenv()

def test_url_parsing():
    """Test the URL parsing logic with different URL formats"""
    
    print("\n===== TESTING URL PARSING =====\n")
    
    # Test various URL formats
    urls = [
        "postgres://user:pass@hostname/dbname",                    # No port
        "postgres://user:pass@hostname:5432/dbname",               # With port
        "postgres://user:pass@hostname:5432/dbname?sslmode=require", # With params
        "postgresql://user:pass@hostname/dbname",                  # postgresql scheme
        "postgresql://user@hostname/dbname",                       # No password
        "postgresql://user:pass@/dbname",                          # No hostname (localhost)
    ]
    
    for i, url in enumerate(urls):
        print(f"Test {i+1}: {url}")
        result = urllib.parse.urlparse(url)
        
        # Extract components
        username = result.username
        password = result.password
        database = result.path[1:]  # Remove the leading '/'
        hostname = result.hostname or "localhost"  # Default to localhost if None
        port = result.port or 5432   # Default to 5432 if None
        
        # Print parsed components
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print(f"  Database: {database}")
        print(f"  Hostname: {hostname}")
        print(f"  Port: {port}")
        
        # Create connection string
        conn_string = f"host={hostname} port={port} dbname={database} user={username}"
        if password:
            conn_string += f" password={password}"
        conn_string += " sslmode=require"
        
        print(f"  Connection string: {conn_string}")
        print("")

def test_env_url():
    """Test the current DATABASE_URL from environment"""
    
    print("\n===== TESTING ENVIRONMENT URL =====\n")
    
    DB_URL = os.environ.get("DATABASE_URL", "")
    if not DB_URL:
        print("DATABASE_URL is not set in environment or .env file")
        return
    
    print(f"DATABASE_URL from environment: {DB_URL}")
    
    result = urllib.parse.urlparse(DB_URL)
    
    # Extract components
    username = result.username
    password = result.password
    database = result.path[1:]  # Remove the leading '/'
    hostname = result.hostname or "localhost"  # Default to localhost if None
    port = result.port or 5432   # Default to 5432 if None
    
    # Print parsed components
    print(f"  Username: {username}")
    print(f"  Password: {'*****' if password else None}")
    print(f"  Database: {database}")
    print(f"  Hostname: {hostname}")
    print(f"  Port: {port}")
    
    # Create connection string
    conn_string = f"host={hostname} port={port} dbname={database} user={username}"
    if password:
        conn_string += f" password=****"  # Don't print actual password
    conn_string += " sslmode=require"
    
    print(f"  Connection string: {conn_string}")

if __name__ == "__main__":
    # Test URL parsing logic
    test_url_parsing()
    
    # Test actual environment URL
    test_env_url()