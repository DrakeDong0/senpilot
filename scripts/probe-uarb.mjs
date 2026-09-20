import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const url = process.env.UARB_URL ?? "https://uarb.novascotia.ca/fmi/webd/UARB15";
const chrome = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const timeout = Number(process.env.UARB_TIMEOUT_MS ?? 30000);
const output = "artifacts/uarb-entry.png";

let browser;
let page;
try {
  browser = await chromium.launch({ headless: true, executablePath: chrome });
  page = await browser.newPage();
  console.log(`Opening ${url} (timeout ${timeout} ms)`);
  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout });
  console.log(`HTTP status: ${response?.status() ?? "no response"}`);
  await page.getByText("Go Directly to Matter").waitFor({ timeout });
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({ path: output, fullPage: true });
  console.log(`Title: ${await page.title()}`);
  console.log(`URL: ${page.url()}`);
  console.log(`Screenshot: ${output}`);
  console.log((await page.locator("body").innerText()).slice(0, 10000));
} catch (error) {
  console.error(`UARB browser probe failed: ${error.message}`);
  if (page) {
    console.error(`Last browser URL: ${page.url()}`);
    try {
      console.error(`Page text: ${(await page.locator("body").innerText({ timeout: 2000 })).slice(0, 1000)}`);
      await mkdir("artifacts", { recursive: true });
      await page.screenshot({ path: output, timeout: 3000 });
      console.error(`Diagnostic screenshot: ${output}`);
    } catch (diagnosticError) {
      console.error(`Page diagnostics unavailable: ${diagnosticError.message}`);
    }
  }
  process.exitCode = 1;
} finally {
  await browser?.close();
}
