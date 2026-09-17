// Optional browser regression: ATMEM_PLAYWRIGHT_MODULE=/path/to/playwright node tools/check_archive_layout.cjs
// Synthetic evidence only; no live database, credentials or running dashboard.
const {chromium} = require(process.env.ATMEM_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const css = fs.readFileSync(path.join(root, 'atmem/control/assets/app.css'), 'utf8');
  const shell = fs.readFileSync(path.join(root, 'atmem/control/assets/app.html'), 'utf8');
  const archive = shell.split('<section class="card" id="blackboxArchiveCard">')[1].split('<section class="card" id="mirrorCard">')[0];
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage();
    for (const width of [2048, 1280, 900, 390]) {
      await page.setViewportSize({width, height: 1000});
      await page.setContent(`<html data-theme="dark"><style>${css}</style><main class="wrap"><div id="viewStatus" class="tabpanel active auditor-open detail-archive"><section id="blackboxArchiveCard" class="card">${archive}</div></main></html>`);
      await page.evaluate(() => {
        const pane = document.getElementById('auditorBackdrop');
        pane.classList.add('show');
        document.getElementById('viewStatus').appendChild(pane);
        document.getElementById('auditorTitle').textContent = 'Run outcome and evidence';
        document.getElementById('auditorBody').textContent = 'Synthetic retained evidence for layout testing.';
        document.getElementById('blackboxFlights').innerHTML = `<article class="flight review selected">
          <div class="flightidentity"><div class="flightidentitytop"><span class="flightstatus">Evidence note</span><time class="flighttimestamp">13 Sept 2026, 15:27:52.351 GMT+10</time></div>
          <b class="mono">run-with-a-long-identifier-to-test-overflow-and-truncation</b><div class="small mono">agent main · agent:main:atmem-local-deploy-e2e-20260913-retry</div></div>
          <div class="flightstat"><b>incomplete evidence</b><small>verdict</small></div>
          <div class="flightstat"><b>not observed</b><small>provider / model</small></div>
          <div class="flightstat"><b>missing</b><small>memory context</small></div>
          <button class="secondary">Inspect evidence</button></article>`;
      });
      const result = await page.evaluate(() => {
        const rect = e => e.getBoundingClientRect();
        const card = document.querySelector('.flight');
        const filter = document.querySelector('.flightfilters');
        const contained = (parent, children) => [...children].every(e => {
          const a = rect(parent), b = rect(e);
          return b.left >= a.left - 1 && b.right <= a.right + 1;
        });
        const children = [...card.children].filter(e => rect(e).height);
        const overlap = children.some((a, i) => children.slice(i + 1).some(b => {
          const ar = rect(a), br = rect(b);
          return Math.min(ar.right, br.right) > Math.max(ar.left, br.left) + 1 && Math.min(ar.bottom, br.bottom) > Math.max(ar.top, br.top) + 1;
        }));
        return {width: innerWidth, cardHeight: rect(card).height,
          cardContained: contained(card, children), filtersContained: contained(filter, filter.children), overlap,
          pageOverflow: document.documentElement.scrollWidth > innerWidth};
      });
      console.log(result);
      assert.equal(result.cardContained, true);
      assert.equal(result.filtersContained, true);
      assert.equal(result.overlap, false);
      assert.equal(result.pageOverflow, false);
      assert.ok(result.cardHeight < 420);
      if (width === 1280 && process.env.ATMEM_LAYOUT_SCREENSHOT) {
        await page.evaluate(() => document.getAnimations().forEach(animation => {
            if (animation.effect?.getComputedTiming().endTime === Infinity) animation.cancel();
            else animation.finish();
        }));
        await page.screenshot({path: process.env.ATMEM_LAYOUT_SCREENSHOT, fullPage: true});
      }
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
