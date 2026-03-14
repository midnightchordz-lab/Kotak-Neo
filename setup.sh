#!/bin/bash

# COSTAR Algo Trader - Local Setup Script
# Run this script after downloading the code

echo "========================================"
echo "COSTAR Kotak Neo F&O Algo Trader Setup"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install Python 3.9+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required. Please install Node.js 18+"
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check yarn or npm
if command -v yarn &> /dev/null; then
    PKG_MANAGER="yarn"
else
    PKG_MANAGER="npm"
fi
echo "✅ Package manager: $PKG_MANAGER"

echo ""
echo "Setting up Backend..."
echo "----------------------"

cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate and install
source venv/bin/activate
pip install -r requirements.txt -q
echo "✅ Backend dependencies installed"

# Create .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env file - PLEASE EDIT WITH YOUR CREDENTIALS"
fi

cd ..

echo ""
echo "Setting up Frontend..."
echo "----------------------"

cd frontend

# Install dependencies
$PKG_MANAGER install -q
echo "✅ Frontend dependencies installed"

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo 'EXPO_PUBLIC_BACKEND_URL=http://localhost:8001' > .env
    echo "✅ Created frontend .env"
fi

cd ..

echo ""
echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Edit backend/.env with your credentials:"
echo "   - EMERGENT_LLM_KEY (from Emergent Profile > Universal Key)"
echo "   - KOTAK_ACCESS_TOKEN (from Kotak NEO API portal)"
echo ""
echo "2. Start MongoDB (if using local):"
echo "   mongod --dbpath /path/to/data"
echo ""
echo "3. Start Backend (Terminal 1):"
echo "   cd backend && source venv/bin/activate"
echo "   uvicorn server:app --host 0.0.0.0 --port 8001 --reload"
echo ""
echo "4. Start Frontend (Terminal 2):"
echo "   cd frontend && $PKG_MANAGER start"
echo ""
echo "5. Open http://localhost:3000 in browser"
echo ""
echo "Happy Trading! 📈"
