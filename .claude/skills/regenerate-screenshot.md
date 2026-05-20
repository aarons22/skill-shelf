---
name: regenerate-screenshot
description: Regenerate the SkillShelf product screenshots in docs/assets/. Spins up an isolated Docker environment on port 8899, seeds realistic demo data, captures two screenshots (marketplace list + detail), saves them, and tears down the environment. Invoke after any UI change that should be reflected in the README.
---

You are regenerating the SkillShelf product screenshots. This runs a fully isolated Docker deployment so the dev environment on port 80 is never touched and prior data is never affected.

## Prerequisites

- Docker and Docker Compose must be running
- You must be in the repo root: `/Users/aaronsapp/projects/skillforge`
- Chrome must be connected via the Claude in Chrome extension

## Step 1: Tear down any leftover screenshot environment

```bash
docker compose -f docker-compose.screenshot.yml -p skillshelf-screenshot down -v 2>/dev/null || true
```

## Step 2: Start the isolated screenshot environment

```bash
docker compose -f docker-compose.screenshot.yml -p skillshelf-screenshot up -d --build
```

This builds both images from source and starts the stack on port 8899 with an empty ephemeral volume. The frontend depends_on the backend health check, so both services will be ready once the command returns.

Wait for the frontend to come up (the backend health check is the gate):

```bash
docker compose -f docker-compose.screenshot.yml -p skillshelf-screenshot ps
```

If the frontend isn't up yet, poll with:
```bash
until curl -sf http://localhost:8899/ > /dev/null; do sleep 2; done && echo "ready"
```

## Step 3: Seed demo data

```bash
backend/.venv/bin/python3 scripts/seed_screenshot_data.py http://localhost:8899
```

If the venv doesn't have httpx, fall back to:
```bash
python3 -m pip install httpx -q && python3 scripts/seed_screenshot_data.py http://localhost:8899
```

The seed script creates two marketplaces (Engineering Tools + Finance Team Skills) each with three plugins and skills. It completes the setup flow internally.

## Step 4: Connect to Chrome and set viewport

Use `mcp__Claude_in_Chrome__list_connected_browsers` then `select_browser` (or `switch_browser` if none connected) to connect to Chrome.

```
tabs_context_mcp(createIfEmpty=true)
resize_window(tabId=<id>, width=1280, height=800)
```

## Step 5: Capture the marketplace list screenshot

Start the one-shot save server:

```bash
python3 -c "
import http.server, base64, json, os

OUTPUT = os.environ.get('SCREENSHOT_OUTPUT', 'docs/assets/screenshot-list.png')

class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for h, v in [('Access-Control-Allow-Origin','*'),('Access-Control-Allow-Methods','POST'),('Access-Control-Allow-Headers','Content-Type')]:
            self.send_header(h, v)
        self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        img = base64.b64decode(body['image'].split(',')[1])
        with open(OUTPUT, 'wb') as f:
            f.write(img)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, *a): pass

s = http.server.HTTPServer(('127.0.0.1', 7654), H)
s.handle_request()
s.handle_request()
s.server_close()
print('saved to', OUTPUT)
" &
echo "save server ready"
```

Navigate and capture:

```
navigate(tabId=<id>, url="http://localhost:8899/")
```

Wait a moment for the page to render, then run this JavaScript:

```javascript
new Promise(async (resolve, reject) => {
  try {
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://html2canvas.hertzen.com/dist/html2canvas.min.js';
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
    const canvas = await html2canvas(document.documentElement, {
      scale: 1, useCORS: true, allowTaint: true,
      width: 1280, height: 800, windowWidth: 1280, windowHeight: 800
    });
    const dataUrl = canvas.toDataURL('image/png');
    const resp = await fetch('http://127.0.0.1:7654', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({image: dataUrl})
    });
    resolve(await resp.text());
  } catch(e) { reject(String(e)); }
})
```

Should return `"OK"`. Verify: `ls -lh docs/assets/screenshot-list.png` (expect > 10 KB).

## Step 6: Capture the marketplace detail screenshot

Repeat step 5's save server setup targeting `docs/assets/screenshot-detail.png`, then navigate:

```
navigate(tabId=<id>, url="http://localhost:8899/marketplaces/engineering-tools")
```

Before capturing, replace the `localhost:8899` URLs in the DOM with the production-looking placeholder so install snippets look polished in the screenshot:

```javascript
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
let node;
while ((node = walker.nextNode())) {
  if (node.nodeValue.includes('localhost:8899')) {
    node.nodeValue = node.nodeValue.replace(/http:\/\/localhost:8899/g, 'https://skillshelf.example.com');
  }
}
'done'
```

Then run the same html2canvas capture JavaScript from step 5 (pointing to port 7654).

## Step 7: Tear down the screenshot environment

```bash
docker compose -f docker-compose.screenshot.yml -p skillshelf-screenshot down -v
```

The `-v` flag removes the ephemeral volume. The dev environment on port 80 is unchanged.

## Step 8: Verify and report

```bash
ls -lh docs/assets/screenshot-list.png docs/assets/screenshot-detail.png
```

Both files should be > 10 KB. Then tell the user:

"Screenshots saved. Commit them with:
```
git add docs/assets/screenshot-list.png docs/assets/screenshot-detail.png
git commit -m 'docs: regenerate README screenshots'
```"
