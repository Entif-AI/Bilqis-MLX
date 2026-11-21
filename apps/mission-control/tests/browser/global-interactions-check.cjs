const fs = require("fs");
const http = require("http");
const path = require("path");

const repo = path.resolve(__dirname, "../../../..");
const renderer = path.join(repo, "apps/mission-control/renderer");
const playwright = require(process.env.BILQIS_PLAYWRIGHT_MODULE ||
  "/Users/emilie/Code/mission-control/node_modules/playwright");
const chrome = process.env.BILQIS_CHROME_PATH ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const operator = JSON.parse(fs.readFileSync(path.join(
  repo, "apps/mission-control/fixtures/operator-view-v1.json"), "utf8"));
const mime = {
  ".html": "text/html",
  ".mjs": "text/javascript",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
};
const bridge = `window.bamfMissionControl={
launchMode:"fixtures",
connect:async()=>({state:"healthy",serviceLive:true,serviceReady:true,learnerReady:true,learnerActive:false,learnerState:"READY",runId:"fixture-run",generation:7}),
status:async()=>({state:"healthy",serviceLive:true,serviceReady:true,learnerReady:true,learnerActive:false,learnerState:"READY",runId:"fixture-run",generation:7}),
querySnapshot:async()=>(${JSON.stringify(operator)})
};`;

function server() {
  return http.createServer((req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    let file = path.join(repo, decodeURIComponent(url.pathname));
    if (url.pathname === "/" || url.pathname === "/apps/mission-control/renderer/") {
      file = path.join(renderer, "index.html");
    }
    if (!file.startsWith(repo) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    const body = fs.readFileSync(file);
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    res.end(body);
  });
}

(async () => {
  const { default: journey } = await import("./journeys/global-interactions-journey.mjs");
  const srv = server();
  await new Promise(resolve => srv.listen(0, "127.0.0.1", resolve));
  const browser = await playwright.chromium.launch({ executablePath: chrome, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 920 } });
    page.setDefaultTimeout(5000);
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    await page.addInitScript({ content: bridge });
    await page.goto(`http://127.0.0.1:${srv.address().port}/apps/mission-control/renderer/`);
    const result = await journey(page);
    if (errors.length) throw new Error(`browser page errors: ${errors.join(" | ")}`);
    console.log(result);
  } finally {
    await browser.close();
    await new Promise(resolve => srv.close(resolve));
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
