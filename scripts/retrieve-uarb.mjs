import { chromium } from "playwright";
import { mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const URL = "https://uarb.novascotia.ca/fmi/webd/UARB15";
const CATEGORIES = ["Exhibits", "Key Documents", "Other Documents", "Transcripts", "Recordings"];
const SITE_LABELS = {
  Exhibits: ["Exhibits"],
  "Key Documents": ["Key Documents"],
  "Other Documents": ["Other Documents"],
  Transcripts: ["Transcripts"],
  Recordings: ["Audio Files", "Recordings"],
};
const matter = process.argv[2]?.toUpperCase();
const requested = process.argv[3];
const directory = path.resolve(process.argv[4] ?? path.join("artifacts", matter ?? "unknown"));
const output = process.argv[5] ? path.resolve(process.argv[5]) : null;

if (!/^M\d{5}$/.test(matter ?? "") || !CATEGORIES.includes(requested)) {
  console.error("Usage: node scripts/retrieve-uarb.mjs M12205 'Other Documents' [download_dir] [result.json]");
  process.exit(2);
}

async function unique(locator, description) {
  const count = await locator.count();
  if (count !== 1) throw new Error(`Expected one ${description}; found ${count}`);
  return locator;
}

async function openMatter(page) {
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("Go Directly to Matter", { exact: true }).waitFor();
  // FileMaker exposes this field as a focusable div, not a native input.
  const field = page.getByText("eg M01234", { exact: true })
    .locator("xpath=../div[contains(@class, 'text')]");
  await (await unique(field, "matter search field")).click();
  await page.waitForFunction(() => document.querySelector(".fm_object_254 .text")?.getAttribute("contenteditable") === "true");
  await field.fill(matter);
  await field.press("Tab");
  const search = page.locator("button[id*='o258']");
  await (await unique(search, "direct matter search button")).click();
  await page.waitForFunction(() => document.body.innerText.includes("Back to Search Results")
    || document.body.innerText.includes("No Records Found"), undefined, { timeout: 30000 });
  if (await page.getByText("No Records Found", { exact: true }).count()) {
    throw new Error(`No UARB records found for ${matter}`);
  }
  const shownMatter = (await page.locator(".fm_object_286 .text").innerText()).trim();
  if (shownMatter !== matter) throw new Error(`UARB displayed ${shownMatter} instead of ${matter}`);
}

async function categoryTab(page, category) {
  for (const label of SITE_LABELS[category]) {
    let tab = page.getByRole("button", { name: new RegExp(`^${label}\\s*-\\s*\\d[\\d,]*$`, "i") });
    if (await tab.count() === 1) return tab;
    tab = page.getByRole("tab", { name: new RegExp(`^${label}(?:\\s|$)`, "i") });
    if (await tab.count() === 1) return tab;
    tab = page.getByText(new RegExp(`^${label}\\s*(?:-\\s*|\\(?)(?:\\d[\\d,]*)\\)?$`, "i"))
      .filter({ visible: true });
    if (await tab.count() === 1) return tab;
  }
  throw new Error(`Could not locate ${category} tab`);
}

async function readTabTotal(tab, category) {
  for (const candidate of [tab, tab.locator("xpath=..")]) {
    const text = (await candidate.innerText()).trim();
    if (!SITE_LABELS[category].some(label => text.startsWith(label))) continue;
    const numbers = [...text.matchAll(/\b\d[\d,]*\b/g)];
    if (numbers.length === 1) return Number(numbers[0][0].replaceAll(",", ""));
  }
  return null;
}

async function openCategory(page, category, tab = null) {
  const before = await page.locator("body").innerText();
  tab ??= await categoryTab(page, category);
  await (await unique(tab, `${category} tab`)).click();
  await tab.first().waitFor({ state: "visible" });
  if (await tab.getAttribute("aria-selected") === "true") return true;
  try {
    await page.waitForFunction(previous => document.body.innerText !== previous, before, { timeout: 10000 });
    return true;
  } catch {
    return false;
  }
}

function labeledValue(text, label) {
  const expression = new RegExp(`^${label}[ \\t]*:[ \\t]*(.+)$`, "im");
  const match = text.match(expression);
  return match?.[1]?.trim() || null;
}

async function readFoundCount(page) {
  const text = await page.locator("body").innerText();
  const matches = [...text.matchAll(/^Found Count[ \t]*:[ \t]*([\d,]+)[ \t]*$/gim)];
  return matches.length === 1 ? Number(matches[0][1].replaceAll(",", "")) : null;
}

async function getButtons(page) {
  return page.getByRole("button", { name: /^Go Get It$/i });
}

async function startDocumentDownload(page, button) {
  await button.click();
  const filenameButton = page.locator(".fm-download-button").filter({ visible: true });
  await filenameButton.first().waitFor({ timeout: 30000 });
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 30000 }),
    (await unique(filenameButton, "download filename button")).click(),
  ]);
  await page.getByText("Close", { exact: true }).filter({ visible: true }).click();
  return download;
}

async function getNextButton(page) {
  let next = page.getByRole("button", { name: /^Next(?: Page)?$/i });
  if (await next.count() === 0) next = page.getByText("Next", { exact: true }).filter({ visible: true });
  return next;
}

async function advancePage(page) {
  const next = await getNextButton(page);
  if (await next.count()) {
    if (await next.count() !== 1) throw new Error("Ambiguous Next page control");
    if (!(await next.isEnabled())) return false;
    const before = await page.locator("body").innerText();
    await next.click();
    await page.waitForFunction(previous => document.body.innerText !== previous, before, { timeout: 10000 });
    return true;
  }
  const scroller = page.locator(".v-grid-scroller-vertical");
  if (await scroller.count() !== 1) return false;
  if (await page.locator(".v-grid-row").count() === 0) return false;
  const before = await page.locator(".v-grid-row").first().innerText();
  const moved = await scroller.evaluate(element => {
    const previous = element.scrollTop;
    element.scrollTop += element.clientHeight;
    element.dispatchEvent(new Event("scroll", { bubbles: true }));
    return element.scrollTop > previous;
  });
  if (!moved) return false;
  await page.waitForFunction(previous => document.querySelector(".v-grid-row")?.innerText !== previous,
    before, { timeout: 10000 });
  return true;
}

async function countCategory(page) {
  const foundCount = await readFoundCount(page);
  const visibleRows = await (await getButtons(page)).count();
  if (foundCount !== null) {
    if (foundCount < visibleRows) throw new Error("Found Count is smaller than visible document rows");
    return { count: foundCount, method: "found_count" };
  }
  const seen = new Set();
  let pages = 0;
  do {
    for (const row of await page.locator(".v-grid-row").all()) {
      seen.add((await row.innerText()).trim());
    }
    pages++;
    if (pages > 1000) throw new Error("Document pagination exceeded 1000 pages");
  } while (await advancePage(page));
  const total = seen.size;
  if (total === 0) {
    const text = await page.locator("body").innerText();
    if (!/\b(?:no (?:records|documents|results)|0 records)\b/i.test(text)) {
      return { count: null, method: "unavailable" };
    }
  }
  return { count: total, method: "paged_rows" };
}

async function downloadUpToTen(page, categoryCount) {
  const records = [];
  const seen = new Set();
  await mkdir(directory, { recursive: true });
  if (categoryCount === 0) {
    if (await (await getButtons(page)).count() > 0) throw new Error("Zero count conflicts with visible download controls");
    return records;
  }
  if (categoryCount !== null) await (await getButtons(page)).first().waitFor({ timeout: 30000 });
  const foundCount = await readFoundCount(page);
  if (categoryCount !== null && foundCount !== null && foundCount !== categoryCount) {
    throw new Error(`Requested category tab total ${categoryCount} differs from Found Count ${foundCount}`);
  }
  while (records.length < 10) {
    const buttons = await getButtons(page);
    const visibleCount = await buttons.count();
    for (let index = 0; index < visibleCount && records.length < 10; index++) {
      const button = buttons.nth(index);
      const row = button.locator("xpath=ancestor::*[@role='row' or self::tr][1]");
      const rowLines = await row.count()
        ? (await row.innerText()).split("\n").map(line => line.trim()).filter(Boolean) : [];
      const rowKey = rowLines.join("\n");
      if (seen.has(rowKey)) continue;
      seen.add(rowKey);
      const record = {
        site_document_id: /^\d+$/.test(rowLines[0] ?? "") ? rowLines[0] : null,
        title: rowLines[1]?.slice(0, 300) ?? null,
        date: /^\d{2}\/\d{2}\/\d{4}$/.test(rowLines[2] ?? "") ? rowLines[2] : null,
        extension: null,
        original_filename: null,
        source_url: page.url(),
        path: null,
        error_code: null,
      };
      try {
        const download = await startDocumentDownload(page, button);
        const filename = path.basename(download.suggestedFilename());
        const destination = path.join(directory, `${String(records.length + 1).padStart(2, "0")}_${filename}`);
        await download.saveAs(destination);
        if ((await stat(destination)).size === 0) throw new Error("empty_file");
        record.original_filename = filename;
        record.extension = path.extname(filename).slice(1).toLowerCase() || null;
        record.path = destination;
      } catch (error) {
        record.error_code = error.message.split("\n")[0];
      }
      records.push(record);
    }
    if (records.length >= 10 || (categoryCount !== null && records.length >= categoryCount)) break;
    if (!await advancePage(page)) break;
  }
  if (categoryCount !== null && records.length < Math.min(categoryCount, 10)) {
    throw new Error(`Only ${records.length} of ${Math.min(categoryCount, 10)} selected rows were reachable`);
  }
  if (categoryCount === null && records.length === 0) {
    throw new Error("Requested tab count and document rows are both unavailable");
  }
  return records;
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
  const headerText = await page.locator("body").innerText();
  const matterMetadata = {
    title: (await page.locator("[id*='o290i0i0']").innerText()).split("\n")[0].trim()
      || labeledValue(headerText, "Matter (?:Title|Name)") || labeledValue(headerText, "Title"),
    matter_type: (await page.locator(".fm_object_298 .text").innerText()).trim()
      || labeledValue(headerText, "(?:Matter )?Type"),
    category: (await page.locator(".fm_object_287 .text").innerText()).trim()
      || labeledValue(headerText, "Category"),
    initial_filing_date: (await page.locator(".fm_object_292 .text").innerText()).trim()
      || labeledValue(headerText, "Initial Filing(?: Date)?")
      || labeledValue(headerText, "Date Received"),
    final_filing_date: (await page.locator(".fm_object_294 .text").innerText()).trim() || null,
  };
  const counts = {};
  const countMethod = {};
  for (const category of CATEGORIES) {
    const tab = await categoryTab(page, category);
    const tabTotal = await readTabTotal(tab, category);
    const transitioned = tabTotal === null ? await openCategory(page, category, tab) : false;
    const measured = tabTotal !== null
      ? { count: tabTotal, method: "tab_total" }
      : transitioned ? await countCategory(page) : { count: null, method: "unavailable" };
    counts[category] = measured.count;
    countMethod[category] = measured.method;
  }
  if (Object.values(countMethod).some(method => method === "paged_rows" || method === "found_count")) {
    await openMatter(page);
  }
  let documents = [];
  if (counts[requested] !== 0) {
    if (!await openCategory(page, requested)) throw new Error("Requested tab did not confirm navigation");
    documents = await downloadUpToTen(page, counts[requested]);
  }
  const result = {
    matter_number: matter,
    requested_type: requested,
    ...matterMetadata,
    counts,
    count_method: countMethod,
    documents,
  };
  if (output) {
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, JSON.stringify(result, null, 2));
  } else {
    console.log(JSON.stringify(result, null, 2));
  }
} catch (error) {
  console.error(`UARB retrieval failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
}
