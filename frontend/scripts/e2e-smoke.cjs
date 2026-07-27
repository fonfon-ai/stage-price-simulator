// Manual E2E smoke script (not part of the automated test suite).
// Requires: backend running (uvicorn app.main:app) and `npm run dev` for this frontend,
// with the E2E_BASE_URL env var pointing at whatever port Vite actually bound to.
const { chromium } = require("playwright");

const BASE = process.env.E2E_BASE_URL || "http://localhost:5173";
const results = [];
const log = (msg) => {
  console.log(msg);
  results.push(msg);
};

async function fillStep1(page) {
  await page.fill('label:has-text("団体名") input', "テスト劇団E2E");
  await page.selectOption('label:has-text("ジャンル") select', "play");
  await page.fill('label:has-text("活動年数") input', "6");
  await page.fill('label:has-text("Xフォロワー数") input', "3000");
  await page.fill('label:has-text("Instagramフォロワー数") input', "1500");
}

async function fillStep2(page) {
  // 1件目
  const cards = () => page.locator(".performance-card");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "公演名")]/input', "公演A");
  await page.fill('(//div[@class="performance-card"])[1]//input[@type="date"]', "2025-06-01");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "キャパ")]/input', "200");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "チケット価格")]/input', "3500");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "販売枚数")]/input', "180");

  await page.click('button:has-text("+ 過去公演を追加")');
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "公演名")]/input', "公演B");
  await page.fill('(//div[@class="performance-card"])[2]//input[@type="date"]', "2025-02-01");
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "キャパ")]/input', "150");
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "チケット価格")]/input', "3300");
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "販売枚数")]/input', "120");

  await page.click('button:has-text("+ 過去公演を追加")');
  await page.fill('(//div[@class="performance-card"])[3]//label[contains(., "公演名")]/input', "公演C");
  await page.fill('(//div[@class="performance-card"])[3]//input[@type="date"]', "2024-10-01");
  await page.fill('(//div[@class="performance-card"])[3]//label[contains(., "キャパ")]/input', "100");
  await page.fill('(//div[@class="performance-card"])[3]//label[contains(., "チケット価格")]/input', "3000");
  await page.fill('(//div[@class="performance-card"])[3]//label[contains(., "販売枚数")]/input', "100");
  void cards;
}

async function fillStep3(page) {
  await page.fill('label:has-text("開催地域") input', "東京都");
  await page.fill('label:has-text("希望価格下限") input', "3000");
  await page.fill('label:has-text("希望価格上限") input', "4500");
}

async function fillStep4(page) {
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "会場名")]/input', "会場X");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "キャパ")]/input', "250");
  await page.fill('(//div[@class="performance-card"])[1]//label[contains(., "会場費")]/input', "300000");

  await page.click('button:has-text("+ 候補会場を追加")');
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "会場名")]/input', "会場Y");
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "キャパ")]/input', "400");
  await page.fill('(//div[@class="performance-card"])[2]//label[contains(., "会場費")]/input', "500000");
}

async function run() {
  const browser = await chromium.launch();

  // --- Desktop pass ---
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push("pageerror: " + err.message));

  await page.goto(BASE, { waitUntil: "networkidle" });
  log("STEP1 loaded: " + (await page.title()));

  await fillStep1(page);
  await page.screenshot({ path: "e2e_shots/step1_desktop.png" });
  await page.click('button:has-text("次へ")');
  await page.waitForSelector('h2:has-text("STEP 2")');
  log("Reached STEP2");

  await fillStep2(page);
  await page.screenshot({ path: "e2e_shots/step2_desktop.png" });
  await page.click('button:has-text("次へ")');
  await page.waitForSelector('h2:has-text("STEP 3")');
  log("Reached STEP3");

  await fillStep3(page);
  await page.screenshot({ path: "e2e_shots/step3_desktop.png" });
  await page.click('button:has-text("次へ")');
  await page.waitForSelector('h2:has-text("STEP 4")');
  log("Reached STEP4");

  await fillStep4(page);
  await page.screenshot({ path: "e2e_shots/step4_desktop.png" });
  await page.click('button:has-text("シミュレーション実行")');

  try {
    await page.waitForSelector('h2:has-text("STEP 5")', { timeout: 15000 });
    log("Reached STEP5 (results)");
  } catch (e) {
    const errText = await page.locator(".error-message").textContent().catch(() => null);
    log("FAILED to reach STEP5. error-message on page: " + errText);
    await page.screenshot({ path: "e2e_shots/step4_failure.png" });
    throw e;
  }

  await page.screenshot({ path: "e2e_shots/step5_desktop_top.png" });

  // Check key elements
  const checks = [
    ["推奨価格帯", 'text=推奨価格帯'],
    ["バランス価格", 'text=バランス価格'],
    ["満席重視価格", 'text=満席重視価格'],
    ["売上重視価格", 'text=売上重視価格'],
    ["利益重視価格", 'text=利益重視価格'],
    ["Venue Fit見出し", 'text=Venue Fit'],
    ["シナリオ比較表見出し", 'text=シナリオ比較表'],
    ["説明可能性見出し", 'text=なぜこの結果になったか'],
    ["免責文言", 'text=参考値です'],
  ];
  for (const [labelName, selector] of checks) {
    const count = await page.locator(selector).count();
    log(`要素チェック [${labelName}]: ${count > 0 ? "OK" : "NG (見つからない)"}`);
  }

  const tableRows = await page.locator("table tbody tr").count();
  log(`シナリオ比較表の行数: ${tableRows}`);

  const chartSvgs = await page.locator(".chart-wrapper svg").count();
  log(`グラフ(svg)の数: ${chartSvgs}`);

  await page.screenshot({ path: "e2e_shots/step5_desktop_full.png", fullPage: true });

  // scroll to see table/chart
  await page.locator("text=シナリオ比較表").scrollIntoViewIfNeeded();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "e2e_shots/step5_desktop_table.png" });

  // Actual result registration
  await page.locator("text=実績登録").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "e2e_shots/actual_result_form.png" });
  await page.fill('label:has-text("実際の販売枚数") input', "230");
  await page.click('button:has-text("実績を登録する")');
  await page.waitForSelector("text=実績を登録しました", { timeout: 10000 });
  log("実績登録: OK");
  await page.screenshot({ path: "e2e_shots/actual_result_submitted.png" });

  // Reload mid-flow (on step5) check for broken state
  await page.reload({ waitUntil: "networkidle" });
  const afterReloadStepTitle = await page.locator("h2").first().textContent();
  log("リロード後の表示: " + afterReloadStepTitle);
  await page.screenshot({ path: "e2e_shots/after_reload.png" });

  log("Console errors (desktop pass): " + JSON.stringify(consoleErrors));

  await context.close();

  // --- Mobile pass ---
  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobileContext.newPage();
  const mobileErrors = [];
  mobilePage.on("console", (msg) => {
    if (msg.type() === "error") mobileErrors.push(msg.text());
  });
  mobilePage.on("pageerror", (err) => mobileErrors.push("pageerror: " + err.message));

  await mobilePage.goto(BASE, { waitUntil: "networkidle" });
  await fillStep1(mobilePage);
  await mobilePage.screenshot({ path: "e2e_shots/step1_mobile.png" });
  await mobilePage.click('button:has-text("次へ")');
  await mobilePage.waitForSelector('h2:has-text("STEP 2")');

  await fillStep2(mobilePage);
  await mobilePage.click('button:has-text("次へ")');
  await mobilePage.waitForSelector('h2:has-text("STEP 3")');

  await fillStep3(mobilePage);
  await mobilePage.click('button:has-text("次へ")');
  await mobilePage.waitForSelector('h2:has-text("STEP 4")');

  await fillStep4(mobilePage);
  await mobilePage.screenshot({ path: "e2e_shots/step4_mobile.png" });
  await mobilePage.click('button:has-text("シミュレーション実行")');
  await mobilePage.waitForSelector('h2:has-text("STEP 5")', { timeout: 15000 });
  await mobilePage.screenshot({ path: "e2e_shots/step5_mobile_top.png" });
  await mobilePage.locator("text=シナリオ比較表").scrollIntoViewIfNeeded();
  await mobilePage.screenshot({ path: "e2e_shots/step5_mobile_table.png" });

  log("Mobile pass reached STEP5 successfully");
  log("Console errors (mobile pass): " + JSON.stringify(mobileErrors));

  await mobileContext.close();
  await browser.close();
}

run()
  .then(() => {
    console.log("=== E2E COMPLETE ===");
    process.exit(0);
  })
  .catch((e) => {
    console.error("=== E2E FAILED ===", e);
    process.exit(1);
  });
