#!/bin/bash
# Quick Start Script for AI Interviewer
# Run this to set everything up in one go

echo "🎤 AI Technical Interview Coach - Setup Script"
echo "=============================================="

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Get API Key
echo -e "\n${YELLOW}Step 1: Groq API Key${NC}"
echo "1. Go to https://console.groq.com/keys"
echo "2. Create a new API key and copy it"
read -p "Paste your GROQ_API_KEY here: " GROQ_KEY

if [ -z "$GROQ_KEY" ]; then
    echo -e "${YELLOW}⚠️  No API key provided. You'll need to add it to .env manually.${NC}"
fi

# Step 2: Check FFmpeg
echo -e "\n${YELLOW}Step 2: Checking FFmpeg${NC}"
if command -v ffmpeg &> /dev/null; then
    echo -e "${GREEN}✓ FFmpeg found${NC}"
else
    echo -e "${YELLOW}⚠️  FFmpeg not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install ffmpeg
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install ffmpeg
    fi
fi

# Step 3: Backend Setup
echo -e "\n${YELLOW}Step 3: Setting up Backend${NC}"
cd "$(dirname "$0")/backend" || exit

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

echo "Installing Python packages..."
pip install -r requirements.txt > /dev/null 2>&1

# Create .env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    if [ ! -z "$GROQ_KEY" ]; then
        sed -i '' "s/your_groq_api_key_here/$GROQ_KEY/" .env
        echo -e "${GREEN}✓ .env created with API key${NC}"
    else
        echo -e "${YELLOW}⚠️  .env created (update with your API key)${NC}"
    fi
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

echo -e "${GREEN}✓ Backend ready${NC}"

# Step 4: Frontend Setup
echo -e "\n${YELLOW}Step 4: Setting up Frontend${NC}"
cd ../frontend || exit

if [ ! -d "node_modules" ]; then
    echo "Installing npm packages..."
    npm install > /dev/null 2>&1
fi

echo -e "${GREEN}✓ Frontend ready${NC}"

# Summary
echo -e "\n${BLUE}=============================================="
echo "       🎉 Setup Complete! 🎉"
echo "=============================================="
echo -e "${GREEN}"
echo "To start the application:"
echo ""
echo "Terminal 1 - Backend:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  python -m uvicorn main:app --reload"
echo ""
echo "Terminal 2 - Frontend:"
echo "  cd frontend"
echo "  npm start"
echo ""
echo -e "${NC}${YELLOW}Frontend will open on: http://localhost:3000"
echo "Backend API on: http://localhost:8000"
echo -e "${NC}"
echo "Happy interviewing! 🚀"
