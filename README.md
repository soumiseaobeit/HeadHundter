# HOW TO GET YOUR BEARER TOKEN
Sign in to your Minecraft account at `minecraft.net`
Open the Chrome / Firefox developer tools (ctrl + shift + i or f12) or right click and click inspect element
Go to the "console" tab
Paste this code into the console:

```console.log(`; ${document.cookie}`.split('; bearer_token=').pop().split(';').shift())]```

_If any issues dm on discord : marinettepute_
