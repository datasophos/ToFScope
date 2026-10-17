"""Selecting a row and applying before its reply must not overwrite another interval."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


def changed(app,before):
    expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1100})
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        before=app.get_attribute('data-revision')
        app.get_by_label('Last integration frame',exact=True).fill('1')
        app.get_by_label('Last integration frame',exact=True).press('Tab');changed(app,before)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Add interval',exact=True).click();changed(app,before)
        for label,value in [('Upper mass limit','48.2'),('Lower mass limit','47.8')]:
            before=app.get_attribute('data-revision');field=app.get_by_label(label,exact=True)
            field.fill(value);field.press('Tab');changed(app,before)
        # Both UI actions run before the interval_select response can arrive.
        first=app.locator('.tof-interval-row').first.locator('[data-select-interval]')
        first.evaluate('b=>{b.click();b.getRootNode().querySelector("[data-action=comparison-window]").click();}')
        expect(app.locator('.tof-comparison-row')).to_have_count(1,timeout=30000);ready(app)
        with page.expect_download() as download:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        exported=json.loads(Path(download.value.path()).read_text())
        assert exported['comparisons'][0]['recipe']['intervals']==[[26.5,27.5],[47.8,48.2]],exported['comparisons']
        # Repeat for the primary Apply action, starting from a different selected row.
        before=app.get_attribute('data-revision')
        app.locator('.tof-interval-row').nth(1).locator('[data-select-interval]').click();changed(app,before)
        first.evaluate('b=>{b.click();b.getRootNode().querySelector("[data-action=integrate]").click();}')
        expect(app.locator('[data-field="signal"]')).to_contain_text('∪',timeout=30000);ready(app)
        print('PASS: immediate row-select plus Add comparison/Apply retains both intervals',flush=True)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Restore stored channel',exact=True).click();changed(app,before)
        for label,value in [('Upper mass limit','27.500000456'),('Lower mass limit','26.500000123')]:
            before=app.get_attribute('data-revision');field=app.get_by_label(label,exact=True)
            field.fill(value);field.press('Tab');changed(app,before)
            assert float(field.input_value())==float(value),(value,field.input_value())
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Apply custom window',exact=True).click();changed(app,before)
        with page.expect_download() as download:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        exported=json.loads(Path(download.value.path()).read_text())
        assert exported['intervals']==[[26.500000123,27.500000456]],exported
        print('PASS: entered interval precision survives rendering and Apply/export',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-interval-race-failure.png');raise
    finally:browser.close()
