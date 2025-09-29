#!/usr/bin/env python3

"""Setup script for Exvora Travel MCP Server"""

import subprocess
import sys
import os

def run_command(command):
    """Run a command and return True if successful"""
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 Setting up Exvora Travel MCP Server...")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    
    # Install required packages
    packages = [
        "mcp>=1.0.0",
        "aiohttp>=3.8.0", 
        "pydantic>=2.5.0",
        "pandas>=2.0.0",
        "geopy>=2.3.0"
    ]
    
    print("📦 Installing dependencies...")
    for package in packages:
        print(f"  Installing {package}...")
        if not run_command(f"{sys.executable} -m pip install '{package}'"):
            print(f"❌ Failed to install {package}")
            return False
    
    # Test imports
    print("🧪 Testing imports...")
    test_imports = [
        "import mcp",
        "import aiohttp", 
        "import pydantic",
        "from exvora_mcp_server.main import ExvoraTravelMCPServer"
    ]
    
    for test_import in test_imports:
        try:
            exec(test_import)
            print(f"  ✅ {test_import}")
        except Exception as e:
            print(f"  ❌ {test_import}: {e}")
            return False
    
    # Create environment template
    env_file = "../.env.example"
    if not os.path.exists(env_file):
        print("📝 Creating environment template...")
        with open(env_file, "w") as f:
            f.write("""# Exvora MCP Server Environment Variables

# Google Places API (FREE - get from: console.cloud.google.com)
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here

# TripAdvisor API (PAID - get from: business.tripadvisor.com)  
TRIPADVISOR_API_KEY=your_tripadvisor_api_key_here

# Optional: Other API keys
OPENWEATHER_API_KEY=your_openweather_key_here
FOURSQUARE_API_KEY=your_foursquare_key_here
YELP_API_KEY=your_yelp_key_here
""")
    
    print("✅ Setup complete!")
    print()
    print("🔑 Next steps:")
    print("1. Get a FREE Google Places API key:")
    print("   → Go to: https://console.cloud.google.com")
    print("   → Enable Places API")  
    print("   → Create credentials")
    print()
    print("2. Set your API key:")
    print("   export GOOGLE_PLACES_API_KEY='your_key_here'")
    print()
    print("3. Test the server:")
    print("   python3 -m exvora_mcp_server.main")
    print()
    print("4. Add to Claude Desktop config:")
    print('   "exvora-travel": {')
    print('     "command": "python3",')
    print('     "args": ["-m", "exvora_mcp_server.main"],')
    print(f'     "cwd": "{os.path.abspath(".")}"')
    print('   }')
    
    return True

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)