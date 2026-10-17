"""Atomic suggestions are offline and never silently replace source labels."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader']);page=b.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        original=app.locator('[data-field="signal"]').inner_text()
        app.get_by_role('button',name='Identify atomic ions',exact=True).click()
        dialog=app.get_by_role('dialog',name='Atomic-ion helper',exact=True)
        dialog.get_by_label('Measured mass',exact=True).fill('26.981')
        dialog.get_by_label('Mass tolerance',exact=True).fill('.01')
        dialog.get_by_role('button',name='Find candidates',exact=True).click()
        al=dialog.locator('[data-candidate="Al-27:+1"]');expect(al).to_be_visible(timeout=10000)
        expect(dialog.locator('[data-candidate]')).not_to_have_count(0)
        al.get_by_role('button',name='Select',exact=True).click()
        dialog.get_by_role('button',name='Annotate signal',exact=True).click();ready(app)
        expect(app.locator('[data-field="signal"]')).to_have_text(original)
        dialog.get_by_label('Ion polarity',exact=True).select_option('-1')
        dialog.get_by_role('button',name='Find candidates',exact=True).click()
        expect(dialog.locator('[data-candidate="Al-27:-1"]')).to_be_visible(timeout=10000)
        dialog.get_by_role('button',name='Done',exact=True).click()
        app.get_by_role('tab',name='Isotopes',exact=True).click()
        app.get_by_role('button',name='Measure selected signals',exact=True).click()
        expect(app.locator('[data-measurement-row]')).to_have_count(1,timeout=30000);ready(app)
        expect(app.locator('[data-measurement-row]')).to_contain_text('Al-27:+1')
        with page.expect_download() as d:app.get_by_role('button',name='Isotope CSV ↓',exact=True).click()
        text=Path(d.value.path()).read_text();assert 'observed_selected_set_fraction' in text and 'reference_abundance_low' in text
        with page.expect_download() as d:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        data=json.loads(Path(d.value.path()).read_text());assert data['assignments'] and data['abundance_context']['frames']==[0,1300]
        assert not errors,errors
        print('PASS: atomic candidates, polarity, explicit annotation without relabeling, explicit measurement, and attributed exports',flush=True)
    finally:b.close()
