const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 }
  });
  const page = await context.newPage();

  const framesDir = '/tmp/gif_frames';
  if (fs.existsSync(framesDir)) {
    fs.rmSync(framesDir, { recursive: true, force: true });
  }
  fs.mkdirSync(framesDir, { recursive: true });

  let frameCount = 0;
  let active = true;

  // Frame capture timer: 300ms (3.3 fps)
  const captureLoop = setInterval(async () => {
    if (!active) return;
    try {
      frameCount++;
      const num = String(frameCount).padStart(4, '0');
      await page.screenshot({ path: `${framesDir}/frame_${num}.png` });
    } catch (e) {
      // Ignore transient screenshot errors during page transitions
    }
  }, 300);

  console.log('Navigating to app...');
  await page.goto('https://smart-pantry-frontend-689300279768.us-east1.run.app', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  async function typeAndSend(text) {
    console.log(`Typing prompt: ${text}`);
    const input = page.locator('#input');
    await input.click();
    await input.type(text, { delay: 30 });
    await page.waitForTimeout(500);
    await page.click('form button');
  }

  // --- Prompt 1: Core Recipe & Pantry Search ---
  await typeAndSend('What can I cook with eggs, spinach, and garlic?');
  
  console.log('Waiting for Agent response to prompt 1...');
  await page.waitForFunction(() => {
    const msgs = document.querySelectorAll('.msg.agent');
    return msgs.length >= 1 && !msgs[msgs.length - 1].textContent.includes('…');
  }, { timeout: 45000 });
  
  await page.waitForTimeout(4000);

  // --- Prompt 2: Richer prompt with Tool Call & Image Generation ---
  await typeAndSend('Show me a plated dish visualization for Mediterranean grilled salmon');
  
  console.log('Waiting for Agent response to prompt 2...');
  await page.waitForFunction(() => {
    const msgs = document.querySelectorAll('.msg.agent');
    return msgs.length >= 2 && !msgs[msgs.length - 1].textContent.includes('…');
  }, { timeout: 60000 });

  await page.waitForTimeout(6000);

  active = false;
  clearInterval(captureLoop);

  console.log(`Captured ${frameCount} clean screenshot frames!`);
  await browser.close();
})();
