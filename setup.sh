#!/bin/bash

# =============================================================================
#  SKY AI WHATSAPP AGENT - Automated Setup Script
#  Compatible with: Termux (Android), Ubuntu, Kali Linux, Debian
# =============================================================================

clear

# ─── Colors ─────────────────────────────────────────────────────────────────
BLUE='\033[38;5;39m'
GREEN='\033[38;5;82m'
YELLOW='\033[38;5;226m'
RED='\033[38;5;196m'
CYAN='\033[38;5;51m'
PURPLE='\033[38;5;141m'
GRAY='\033[38;5;245m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Banner ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}"
echo '   ╔═══════════════════════════════════════════════════════╗'
echo '   ║    🌌  SKY AI WHATSAPP AGENT - SETUP  🌌            ║'
echo '   ║        Automated Installation Script                 ║'
echo '   ║        Powered by Gemini AI + Baileys                ║'
echo '   ╚═══════════════════════════════════════════════════════╝'
echo -e "${NC}"

# ─── Helper Functions ──────────────────────────────────────────────────────
status() { echo -e "${BLUE}[${CYAN}✦${BLUE}]${NC} $1"; }
success() { echo -e "${GREEN}[${GREEN}✓${GREEN}]${NC} $1"; }
error() { echo -e "${RED}[${RED}✗${RED}]${NC} $1"; }
section() {
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─── Detect OS ──────────────────────────────────────────────────────────────
if [[ "$OSTYPE" == "linux-android"* ]] || [[ -d "/data/data/com.termux" ]]; then
    IS_TERMUX=true
    success "Termux detected (Android)"
elif [[ -f "/etc/debian_version" ]] || [[ -f "/etc/os-release" ]]; then
    IS_TERMUX=false
    success "Debian-based Linux detected"
else
    IS_TERMUX=false
    status "Unknown OS, proceeding with generic setup..."
fi

# ─── Step 1: Update packages ────────────────────────────────────────────────
section "📦 Step 1: Updating Package Lists"

if [ "$IS_TERMUX" = true ]; then
    pkg update -y 2>/dev/null || true
    pkg upgrade -y 2>/dev/null || true
else
    sudo apt-get update -y 2>/dev/null || sudo apt update -y 2>/dev/null || true
fi
success "Package lists updated"

# ─── Step 2: Install Core Dependencies ──────────────────────────────────────
section "🔧 Step 2: Installing Core Dependencies"

if [ "$IS_TERMUX" = true ]; then
    pkg install -y nodejs python python-pip git make 2>/dev/null || {
        error "Failed to install Termux packages"
        exit 1
    }
else
    sudo apt-get install -y nodejs npm python3 python3-pip git make 2>/dev/null || {
        error "Failed to install system packages"
        exit 1
    }
fi
success "Node.js, Python, Git installed"

# ─── Step 3: Install Python Dependencies ────────────────────────────────────
section "🐍 Step 3: Installing Python Dependencies"

pip3 install -r requirements.txt 2>/dev/null || pip install -r requirements.txt 2>/dev/null
success "Python packages installed (requests)"

# ─── Step 4: Install Node.js Dependencies ───────────────────────────────────
section "📀 Step 4: Installing WhatsApp Handler (Baileys)"

if [ -d "wa_handler" ]; then
    cd wa_handler
    status "Installing @whiskeysockets/baileys..."
    npm install --no-audit --no-fund 2>/dev/null || {
        error "npm install failed"
        exit 1
    }
    cd ..
    success "WhatsApp handler dependencies installed"
else
    error "wa_handler directory not found!"
    exit 1
fi

# ─── Step 5: Create Session Directory ───────────────────────────────────────
section "📁 Step 5: Preparing Workspace"

mkdir -p wa_handler/auth_info
chmod +x main.py 2>/dev/null
success "Auth directory created"
success "main.py is now executable"

# ─── Step 6: Verification ───────────────────────────────────────────────────
section "✅ Step 6: Verification"

NODE_VER=$(node --version 2>/dev/null)
PY_VER=$(python3 --version 2>/dev/null)
NPM_VER=$(npm --version 2>/dev/null)

echo -e "  ${GRAY}Node.js  :${NC} ${GREEN}${NODE_VER:-Not found}${NC}"
echo -e "  ${GRAY}Python   :${NC} ${GREEN}${PY_VER:-Not found}${NC}"
echo -e "  ${GRAY}npm      :${NC} ${GREEN}${NPM_VER:-Not found}${NC}"

# Check Baileys
if [ -d "wa_handler/node_modules/@whiskeysockets/baileys" ]; then
    success "@whiskeysockets/baileys installed"
else
    error "Baileys not found! Try running setup again."
fi

# ─── Completion ─────────────────────────────────────────────────────────────
echo -e ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${GREEN}🎉${NC}  ${BOLD}SETUP COMPLETE!${NC}                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                      ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  ${CYAN}Run the bot with:${NC}                                   ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  ${YELLOW}python3 main.py${NC}                                        ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                      ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  ${GRAY}Or directly:${NC}                                            ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  ${YELLOW}./main.py${NC}                                                ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                      ${BLUE}║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${PURPLE}✨${NC} Happy cosmic chatting! ${PURPLE}🚀${NC}"
echo ""
