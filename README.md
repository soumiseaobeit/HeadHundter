# HeadHunter

A lightweight Minecraft username sniper designed to send requests exactly when a username becomes available.

## Features

- Fast username sniping
- Custom request amount
- Adjustable request delay
- Proxy support
- Multiple date/time formats
- Simple terminal interface

---

# Getting Your Bearer Token

1. Sign in to your Minecraft account on `minecraft.net`
2. Open Developer Tools:
   - `CTRL + SHIFT + I`
   - or `F12`
   - or right-click anywhere and press **Inspect**
3. Open the **Console** tab
4. Paste this code into it
```console.log(`; ${document.cookie}`.split('; bearer_token=').pop().split(';').shift())
                ```
5. Copy your bearer token
6. And voilà !

---

# Installation

Clone or download the repository:

```bash
git clone https://github.com/yourname/HeadHunter.git
```

Open the project folder and edit `sniper_data.json`.

---

# Configuration

## Adding Your Minecraft Token

Replace the token value with your own bearer token:

```json
"mc_token": "your_minecraft_bearer_token_here"
```

---

## Adding Proxies (Optional)

If you want to use proxies, add them like this:

```json
"proxies": [
  "http://user:password@38.154.154.154:67",
  "http://user:password@38.158.154.154:67"
]
```

---

# Usage

Launch the sniper:

```bash
python mc_sniper_ez.py
```

You will see a menu.

Press `1` to start sniping a username.

Example:

```txt
bigfanboyofobeit
```

Then enter the username drop time.

Supported formats:

```txt
30s                   = 30 seconds from now
5m                    = 5 minutes from now
14:30:00              = Today at 2:30 PM
2024-06-15 14:30:00  = Exact date and time
now                   = Launch immediately
```

Here is where to see the time it is avaible: 

<img width="597" height="220" alt="Preview" src="https://github.com/user-attachments/assets/cfe4e981-48db-4dc9-a7b7-4d259839ee47" />

After that, the sniper will ask:

- Number of requests (default: `20`)
- Delay between requests in milliseconds (default: `50ms`)

Finally:

```txt
Start Sniper? (Y/N)
```

Press `Y` and wait for the sniper to start.

---

# Notes

- A stable internet connection is recommended
- Using proxies may improve reliability
- Make sure your token is valid before starting

---

# Support

If you run into any issues, feel free to contact me on Discord:

```txt
marinettepute
```
