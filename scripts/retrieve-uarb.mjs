import { chromium } from "playwright";
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";

const URL = "https://uarb.novascotia.ca/fmi/webd/UARB15";
const CATEGORIES = ["Exhibits", "Key Documents", "Other Documents", "Transcripts", "Recordings"];
const matter = process.argv[2]?.toUpperCase();
const requested = process.argv.slice(3).join(" ");

if (!/^M\d{5}$/.test(matter ?? "") || !CATEGORIES.includes(requested)) {
  console.error("Usage: npm run inspect:uarb -- M12205 'Other Documents'");
  process.exit(2);
}

async function unique(locator, description) {
  const count = await locator.count();
  if (count !== 1) throw new Error(`Expected one ${description}; found ${count}`);
  return locator;
}

async function openMatter(page) {
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  const label = page.getByText("Go Directly to Matter", { exact: true });
  await label.waitFor();
  let input = page.getByRole("textbox", { name: /Go Directly to Matter/i });
  if (await input.count() !== 1) {
    input = label.locator("xpath=..").locator("input");
  }
  await (await unique(input, "matter search input")).fill(matter);
  const search = page.getByRole("button", { name: "Search", exact: true });
  await (await unique(search, "Search button")).click();
  await page.getByText(matter, { exact: true }).first().waitFor();
}

async function openCategory(page, category) {
  let tab = page.getByRole("tab", { name: new RegExp(`^${category}(?:\\s*\\(\\d+\\))?$`, "i") });
  if (await tab.count() !== 1) {
    tab = page.getByText(category, { exact: true });
  }
  await (await unique(tab, `${category} tab`)).click();
  await page.getByText(category, { exact: true }).first().waitFor();
}

async function readFoundCount(page) {
  const text = await page.locator("body").innerText();
  const matches = [...text.matchAll(/Found Count\s*:?\s*([\d,]+)/gi)];
  if (matches.length !== 1) return null;
  return Number(matches[0][1].replaceAll(",", ""));
}

async function downloadFirst(page, directory) {
  const buttons = page.getByRole("button", { name: "Go Get It", exact: true });
  if (await buttons.count() === 0) return null;
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 30000 }),
    buttons.first().click(),
  ]);
  const filename = path.basename(download.suggestedFilename());
  const destination = path.join(directory, filename);
  await download.saveAs(destination);
  if ((await stat(destination)).size === 0) throw new Error("Downloaded file is empty");
  return { filename, path: destination };
}

let browser;
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  await openMatter(page);
  const counts = {};
  for (const category of CATEGORIES) {
    await openCategory(page, category);
    counts[category] = await readFoundCount(page);
  }
  await openCategory(page, requested);
  const directory = path.resolve("artifacts", matter);
  await mkdir(directory, { recursive: true });
  const firstDownload = await downloadFirst(page, directory);
  console.log(JSON.stringify({ matter, requested, counts, firstDownload }, null, 2));
} catch (error) {
  console.error(`UARB inspection failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
