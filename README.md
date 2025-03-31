# Flipr - AI Property Evaluator

A real estate evaluation tool with AI-powered insights for property analysis.

## Architecture

This application uses a distributed architecture with:

- Frontend: Hosted on Vercel
- Backend: Flask server hosted on Render
- Database: PostgreSQL hosted on Supabase

## Setup Instructions

### Backend Setup (Render)

1. Create a new Web Service on Render
2. Link your GitHub repository
3. Configure the build settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python fixed_backend.py`
4. Set Environment Variables:
   - `DATABASE_URL`: Your Supabase PostgreSQL connection string
   - `PRODUCTION`: true
   - Any API keys required

### Database Setup (Supabase)

1. Create a new Supabase project
2. Create a new PostgreSQL database table named `properties`
3. Copy your connection string for the Render setup

### Frontend Setup (Vercel)

1. Connect your repository to Vercel
2. Deploy the frontend from the repository

## Local Development

1. Clone the repository
2. Copy `.env.example` to `.env` and add your environment variables
3. Install dependencies: `pip install -r requirements.txt`
4. Update BACKEND_URL in index.html and ai_enhanced_property_lookup.py to your local server URL
5. Run the server: `python fixed_backend.py`

## Files Overview

- `fixed_backend.py`: Flask backend server
- `index.html`: Frontend interface
- `ai_enhanced_property_lookup.py`: Property data lookup
- `ai_property_evaluator.py`: AI evaluation logic
- `requirements.txt`: Python dependencies

## Important Configuration

- CORS is configured to work with specific frontend domains
- Socket.io is configured for real-time updates between frontend and backend
- Database connections support both PostgreSQL (production) and SQLite (development)