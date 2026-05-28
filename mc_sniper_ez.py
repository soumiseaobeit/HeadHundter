import asyncio
import aiohttp
import requests
import time
import json
import os
import re
import itertools
import base64
from datetime import datetime, timedelta

# ============================================================================
# TOKEN DECODER (extracts profile info from JWT)
# ============================================================================

def decode_token_info(token):
    """Extract profile name and expiration from JWT."""
    try:
        # Parse JWT payload
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        
        # Extract profile name from pfd array
        profile_name = "Unknown"
        if "pfd" in payload and isinstance(payload["pfd"], list) and len(payload["pfd"]) > 0:
            profile_name = payload["pfd"][0].get("name", "Unknown")
        
        # Extract expiration
        exp_timestamp = payload.get('exp', 0)
        exp_dt = datetime.fromtimestamp(exp_timestamp)
        expired = datetime.now() > exp_dt
        
        return {
            "profile": profile_name,
            "expires": exp_dt.strftime('%Y-%m-%d %H:%M:%S'),
            "expired": expired
        }
    except Exception as e:
        return {
            "profile": "Error parsing",
            "expires": "Unknown",
            "expired": True,
            "error": str(e)
        }

# ============================================================================
# SIMPLE CONFIG STORAGE
# ============================================================================

class SimpleConfig:
    def __init__(self):
        self.file = "sniper_data.json"
        self.data = self.load()
    
    def load(self):
        if os.path.exists(self.file):
            with open(self.file, 'r') as f:
                data = json.load(f)
                # Migration: convert old single token to array
                if "mc_token" in data:
                    old_token = data.pop("mc_token")
                    if old_token:
                        data["mc_tokens"] = [old_token]
                    else:
                        data["mc_tokens"] = []
                    self.save_data(data)
                return data
        return {"mc_tokens": [], "proxies": []}
    
    def save(self):
        self.save_data(self.data)
    
    def save_data(self, data):
        with open(self.file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_token(self, token):
        # Extract JWT from MCToken JSON if needed
        if "MCToken" in token or "mcToken" in token:
            try:
                if token.startswith('{"mcToken"') or token.startswith('{"MCToken"'):
                    parsed = json.loads(token)
                    token = parsed.get("mcToken") or parsed.get("MCToken")
                if token.startswith("MCToken "):
                    token = token.split("MCToken ", 1)[1]
            except:
                pass
        
        # Clean up quotes and whitespace
        token = token.strip().strip('"').strip("'")
        
        # Validate JWT format
        if not re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', token):
            print("[!] Warning: Token doesn't look like a valid JWT")
            print(f"[!] Token preview: {token[:50]}...")
            return False
        
        # Check if already exists
        if token in self.data["mc_tokens"]:
            print("[!] Token already exists")
            return False
        
        # Decode and show info
        info = decode_token_info(token)
        if info["expired"]:
            print(f"[⚠️] Token EXPIRED on {info['expires']}")
            print("[!] Get a fresh token from Minecraft launcher")
            confirm = input("Add anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                return False
        else:
            print(f"[✓] Profile: {info['profile']}")
            print(f"[✓] Valid until {info['expires']}")
        
        self.data["mc_tokens"].append(token)
        self.save()
        print("[✓] Token added!")
        return True
    
    def get_tokens(self):
        return self.data["mc_tokens"]
    
    def remove_token(self, index):
        if 0 <= index < len(self.data["mc_tokens"]):
            removed = self.data["mc_tokens"].pop(index)
            self.save()
            return True
        return False
    
    def add_proxies(self, proxy_list):
        self.data["proxies"] = [p.strip() for p in proxy_list if p.strip()]
        self.save()
        print(f"[✓] Saved {len(self.data['proxies'])} proxies")

# ============================================================================
# ROTATORS
# ============================================================================

class ProxyRotator:
    def __init__(self, proxies):
        self.proxies = proxies
        if self.proxies:
            self.pool = itertools.cycle(self.proxies)
            self.current = next(self.pool)
        else:
            self.current = None
    
    def get_next(self):
        if not self.proxies:
            return None
        self.current = next(self.pool)
        return self.current

class TokenRotator:
    def __init__(self, tokens):
        self.tokens = tokens
        if self.tokens:
            self.pool = itertools.cycle(self.tokens)
            self.current = next(self.pool)
        else:
            self.current = None
    
    def get_next(self):
        if not self.tokens:
            return None
        self.current = next(self.pool)
        return self.current

# ============================================================================
# SNIPER CORE
# ============================================================================

async def claim_username(session, username, mc_token, proxy=None):
    url = f"https://api.minecraftservices.com/minecraft/profile/name/{username}"
    headers = {
        "Authorization": f"Bearer {mc_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    payload = {}
    
    try:
        async with session.put(
            url, 
            headers=headers, 
            json=payload,
            proxy=proxy, 
            timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            status = resp.status
            if status == 200:
                return True, "✓ SUCCESS"
            elif status == 403:
                return False, "✗ FORBIDDEN"
            elif status == 429:
                return False, "⚠ RATE_LIMIT"
            elif status == 400:
                return False, "✗ BAD_REQUEST"
            elif status == 401:
                return False, "✗ AUTH_FAILED"
            elif status == 415:
                return False, "✗ WRONG_FORMAT"
            else:
                return False, f"✗ HTTP_{status}"
    except asyncio.TimeoutError:
        return False, "⏱ TIMEOUT"
    except Exception as e:
        return False, f"✗ {str(e)[:15]}"

async def snipe_attack(username, drop_time, mc_tokens, request_count, proxies, delay_ms=50):
    """
    Multi-token distributed attack.
    Requests are spread evenly across all tokens to bypass rate limits.
    """
    proxy_rotator = ProxyRotator(proxies)
    token_rotator = TokenRotator(mc_tokens)
    
    # Countdown
    while True:
        remaining = drop_time - time.time()
        if remaining <= 0:
            break
        
        if remaining > 60:
            print(f"\r[⏳] Waiting... {int(remaining//60)}m {int(remaining%60)}s until drop", end='', flush=True)
        else:
            print(f"\r[⏳] T-{remaining:.1f}s ", end='', flush=True)
        
        if remaining < 1:
            await asyncio.sleep(0.01)
        else:
            await asyncio.sleep(0.5)
    
    print(f"\n\n[🚀] FIRING {request_count} REQUESTS across {len(mc_tokens)} token(s) (staggered {delay_ms}ms delay)!\n")
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        async def delayed_claim(delay):
            await asyncio.sleep(delay / 1000.0)
            token = token_rotator.get_next()
            proxy = proxy_rotator.get_next() if proxy_rotator.proxies else None
            return await claim_username(session, username, token, proxy)
        
        for i in range(request_count):
            delay = i * delay_ms
            tasks.append(delayed_claim(delay))
        
        results = await asyncio.gather(*tasks)
        
        # Results summary
        success = sum(1 for r, _ in results if r)
        status_counts = {}
        for _, status in results:
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n" + "="*50)
        if success > 0:
            print(f"[🎉] CLAIMED '{username}'!")
        else:
            print(f"[❌] Failed to claim '{username}'")
        print("="*50)
        print(f"\nTotal requests: {request_count}")
        print(f"Tokens used: {len(mc_tokens)}")
        print(f"Requests per token: ~{request_count // len(mc_tokens) if mc_tokens else 0}")
        print(f"Successful: {success}")
        print("\nStatus breakdown:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"  {status}: {count}")
        print()

def parse_drop_time(input_str):
    """Parse various time formats."""
    input_str = input_str.strip().lower()
    
    # Format: "30s" or "30 seconds"
    match = re.match(r'(\d+)\s*s(?:ec(?:onds?)?)?', input_str)
    if match:
        seconds = int(match.group(1))
        return time.time() + seconds
    
    # Format: "5m" or "5 minutes"
    match = re.match(r'(\d+)\s*m(?:in(?:utes?)?)?', input_str)
    if match:
        minutes = int(match.group(1))
        return time.time() + (minutes * 60)
    
    # Format: "YYYY-MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(input_str, "%Y-%m-%d %H:%M:%S")
        return dt.timestamp()
    except:
        pass
    
    # Format: "HH:MM:SS"
    try:
        time_parts = input_str.split(':')
        if len(time_parts) == 3:
            h, m, s = map(int, time_parts)
            now = datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target.timestamp()
    except:
        pass
    
    return None

# ============================================================================
# SETUP WIZARD
# ============================================================================

def setup_wizard(config):
    print("\n" + "="*60)
    print(" "*20 + "FIRST TIME SETUP")
    print("="*60 + "\n")
    
    print("Step 1: Get your Minecraft token(s)")
    print("  1. Open Minecraft Launcher")
    print("  2. Press F12 (DevTools)")
    print("  3. Go to: Application → Local Storage → launcher.mojang.com")
    print("  4. Find the 'MCToken' entry")
    print("  5. Copy the ENTIRE value (starts with {\"mcToken\":...})")
    print()
    print("  OR just paste the raw JWT token (starts with eyJ...)")
    print()
    print("  TIP: Add multiple accounts to distribute requests and bypass rate limits!")
    print()
    
    token_input = input("Paste your first token here: ").strip()
    if token_input:
        config.add_token(token_input)
    else:
        print("[!] No token provided, you'll need to set this later")
        return
    
    # Offer to add more
    while True:
        add_more = input("\nAdd another token? (y/n): ").strip().lower()
        if add_more != 'y':
            break
        token = input("Paste token: ").strip()
        if token:
            config.add_token(token)
    
    print("\nStep 2: Proxies (optional)")
    print("  Proxies help bypass rate limits")
    print("  Format: http://ip:port or http://user:pass@ip:port")
    print("  Leave blank to skip")
    print()
    
    use_proxies = input("Do you have proxies? (y/n): ").strip().lower()
    if use_proxies == 'y':
        print("\nPaste proxies (one per line, empty line to finish):")
        proxies = []
        while True:
            line = input().strip()
            if not line:
                break
            proxies.append(line)
        
        if proxies:
            config.add_proxies(proxies)
    
    print("\n[✓] Setup complete! You're ready to snipe.")
    input("\nPress Enter to continue...")

# ============================================================================
# MAIN MENU
# ============================================================================

def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n" + "="*60)
    print(" "*15 + "HEADHUNTER USERNAME SNIPER V2")
    print(" "*20 + "BY Obeit")
    print("="*60 + "\n")

def main():
    config = SimpleConfig()
    
    # First run setup
    if not config.get_tokens():
        setup_wizard(config)
    
    while True:
        print_banner()
        
        print("1. Snipe Username")
        print("2. Manage Tokens")
        print("3. Manage Proxies")
        print("4. Settings")
        print("5. Exit")
        print()
        
        choice = input("Choose option: ").strip()
        
        if choice == "1":
            # Quick snipe
            print("\n" + "-"*60)
            username = input("Target username: ").strip()
            if not username:
                print("[!] No username entered")
                input("Press Enter to continue...")
                continue
            
            print("\nWhen does it drop?")
            print("  Examples:")
            print("    30s          = 30 seconds from now")
            print("    5m           = 5 minutes from now")
            print("    14:30:00     = Today at 2:30 PM")
            print("    2024-06-15 14:30:00 = Exact date/time")
            print("    now          = Fire immediately")
            print()
            
            time_input = input("Drop time: ").strip().lower()
            
            if time_input == "now":
                drop_timestamp = time.time()
            else:
                drop_timestamp = parse_drop_time(time_input)
            
            if not drop_timestamp:
                print("[!] Invalid time format")
                input("Press Enter to continue...")
                continue
            
            # Request count
            try:
                count_input = input("\nHow many requests? (default 20, max 500): ").strip()
                request_count = int(count_input) if count_input else 20
                request_count = min(request_count, 500)  # Cap at 500 with multi-token
            except:
                request_count = 20
            
            # Delay between requests
            try:
                delay_input = input("Delay between requests in ms? (default 50ms): ").strip()
                delay_ms = int(delay_input) if delay_input else 50
            except:
                delay_ms = 50
            
            # Confirm
            tokens = config.get_tokens()
            if not tokens:
                print("[!] No tokens configured! Use option 2 to add tokens first.")
                input("Press Enter to continue...")
                continue
            
            remaining = drop_timestamp - time.time()
            print(f"\n[✓] Target: {username}")
            print(f"[✓] Drops in: {int(remaining)} seconds" if remaining > 0 else "[✓] Firing immediately")
            print(f"[✓] Total requests: {request_count}")
            print(f"[✓] Tokens: {len(tokens)} accounts")
            print(f"[✓] Requests per token: ~{request_count // len(tokens)}")
            print(f"[✓] Delay: {delay_ms}ms between requests")
            print(f"[✓] Proxies: {len(config.data['proxies'])}")
            print(f"[✓] Total duration: ~{(request_count * delay_ms) / 1000:.1f}s")
            print()
            
            confirm = input("Start sniper? (y/n): ").strip().lower()
            if confirm == 'y':
                asyncio.run(snipe_attack(username, drop_timestamp, tokens, request_count, config.data["proxies"], delay_ms))
            
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            # Token management
            while True:
                print("\n" + "-"*60)
                print("TOKEN MANAGEMENT")
                print()
                
                tokens = config.get_tokens()
                if tokens:
                    print("Current tokens:")
                    for i, token in enumerate(tokens):
                        info = decode_token_info(token)
                        status = "EXPIRED" if info["expired"] else "Valid"
                        print(f"  {i+1}. {info['profile']} - {status} until {info['expires']}")
                else:
                    print("No tokens configured")
                
                print()
                print("1. Add token")
                print("2. Remove token")
                print("3. Back")
                
                token_choice = input("\nChoose: ").strip()
                
                if token_choice == "1":
                    print("\nPaste token (MCToken JSON or raw JWT):")
                    token = input().strip()
                    if token:
                        config.add_token(token)
                    input("\nPress Enter to continue...")
                
                elif token_choice == "2":
                    if not tokens:
                        print("[!] No tokens to remove")
                        input("\nPress Enter to continue...")
                        continue
                    try:
                        idx = int(input("Enter token number to remove: ").strip()) - 1
                        if config.remove_token(idx):
                            print("[✓] Token removed")
                        else:
                            print("[!] Invalid token number")
                    except:
                        print("[!] Invalid input")
                    input("\nPress Enter to continue...")
                
                elif token_choice == "3":
                    break
        
        elif choice == "3":
            print("\n" + "-"*60)
            print(f"Current proxies: {len(config.data['proxies'])}")
            print("\n1. Add proxies")
            print("2. Clear all proxies")
            print("3. Back")
            
            proxy_choice = input("\nChoose: ").strip()
            if proxy_choice == "1":
                print("\nPaste proxies (one per line, empty line to finish):")
                proxies = []
                while True:
                    line = input().strip()
                    if not line:
                        break
                    proxies.append(line)
                if proxies:
                    config.add_proxies(config.data["proxies"] + proxies)
            elif proxy_choice == "2":
                config.data["proxies"] = []
                config.save()
                print("[✓] Cleared all proxies")
            input("\nPress Enter to continue...")
        
        elif choice == "4":
            # Settings with profile info
            print("\n" + "-"*60)
            print("SETTINGS & ACCOUNT INFO")
            print()
            
            tokens = config.get_tokens()
            print("Configured Accounts:")
            if tokens:
                for i, token in enumerate(tokens):
                    info = decode_token_info(token)
                    status_icon = "✗" if info["expired"] else "✓"
                    print(f"  {status_icon} Account {i+1}: {info['profile']}")
                    print(f"    Expires: {info['expires']}")
                    if info["expired"]:
                        print(f"    Status: EXPIRED - needs refresh")
                    print()
            else:
                print("  No accounts configured")
            
            print(f"Proxies: {len(config.data['proxies'])}")
            print()
            print("Recommended settings for Mojang API:")
            print("  • With 1 token: 10-20 requests, 50-100ms delay")
            print("  • With 2 tokens: 20-40 requests, 50ms delay")
            print("  • With 3+ tokens: 30-100 requests, 30-50ms delay")
            print("  • More tokens = more requests without hitting rate limits")
            print("  • Timing: Fire 0-2 seconds AFTER official drop time")
            print()
            input("Press Enter to continue...")
        
        elif choice == "5":
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()