# Flipr - Real Estate Analysis App (Fixed Version)

Flipr is a real estate analysis app that pulls data from various APIs, evaluates properties using AI, and displays a color-coded score on a map. This repository contains the fixed version with critical issues resolved.

## Project Overview

- **Frontend**: Vercel-hosted web application with property map and filtering
- **Backend**: Flask API hosted on Render
- **Database**: Supabase PostgreSQL

## Fixed Issues

### 1. Security: Removed Hardcoded API Keys
- All API keys and credentials now use environment variables
- Added proper documentation for environment configuration
- Created .env file support for local development

### 2. Reliability: Added API Rate Limiting
- Implemented token bucket algorithm for rate limiting
- Added exponential backoff for API retries
- Improved error handling for all external API calls

### 3. Data Consistency: Standardized Data Structure
- Normalized property object structure between frontend and backend
- Standardized lat/lng field names
- Added proper data type conversion and validation
- Updated frontend to match backend response format

### 4. Performance: Added Property Deduplication
- Implemented fingerprinting for properties to detect duplicates
- Added cache cleanup to prevent memory issues
- Optimized property processing with standardization

### 5. Infrastructure: Added Pagination & Removed SQLite Fallback
- Added pagination for the properties API endpoint
- Updated frontend to support paginated responses
- Disabled SQLite fallback in production environments
- Added production mode detection with environment variables

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
DATABASE_URL=postgresql://user:password@hostname:port/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key

# API Keys
ATTOM_API_KEY=your-attom-api-key
RENTCAST_API_KEY=your-rentcast-api-key
WALK_SCORE_API_KEY=your-walkscore-api-key
OXYLABS_USER=your-oxylabs-username
OXYLABS_PASS=your-oxylabs-password

# Backend URL Configuration
BACKEND_URL=https://your-backend-url.onrender.com
PORT=5005

# Production Settings
PRODUCTION=true
DISABLE_SQLITE_FALLBACK=true
```

## Running the Application

### Backend

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application in development mode:
   ```bash
   python fixed_backend.py
   ```

3. Run in production mode:
   ```bash
   gunicorn --worker-class eventlet -w 1 fixed_backend:app
   ```

### Property Data Collection

Run the property lookup script to fetch and evaluate real estate data:

```bash
python ai_enhanced_property_lookup.py
```

## Monitoring

The application logs information to:
- `fixed_backend.log` - Backend server logs
- `property_lookup.log` - Property fetch and evaluation logs

## Architecture

1. Scripts pull real estate data from APIs (ATTOM, Rentcast, WalkScore, etc.)
2. AI evaluates each property and assigns a score
3. Scores are stored in PostgreSQL database
4. Color-coded property markers appear on the dApp map