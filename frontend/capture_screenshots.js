import puppeteer from 'puppeteer-core';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\malik\\.gemini\\antigravity\\brain\\97199a0d-0ea1-44d0-8dad-00d8808834cf';

async function capture() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();

  // 1. Desktop Screenshot
  console.log('Capturing Desktop Screenshot...');
  await page.setViewport({ width: 1440, height: 960, deviceScaleFactor: 1 });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle0', timeout: 20000 });
  // wait extra 1.5s for charts and animations to render smoothly
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: `${ARTIFACT_DIR}\\dashboard_desktop.png`, fullPage: false });
  console.log('Desktop screenshot saved.');

  // 2. Mobile Screenshot
  console.log('Capturing Mobile Screenshot...');
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await page.reload({ waitUntil: 'networkidle0', timeout: 20000 });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: `${ARTIFACT_DIR}\\dashboard_mobile.png`, fullPage: false });
  console.log('Mobile screenshot saved.');

  await browser.close();
  console.log('Done!');
}

capture().catch(err => {
  console.error('Capture error:', err);
  process.exit(1);
});
