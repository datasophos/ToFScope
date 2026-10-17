"""Known-depth editing keeps all plot selections in acquisition frames."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
def changed(app,revision):expect(app).not_to_have_attribute('data-revision',revision,timeout=30000);ready(app)
def point(gd,x):return gd.evaluate('(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;return {x:r.left+a._offset+a.d2p(x),y:r.top+b._offset+b._length/2}}',x)

with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        app.get_by_role('button',name='Calibrate depth',exact=True).click()
        dialog=app.get_by_role('dialog',name='Known depths',exact=True)
        for frame,depth in [(300,250),(100,50)]:
            dialog.get_by_label('Anchor frame',exact=True).fill(str(frame));dialog.get_by_label('Known depth',exact=True).fill(str(depth))
            revision=app.get_attribute('data-revision');dialog.get_by_role('button',name='Add anchor',exact=True).click();changed(app,revision)
        expect(dialog.locator('[data-anchor-frame]')).to_have_count(3)
        expect(dialog.locator('[data-anchor-frame="0"]')).to_contain_text('Fixed')
        dialog.get_by_label('Known depth',exact=True).fill('100')
        revision=app.get_attribute('data-revision');dialog.get_by_label('Depth display unit',exact=True).select_option('µm');changed(app,revision)
        assert float(dialog.get_by_label('Known depth',exact=True).input_value())==.1
        dialog.get_by_label('Depth at frame 100',exact=True).fill('.06')
        revision=app.get_attribute('data-revision');dialog.get_by_label('Profile coordinates',exact=True).select_option('depth');changed(app,revision)
        assert float(dialog.get_by_label('Depth at frame 100',exact=True).input_value())==.06
        dialog.get_by_role('button',name='Done',exact=True).click()
        gd=app.locator('[data-plot="profile"]');expect(gd.locator('.xtitle')).to_have_text('Depth (µm)',timeout=10000)
        a=point(gd,.025);c=point(gd,.150);revision=app.get_attribute('data-revision')
        page.mouse.move(a['x'],a['y']);page.mouse.down();page.mouse.move(c['x'],c['y'],steps=15);page.mouse.up();changed(app,revision)
        assert json.loads(app.get_attribute('data-depth-window'))==[50,200],app.get_attribute('data-depth-window')
        expect(app.locator('[data-plot="ion"] .gtitle')).to_contain_text('frames 50–200')
        with page.expect_download() as d:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        settings=json.loads(Path(d.value.path()).read_text());assert settings['depth_calibration']['unit']=='µm'
        app.locator('[data-display="profile"] .tof-maximize').click()
        app.get_by_role('button',name='Calibrate depth',exact=True).click()
        for frame in [100,300]:
            revision=app.get_attribute('data-revision');dialog.locator(f'[data-anchor-frame="{frame}"]').get_by_role('button',name='Remove anchor',exact=True).click();changed(app,revision)
        expect(dialog.get_by_label('Profile coordinates',exact=True)).to_have_value('frame')
        dialog.get_by_role('button',name='Done',exact=True).click();expect(gd.locator('.xtitle')).to_have_text('Depth frame')
        page.keyboard.press('Escape');revision=app.get_attribute('data-revision')
        app.get_by_role('button',name='All depths',exact=True).click();changed(app,revision)
        assert app.get_attribute('data-depth-window')=='null'
        assert not errors,errors
        print('PASS: fixed zero anchor, unsorted anchors, units, depth selection→frames, exports, maximize/removal, and All depths',flush=True)
    finally:b.close()
