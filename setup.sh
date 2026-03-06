#!/bin/bash

# Development setup script
set -e

echo "🚀 AI Agents SaaS Platform - Development Setup"
echo "================================================"

# Check Python version
echo "✓ Checking Python version..."
python --version

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "✓ Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies
echo "✓ Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "✓ Initializing database..."
python init_db.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and update configuration"
echo "2. Run: uvicorn app.main:app --reload"
echo "3. Visit: http://localhost:8000"
echo ""
