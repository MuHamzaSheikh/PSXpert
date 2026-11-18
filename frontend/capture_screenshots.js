import puppeteer from 'puppeteer-core';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\malik\\.gemini\\antigravity\\brain\\97199a0d-0ea1-44d0-8dad-00d8808834cf';

async function captureAll() {
  console.log('Launching Chrome...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 960, deviceScaleFactor: 1 });

  const routes = [
    { url: 'http://localhost:5173/', file: 'dashboard_desktop.png' },
    { url: 'http://localhost:5173/screener', file: 'screener_desktop.png' },
    { url: 'http://localhost:5173/analysis/MEBL', file: 'analysis_desktop.png' },
    { url: 'http://localhost:5173/portfolio', file: 'portfolio_desktop.png' },
    { url: 'http://localhost:5173/assistant', file: 'assistant_desktop.png' },
  ];

  for (const r of routes) {
    console.log(`Capturing ${r.url} -> ${r.file}...`);
    await page.goto(r.url, { waitUntil: 'networkidle0', timeout: 25000 });
    await new Promise(res => setTimeout(res, 1200));
    await page.screenshot({ path: `${ARTIFACT_DIR}\\${r.file}`, fullPage: false });
  }

  // Also capture mobile for analysis page
  console.log('Capturing mobile view for analysis...');
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await page.goto('http://localhost:5173/analysis/MEBL', { waitUntil: 'networkidle0', timeout: 25000 });
  await new Promise(res => setTimeout(res, 1200));
  await page.screenshot({ path: `${ARTIFACT_DIR}\\analysis_mobile.png`, fullPage: false });

  await browser.close();
  console.log('All screenshots captured successfully!');
}

captureAll().catch(err => {
  console.error('Capture error:', err);
  process.exit(1);
});
