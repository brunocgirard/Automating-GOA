============================================
  GOA Server - Quick Start Guide (macOS)
============================================

FRESH MAC? (nothing installed):
  1. Extract this folder to any location (e.g., ~/GOA_Server)
  2. Open Terminal (Cmd+Space, type "Terminal", press Enter)
  3. Type: cd ~/GOA_Server  (or wherever you extracted it)
  4. Type: chmod +x *.sh
  5. Type: ./prereqs.sh
  6. This installs Homebrew, Python, Node.js, and pango automatically
  7. Then continue with SETUP below

ALREADY HAVE Python 3.11+ and Node.js 20+?
  Skip prereqs.sh, go straight to SETUP.

SETUP (one-time):
  1. Open Terminal, cd into the folder
  2. Run: chmod +x *.sh *.command  (if not already done)
  3. Run: ./setup.sh
  4. When your editor opens .env, fill in your Gemini API key and admin password
  5. Save and close, press ENTER in Terminal to continue
  6. Wait for setup to complete (~5 minutes)

DAILY USE:
  - Easiest: double-click "Start GOA Server.command" in Finder
  - Or in Terminal run: ./start.sh
  - Browser opens automatically
  - Login with admin / your chosen password
  - To stop: press Ctrl+C in Terminal, run ./stop.sh, or double-click "Stop GOA Server.command"

NETWORK ACCESS:
  - Other devices on your network can access http://<your-ip>:3000
  - Your IP is shown when start.sh runs
  - Add their origin to CORS_ORIGINS in .env if needed

TROUBLESHOOTING:
  - "Python not found"  --> brew install python3 or reinstall from python.org
  - "Node not found"    --> brew install node or reinstall from nodejs.org
  - Blank page          --> wait 10 seconds, refresh browser
  - Login fails         --> check AUTH_BOOTSTRAP_ADMIN_PASSWORD in .env
  - WeasyPrint errors   --> brew install pango (required C dependency)
