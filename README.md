How to get your bearer token
Sign in to your Minecraft account at minecraft.net
Open the Chrome / Firefox developer tools (ctrl + shift + i or f12) or right click and click inspect element
Go to the "console" tab
Paste this code into the console:

```console.log(`; ${document.cookie}`.split('; bearer_token=').pop().split(';').shift())]```
                
Or, alternatively, drag this text to your browser's URL shortcuts bar, and click it.
Copy the bearer token that it shows in the console
