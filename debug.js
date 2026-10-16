// debug.js — capture console logs & screenshots from the billboard page
const { chromium } = require('playwright'); // Playwright's bundled Chromium
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture every console message from the page
  page.on('console', msg => {
    const type = msg.type(); // log, error, warning, info …
    const text = msg.text();
    console.log(`[PAGE ${type}] ${text}`);
  });

  // Listen for any page errors (uncaught exceptions)
  page.on('pageerror', err => {
    console.error(`[PAGE ERROR] ${err}`);
  });

  // Serve the local file via a file:// URL
  const filePath = path.resolve('templates/index.html');
  const fileUrl = `file://${filePath}`;
  console.log(`Opening ${fileUrl}`);

  await page.goto(fileUrl, { waitUntil: 'load' });

  // Give the page a few seconds to run its timers & animations
  await page.waitForTimeout(4000);

  // --- Capture screenshots of key UI sections ---
  // 1. Whole viewport (slides)
  await page.screenshot({ path: 'slide_view.png', fullPage: true });
  console.log('Saved slide_view.png');

  // 2. Meter (liquid) element – try to locate by class/id
  const meter = await page.$('.liquid-meter, .meter, #liquid-meter'); // adjust selector if needed
  if (meter) {
    await meter.screenshot({ path: 'meter_view.png' });
    console.log('Saved meter_view.png');
  } else {
    console.warn('Meter element not found – selector may be wrong');
  }

  // 3. Mint icon – guess a class name like .mint-icon
  const mint = await page.$('.mint, .mint-icon, #mint');
  if (mint) {
    await mint.screenshot({ path: 'mint_view.png' });
    console.log('Saved mint_view.png');
  } else {
    console.warn('Mint element not found – selector may be wrong');
  }

  // 4. Banner area – look for .banner
  const banner = await page.$('.banner');
  if (banner) {
    await banner.screenshot({ path: 'banner_view.png' });
    console.log('Saved banner_view.png');
  }

  await browser.close();
})();
