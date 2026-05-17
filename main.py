#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║            SKY AI WHATSAPP AGENT v2.0                ║
║     Connect Gemini AI to WhatsApp via Baileys        ║
║     Powered by api.nexray.eu.cc/gemini               ║
╚══════════════════════════════════════════════════════╝
"""

import json
import os
import subprocess
import sys
import time
import signal
import threading
import urllib.parse
import urllib.request
import re
import logging
from datetime import datetime
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
CONFIG_FILE = 'config.json'
WA_DIR = 'wa_handler'
NODE_SCRIPT = os.path.join(WA_DIR, 'index.js')
AUTH_DIR = os.path.join(WA_DIR, 'auth_info')
API_ENDPOINT = "https://api.nexray.eu.cc/ai/gemini"
LOG_FILE = "sky_ai_bot.log"

# ─── Global State ────────────────────────────────────────────────────────────
node_process = None
node_stdin = None
config = {}
running = True
output_threads = []

# ─── Logging Setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('SkyAI')


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        logger.info(f"Config loaded: {config.get('phone_number', 'Not set')}")
    else:
        config = {
            "phone_number": "",
            "session_saved": False,
            "auto_reconnect": True,
            "api_endpoint": API_ENDPOINT,
            "connected": False,
            "pairing_code_generated": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        save_config()
        logger.info("New config file created")


def save_config():
    config['updated_at'] = datetime.now().isoformat()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


# ═══════════════════════════════════════════════════════════════════════════════
# UI / DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    'blue': '\033[38;5;39m',
    'green': '\033[38;5;82m',
    'yellow': '\033[38;5;226m',
    'red': '\033[38;5;196m',
    'purple': '\033[38;5;141m',
    'cyan': '\033[38;5;51m',
    'pink': '\033[38;5;206m',
    'orange': '\033[38;5;214m',
    'gray': '\033[38;5;245m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}


def c(color, text):
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def print_banner():
    banner = f"""
{c('blue', '    ╔═══════════════════════════════════════════════════════╗')}
{c('blue', '    ║')}  {c('yellow', '✦')}  {c('cyan', 'SKY AI WHATSAPP AGENT')} {c('bold', 'v2.0')}  {c('purple', '✦')}            {c('blue', '║')}
{c('blue', '    ║')}  {c('gray', '───────────────────────────────────────────────')}  {c('blue', '║')}
{c('blue', '    ║')}       {c('pink', '🌌')}  {c('cyan', 'Powered by Gemini AI')}  {c('pink', '🌌')}                {c('blue', '║')}
{c('blue', '    ║')}       {c('green', '🚀')}  {c('gray', 'Connected to the Galaxy')}  {c('green', '🚀')}             {c('blue', '║')}
{c('blue', '    ╚═══════════════════════════════════════════════════════╝')}
    """
    print(banner)


def print_status(text, emoji="✦"):
    print(f"  {c('blue', '[')}{c('cyan', emoji)}{c('blue', ']')} {text}")


def print_error(text):
    print(f"  {c('red', '[✗]')} {text}")
    logger.error(text)


def print_success(text):
    print(f"  {c('green', '[✓]')} {text}")


def print_warning(text):
    print(f"  {c('yellow', '[⚠]')} {text}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_node():
    try:
        result = subprocess.run(['node', '--version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print_success(f"Node.js detected: {version}")
            return True
        else:
            print_error("Node.js check failed")
            return False
    except FileNotFoundError:
        print_error("Node.js not found! Please run setup.sh first.")
        return False
    except Exception as e:
        print_error(f"Node.js check error: {e}")
        return False


def install_npm_deps():
    print_status("Installing Node.js dependencies...", "📦")
    try:
        result = subprocess.run(
            ['npm', 'install', '--no-audit', '--no-fund'],
            cwd=WA_DIR,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print_success("Dependencies installed!")
            return True
        else:
            print_error(f"npm install failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_error(f"npm install error: {e}")
        return False


def check_deps():
    node_modules = os.path.join(WA_DIR, 'node_modules')
    package_json = os.path.join(WA_DIR, 'package.json')

    if not os.path.exists(package_json):
        print_error("package.json not found in wa_handler/")
        return False

    if not os.path.exists(node_modules):
        print_status("Dependencies not found. Installing...")
        return install_npm_deps()

    # Quick check for baileys
    baileys_path = os.path.join(node_modules, '@whiskeysockets', 'baileys')
    if not os.path.exists(baileys_path):
        print_status("Baileys not found. Reinstalling...")
        return install_npm_deps()

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# NODE PROCESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def start_node_process():
    global node_process, node_stdin

    print_status("Starting WhatsApp engine...", "⚡")

    try:
        node_process = subprocess.Popen(
            ['node', NODE_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=os.path.abspath('.')
        )
        node_stdin = node_process.stdin
        print_success(f"WhatsApp engine started (PID: {node_process.pid})")
        return node_process
    except Exception as e:
        print_error(f"Failed to start Node.js process: {e}")
        return None


def send_command(cmd):
    global node_stdin
    if node_stdin and not node_stdin.closed:
        try:
            node_stdin.write(json.dumps(cmd) + '\n')
            node_stdin.flush()
        except BrokenPipeError:
            print_error("Node.js process pipe broken")
            return False
        except Exception as e:
            print_error(f"Send command error: {e}")
            return False
        return True
    return False


def stop_node_process():
    global node_process, node_stdin

    if node_process:
        print_status("Stopping WhatsApp engine...", "🛑")
        try:
            send_command({'type': 'logout'})
            time.sleep(1)
            node_process.terminate()
            node_process.wait(timeout=5)
        except Exception:
            try:
                node_process.kill()
            except Exception:
                pass
        print_success("WhatsApp engine stopped")
        node_process = None
        node_stdin = None


# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI API
# ═══════════════════════════════════════════════════════════════════════════════

def call_gemini_api(text):
    """Call the Gemini REST API and return the response text."""
    if not text or not text.strip():
        return ("👋 Halo! Gunakan format: /chat <pertanyaan>\n"
                "Contoh: /chat siapa presiden Indonesia?")

    encoded_query = urllib.parse.quote(text.strip())
    url = f"{API_ENDPOINT}?text={encoded_query}"

    logger.info(f"Calling Gemini API: text={text[:80]}...")
    print_status(f"Sending to Gemini AI...", "🤖")

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'SkyAI-WhatsApp-Agent/2.0',
                'Accept': 'text/plain, */*'
            }
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = response.read().decode('utf-8')
            status_code = response.getcode()

            if status_code == 200 and result:
                logger.info(f"Gemini API success: {len(result)} chars received")
                print_success(f"AI Response received ({len(result)} chars)")
                return result
            else:
                logger.warning(f"Gemini API returned HTTP {status_code}")
                return (f"⚠️ Maaf, server AI merespon dengan kode "
                        f"{status_code}. Silakan coba lagi.")

    except urllib.error.HTTPError as e:
        logger.error(f"Gemini API HTTP Error: {e.code} - {e.reason}")
        return (f"⚠️ Maaf, server AI error (HTTP {e.code}). "
                f"Silakan coba lagi nanti.")

    except urllib.error.URLError as e:
        logger.error(f"Gemini API URL Error: {e.reason}")
        return ("⚠️ Maaf, tidak dapat terhubung ke server AI. "
                "Periksa koneksi internet Anda.")

    except Exception as e:
        logger.error(f"Gemini API unexpected error: {e}")
        return f"⚠️ Terjadi kesalahan saat menghubungi AI: {str(e)[:50]}"


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

def handle_message(message_data):
    """Process an incoming WhatsApp message."""
    text = message_data.get('text', '')
    from_jid = message_data.get('from', '')
    sender = message_data.get('sender', '')
    push_name = message_data.get('pushName', 'Unknown')
    timestamp = message_data.get('timestamp', '')

    time_str = ""
    if timestamp:
        try:
            time_str = datetime.fromtimestamp(
                int(timestamp)
            ).strftime('%H:%M:%S')
        except Exception:
            time_str = ""

    print(f"\n  {c('orange', '[📩 INCOMING]')} {c('gray', time_str)}")
    print(f"  {c('purple', '  From:')} {push_name} {c('gray', f'({sender})')}")
    print(f"  {c('cyan', '  Text:')} {c('gray', text[:120] + ('...' if len(text) > 120 else ''))}")

    logger.info(f"MSG | From: {push_name} ({sender}) | Text: {text[:100]}")

    # Check for /chat trigger (case-insensitive, also /ai or /ask)
    trigger_match = re.match(r'^/(chat|ai|ask)\b\s*(.*)', text, re.IGNORECASE)

    if trigger_match:
        query = trigger_match.group(2).strip()

        if not query:
            response = (
                "👋 *Halo! Saya Sky AI Bot!*\n\n"
                "Gunakan format:\n"
                "`/chat pertanyaanmu`\n\n"
                "Contoh:\n"
                "`/chat siapa penemu lampu?`\n"
                "`/chat jelaskan teori relativitas`\n"
                "`/chat buatkan puisi tentang bintang`"
            )
            print_status(f"Empty query from {push_name}, sending guide", "ℹ️")
        else:
            send_command({'type': 'send_typing', 'to': from_jid, 'status': True})
            print_status(f"Processing AI query: {query[:60]}...", "🧠")
            response = call_gemini_api(query)
            send_command({'type': 'send_typing', 'to': from_jid, 'status': False})

        send_command({'type': 'send_message', 'to': from_jid, 'text': response})
        logger.info(f"RESP | To: {push_name} ({sender}) | Length: {len(response)} chars")
        print_success(f"Response sent to {push_name}")
    else:
        print_status("Message ignored (no /chat trigger)", "⏭️")
        logger.debug(f"IGNORED | From: {push_name} | Text: {text[:50]}")


# ═══════════════════════════════════════════════════════════════════════════════
# NODE OUTPUT READER
# ═══════════════════════════════════════════════════════════════════════════════

def read_node_output():
    """Read JSON lines from Node.js stdout and process them."""
    global node_process, running

    while running and node_process and node_process.stdout \
            and not node_process.stdout.closed:
        try:
            line = node_process.stdout.readline()
            if not line:
                if running:
                    time.sleep(0.5)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                if line:
                    print(f"  {c('gray', '[Node]')} {line}")
                continue

            msg_type = data.get('type', '')

            if msg_type == 'pairing_code':
                code = data.get('code', '')
                print(f"""
  {c('blue', '╔════════════════════════════════════════════════════╗')}
  {c('blue', '║')}  {c('yellow', '🔐  PAIRING CODE')}                               {c('blue', '║')}
  {c('blue', '╠════════════════════════════════════════════════════╣')}
  {c('blue', '║')}                                                  {c('blue', '║')}
  {c('blue', '║')}       {c('yellow', code.center(40))}        {c('blue', '║')}
  {c('blue', '║')}                                                  {c('blue', '║')}
  {c('blue', '╚════════════════════════════════════════════════════╝')}
                """)
                print(f"  {c('cyan', '📱')} Buka WhatsApp > 3 titik > "
                      f"Perangkat tertaut > Hubungkan perangkat")
                print(f"  {c('cyan', '📝')} Masukkan kode pairing di atas\n")

                config['pairing_code'] = code
                config['pairing_code_generated'] = True
                save_config()

                input(f"  {c('green', '[Press Enter after pairing is complete]')}")

            elif msg_type == 'ready':
                user_info = data.get('user', '')
                print_success(f"✅ WhatsApp Bot ONLINE! "
                              f"{c('gray', f'({user_info})')}")
                print(f"\n  {c('green', '━' * 55)}")
                print(f"  {c('cyan', '👂')} Waiting for /chat messages...")
                config['connected'] = True
                save_config()

            elif msg_type == 'message':
                handle_message(data)

            elif msg_type == 'sent':
                chunks = data.get('chunks', 1)
                print_success(f"Message delivered ✅ "
                              f"{c('gray', f'({chunks} chunk(s))')}")

            elif msg_type == 'disconnected':
                if data.get('reconnect'):
                    print_warning("Connection lost. Reconnecting...")
                elif data.get('loggedOut'):
                    print_error("Logged out from WhatsApp!")
                    print_status("Run the script again to re-pairing.", "🔄")
                    config['session_saved'] = False
                    config['connected'] = False
                    save_config()
                else:
                    print_error(f"Disconnected: {data.get('message', '')}")

            elif msg_type == 'info':
                print_status(data.get('message', ''), "ℹ️")

            elif msg_type == 'error':
                print_error(data.get('message', ''))

            elif msg_type == 'pong':
                pass

            elif msg_type == 'status_report':
                print_success(f"Status: connected={data.get('connected')}")

            else:
                if msg_type:
                    print(f"  {c('gray', f'[Node:{msg_type}]')} "
                          f"{json.dumps(data)[:100]}")

        except Exception as e:
            if running:
                print_error(f"Node output error: {e}")
                time.sleep(1)

    if running:
        print_error("WhatsApp engine output stream ended")


def monitor_stderr():
    """Read Node.js stderr and log it."""
    global node_process, running

    while running and node_process and node_process.stderr \
            and not node_process.stderr.closed:
        try:
            line = node_process.stderr.readline()
            if not line:
                time.sleep(0.5)
                continue
            logger.warning(f"[Node STDERR] {line.strip()}")
        except Exception:
            break


# ═══════════════════════════════════════════════════════════════════════════════
# PAIRING FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def pairing_flow():
    """Run the WhatsApp pairing flow."""
    print(f"""
  {c('blue', '═════════════════════════════════════════════════════')}
  {c('yellow', '         🔐 WhatsApp Pairing Setup')}
  {c('blue', '═════════════════════════════════════════════════════')}
    """)

    # Check for existing session
    if os.path.exists(AUTH_DIR) and os.listdir(AUTH_DIR):
        print_success("Existing session found!")
        use_existing = input(
            f"  {c('cyan', '[?]')} Use existing session? (Y/n): "
        ).strip().lower()
        if use_existing != 'n':
            return True
        else:
            import shutil
            shutil.rmtree(AUTH_DIR, ignore_errors=True)
            os.makedirs(AUTH_DIR, exist_ok=True)
            config['session_saved'] = False
            save_config()

    # Ask for phone number
    while True:
        phone = input(
            f"  {c('cyan', '[📱]')} Enter WhatsApp number (with country code)\n"
            f"       Example: 6281234567890, 081234567890\n"
            f"       {c('cyan', '>>>')} "
        ).strip()
        phone = re.sub(r'[^0-9]', '', phone)

        # Normalize to international format (62 for Indonesia)
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        if not phone.startswith('62'):
            phone = '62' + phone

        if len(phone) >= 10:
            break
        print_error("Invalid number! Minimum 10 digits.")

    config['phone_number'] = phone
    save_config()
    print_success(f"Number saved: {phone}")

    print_status("Requesting pairing code from WhatsApp...", "📡")
    send_command({'type': 'pairing', 'number': phone})

    # The pairing code response will be handled in the output reader thread
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════

def cleanup(signum=None, frame=None):
    """Graceful shutdown on SIGINT/SIGTERM."""
    global running, node_process

    print(f"\n\n  {c('blue', '[🛑]')} Shutting down Sky AI WhatsApp Agent...")

    running = False
    stop_node_process()

    print(f"""
  {c('green', '╔═══════════════════════════════════════════╗')}
  {c('green', '║')}     {c('yellow', '✨ Bot Stopped. See you later! ✨')}    {c('green', '║')}
  {c('green', '╚═══════════════════════════════════════════╝')}
    """)
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Setup signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Clear terminal
    os.system('clear' if os.name == 'posix' else 'cls')

    # Display banner
    print_banner()

    logger.info("=" * 60)
    logger.info("Sky AI WhatsApp Agent v2.0 - Starting...")
    logger.info("=" * 60)

    # Check environment
    if not check_node():
        print_status("Please run: bash setup.sh", "💡")
        sys.exit(1)

    # Load config
    load_config()

    # Check Node.js dependencies
    if not check_deps():
        print_error("Dependency check failed. Run: bash setup.sh")
        sys.exit(1)

    # Ensure auth directory exists
    os.makedirs(AUTH_DIR, exist_ok=True)

    # Start Node.js WhatsApp engine
    proc = start_node_process()
    if not proc:
        print_error("Failed to start WhatsApp engine")
        sys.exit(1)

    # Allow Node process to initialize
    time.sleep(2)

    # Start output reader threads
    t1 = threading.Thread(target=read_node_output, daemon=True)
    t2 = threading.Thread(target=monitor_stderr, daemon=True)
    t1.start()
    t2.start()
    output_threads.append(t1)
    output_threads.append(t2)

    # Small delay for threads to start
    time.sleep(0.5)

    # Run pairing flow (blocks until paired or not)
    session_exists = (config.get('session_saved')
                      and os.path.exists(AUTH_DIR)
                      and os.listdir(AUTH_DIR))
    if not session_exists:
        pairing_flow()
    else:
        print_success(f"Session found for "
                      f"{config.get('phone_number', 'Unknown')}")
        print_success("Bot is starting... waiting for connection")

    # Display running status
    number_display = config.get('phone_number', 'N/A')
    if len(number_display) > 5:
        number_display = number_display[:5] + 'xxxxx'

    print(f"""
  {c('blue', '╔════════════════════════════════════════════════════')}
  {c('blue', '║')}     {c('green', '🚀  SKY AI WHATSAPP AGENT IS RUNNING')}   {c('blue', '║')}
  {c('blue', '║')}                                           {c('blue', '║')}
  {c('blue', '║')}  {c('cyan', '📱')} Number: {c('yellow', number_display)}          {c('blue', '║')}
  {c('blue', '║')}  {c('cyan', '💬')} Trigger: {c('yellow', '/chat <message>')}       {c('blue', '║')}
  {c('blue', '║')}  {c('cyan', '📝')} Log file: {c('yellow', LOG_FILE)}             {c('blue', '║')}
  {c('blue', '║')}  {c('cyan', '🔴')} Press {c('red', 'Ctrl+C')} to stop            {c('blue', '║')}
  {c('blue', '╚════════════════════════════════════════════════════')}
    """)

    # Keep main alive
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == '__main__':
    main()
