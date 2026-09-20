import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const url = "https://uarb.novascotia.ca/fmi/webd/UARB15";
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = "artifacts/uarb-entry.png";

let browser;
try {
  browser = await chromium.launch({ headless: true, executablePath: chrome });
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("Go Directly to Matter").waitFor({ timeout: 30000 });
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({ path: output, fullPage: true });
  console.log(`Title: ${await page.title()}`);
  console.log(`URL: ${page.url()}`);
  console.log(`Screenshot: ${output}`);
  console.log((await page.locator("body").innerText()).slice(0, 10000));
} catch (error) {
  console.error(`UARB browser probe failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
