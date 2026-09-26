const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  
  const videoDir = '/config/.gemini/antigravity/brain/77c2124b-24fb-4801-8cee-2b2386a424ef/scratch/video_lofi_raw';
  if (!fs.existsSync(videoDir)) {
    fs.mkdirSync(videoDir, { recursive: true });
  }

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: {
      dir: videoDir,
      size: { width: 1280, height: 720 }
    }
  });

  const page = await context.newPage();
  console.log('Navigating to app...');
  await page.goto('https://smart-pantry-frontend-689300279768.us-east1.run.app', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // --- Start Web Audio Upbeat Lo-Fi Background Music ---
  console.log('Starting upbeat lo-fi Web Audio background music...');
  await page.evaluate(() => {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    
    const master = ctx.createGain();
    master.gain.value = 0.25;
    master.connect(ctx.destination);
    
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 1300;
    filter.connect(master);
    
    const bpm = 88;
    const stepTime = (60 / bpm / 4) * 1000;
    
    const chords = [
      [261.63, 329.63, 392.00, 493.88], // Cmaj7
      [220.00, 261.63, 329.63, 392.00], // Am7
      [293.66, 349.23, 440.00, 523.25], // Dm7
      [196.00, 246.94, 293.66, 349.23]  // G7
    ];
    
    let step = 0;
    setInterval(() => {
      const time = ctx.currentTime;
      const measure = Math.floor(step / 16);
      const chord = chords[measure % chords.length];
      
      // Warm Rhodes Synth Chord
      if (step % 8 === 0) {
        chord.forEach(freq => {
          const osc = ctx.createOscillator();
          const g = ctx.createGain();
          osc.type = 'triangle';
          osc.frequency.value = freq;
          g.gain.setValueAtTime(0.08, time);
          g.gain.exponentialRampToValueAtTime(0.001, time + 1.2);
          osc.connect(g);
          g.connect(filter);
          osc.start(time);
          osc.stop(time + 1.2);
        });
      }
      
      // Kick drum
      if (step % 16 === 0 || step % 16 === 10) {
        const kOsc = ctx.createOscillator();
        const kGain = ctx.createGain();
        kOsc.frequency.setValueAtTime(110, time);
        kOsc.frequency.exponentialRampToValueAtTime(35, time + 0.15);
        kGain.gain.setValueAtTime(0.4, time);
        kGain.gain.exponentialRampToValueAtTime(0.001, time + 0.15);
        kOsc.connect(kGain);
        kGain.connect(master);
        kOsc.start(time);
        kOsc.stop(time + 0.15);
      }
      
      // Snare / Rimshot
      if (step % 16 === 4 || step % 16 === 12) {
        const bufferSize = Math.floor(ctx.sampleRate * 0.08);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const nGain = ctx.createGain();
        nGain.gain.setValueAtTime(0.2, time);
        nGain.gain.exponentialRampToValueAtTime(0.001, time + 0.08);
        noise.connect(nGain);
        nGain.connect(filter);
        noise.start(time);
      }
      
      // Hi-hat
      if (step % 2 === 1) {
        const bufferSize = Math.floor(ctx.sampleRate * 0.02);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        const hat = ctx.createBufferSource();
        hat.buffer = buffer;
        const hGain = ctx.createGain();
        hGain.gain.setValueAtTime(0.04, time);
        hGain.gain.exponentialRampToValueAtTime(0.001, time + 0.02);
        hat.connect(hGain);
        hGain.connect(master);
        hat.start(time);
      }
      
      step++;
    }, stepTime);
  });

  await page.waitForTimeout(2000);

  // Helper for typing text with realistic delay
  async function typeAndSend(text) {
    console.log(`Typing prompt: ${text}`);
    const input = page.locator('#input');
    await input.click();
    await input.type(text, { delay: 40 });
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

  // --- Prompt 2: Richer prompt with Tool Call & Image Generation / Plating ---
  await typeAndSend('Show me a plated dish visualization for Mediterranean grilled salmon');
  
  console.log('Waiting for Agent response to prompt 2...');
  await page.waitForFunction(() => {
    const msgs = document.querySelectorAll('.msg.agent');
    return msgs.length >= 2 && !msgs[msgs.length - 1].textContent.includes('…');
  }, { timeout: 60000 });

  await page.waitForTimeout(6000);

  console.log('Closing browser to save video...');
  await context.close();
  await browser.close();

  // Save video file
  const videoFiles = fs.readdirSync(videoDir).filter(f => f.endsWith('.webm'));
  if (videoFiles.length > 0) {
    const srcPath = path.join(videoDir, videoFiles[0]);
    const destPath = '/config/.gemini/antigravity/brain/77c2124b-24fb-4801-8cee-2b2386a424ef/demo.webm';
    fs.copyFileSync(srcPath, destPath);
    console.log(`Video with upbeat lo-fi audio successfully recorded and saved to: ${destPath}`);
  } else {
    console.error('No video file found in recording directory!');
  }
})();
