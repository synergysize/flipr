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
        "postgresql://user:pass@:5432/dbname",                     # Empty hostname
        "postgres:///dbname",                                      # No auth info or hostname
        "postgres://:@/dbname",                                    # Empty username and password
        "DATABASE_URL=postgres://user:pass@hostname:5432/dbname",  # Common mistake including var name
        # URL with a newline in the middle (common copy-paste error)
        """postgresql://user:pass
@hostname:5432/dbname""",
        # URL with special characters in password
        "postgresql://user:p@$$w0rd!@hostname:5432/dbname",
        # Complex real-world example with special chars
        "postgresql://postgres:zP8@m$Kd2L#qF*v7XrT9nH^Ew3Js!6B@db.example.supabase.co:5432/postgres",
        # Complex example with newline (what we saw in the error)
        """DATABASE_URL=postgresql://postgres:zP8@m$Kd2L#qF*v7XrT9nH^Ew3Js!6B
@db.utalravvcgiehxojrgba.supabase.co:5432/postgres"""
    ]
    
    for i, url in enumerate(urls):
        print(f"Test {i+1}: {url}")
        
        # Check for common mistakes and fix them
        original_url = url
        
        # Remove variable name prefix if included
        if url.startswith("DATABASE_URL="):
            url = url.split("=", 1)[1]
        
        # Fix newlines in the URL (common copy-paste issue)
        url = url.replace("\n", "").replace("\r", "")
        
        # Report corrections if any were made
        if url != original_url:
            print(f"  Corrected URL: {url}")
            
        result = urllib.parse.urlparse(url)
        
        # Extract components with validation
        username = result.username or "postgres"  # Default username
        password = result.password  # Password can be None
        database = result.path[1:] if result.path else ""  # Remove the leading '/'
        hostname = result.hostname or "localhost"  # Default to localhost if None
        port = result.port or 5432   # Default to 5432 if None
        
        # Validation of minimum requirements
        valid = True
        errors = []
        
        if not (result.scheme in ['postgresql', 'postgres']):
            valid = False
            errors.append(f"Invalid scheme: {result.scheme}")
            
        if not database:
            valid = False
            errors.append("Missing database name")
            
        if not username:
            errors.append("Username is empty (using default: postgres)")
            
        if not hostname:
            errors.append("Hostname is empty (using default: localhost)")
        
        # Print parsed components
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print(f"  Database: {database}")
        print(f"  Hostname: {hostname}")
        print(f"  Port: {port}")
        print(f"  Valid: {valid}")
        
        if errors:
            print("  Validation errors:")
            for error in errors:
                print(f"   - {error}")
        
        # Create connection string
        if valid:
            conn_string = f"host={hostname} port={port} dbname={database} user={username}"
            if password:
                conn_string += f" password={password}"
            conn_string += " sslmode=require"
            
            print(f"  Connection string: {conn_string}")
        else:
            print("  Connection string: Not created due to validation errors")
            
        print("")

def test_env_url():
    """Test the current DATABASE_URL from environment"""
    
    print("\n===== TESTING ENVIRONMENT URL =====\n")
    
    DB_URL = os.environ.get("DATABASE_URL", "")
    if not DB_URL:
        print("DATABASE_URL is not set in environment or .env file")
        return
    
    # Apply the same fixes as in the main application
    original_url = DB_URL
    
    # Remove variable name prefix if included
    if DB_URL.startswith("DATABASE_URL="):
        DB_URL = DB_URL.split("=", 1)[1]
    
    # Fix newlines in the URL (common copy-paste issue)
    DB_URL = DB_URL.replace("\n", "").replace("\r", "")
    
    # Report corrections if any were made
    if DB_URL != original_url:
        print(f"Original DATABASE_URL: {original_url}")
        print(f"Corrected DATABASE_URL: {DB_URL}")
    else:
        print(f"DATABASE_URL from environment: {DB_URL}")
    
    result = urllib.parse.urlparse(DB_URL)
    
    # Extract components
    username = result.username or "postgres"  # Default username
    password = result.password  # Password can be None
    database = result.path[1:] if result.path else ""  # Remove the leading '/'
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