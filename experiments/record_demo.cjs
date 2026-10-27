/* Re-capture the actual Studio UI for the editable demo. No UI data is fabricated.
   npm install --no-save playwright
   CHROME_PATH=/path/to/chrome node experiments/record_demo.cjs http://127.0.0.1:8782 docs/media/new-capture
   Original launch-v1 screenshots were captured through Codex CUA Chrome controls.
*/
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
(async()=>{
  const [url, directory] = process.argv.slice(2);
  if (!url || !directory) throw Error('Pass the local Studio URL and a new output directory');
  const parsed = new URL(url);
  if (!['127.0.0.1','localhost','[::1]'].includes(parsed.hostname)) throw Error('Use a localhost Studio URL');
  const output = path.resolve(directory);
  await fs.mkdir(output); // Deliberately refuses to overwrite an existing capture.
  const browser = await chromium.launch({headless:true, ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH}: {})});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1,reducedMotion:'reduce'});
    await page.goto(url); await page.locator('#status').waitFor();
    const capture=async name=>{await page.screenshot({path:path.join(output,name)});};
    await capture('01-overview.png');
    await page.getByLabel('Select transformation attempt').selectOption('0');
    await page.getByRole('link',{name:'01 Overview'}).click();
    await capture('02-seeded-failure-v2.png');
    await page.getByLabel('Filter function').selectOption('sum_squares');
    await page.getByRole('link',{name:'03 Counterexamples'}).click();
    await page.locator('#cases details').nth(0).locator('summary').click();
    await page.locator('#cases details').nth(1).locator('summary').click();
    await capture('03-minimized-counterexample.png');
    await page.getByLabel('Select transformation attempt').selectOption('1');
    await page.getByRole('link',{name:'02 Contract inspector'}).click();
    await page.getByRole('tab',{name:'Rust candidate'}).click();
    await page.locator('#code').evaluate(el=>{el.scrollTop=400;});
    await capture('04-repaired-rust.png');
    await page.getByRole('table',{name:'Per-function benchmark results'}).scrollIntoViewIfNeeded();
    await capture('05-benchmark.png');
  } finally {await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
