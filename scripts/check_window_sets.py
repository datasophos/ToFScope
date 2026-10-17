"""Multiple draft intervals, composite apply/comparison and full recipe export."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=60000)


def changed(app,before):
    expect(app).not_to_have_attribute('data-revision',before,timeout=60000);ready(app)


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1660,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        add=app.get_by_role('button',name='Add interval',exact=True)
        expect(add).to_be_visible(timeout=5000)
        gd=app.locator('[data-plot="spectrum"]')
        def action(button):
            before=app.get_attribute('data-revision');button.click();changed(app,before)
        def set_limits(low,high):
            # Widen upper first when moving upward, lower first when moving downward.
            old_low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
            pairs=[('Upper mass limit',high),('Lower mass limit',low)] if low>=old_low else [('Lower mass limit',low),('Upper mass limit',high)]
            for label,value in pairs:
                box=app.get_by_label(label,exact=True)
                if float(box.input_value())==value:continue
                before=app.get_attribute('data-revision');box.fill(str(value));box.press('Tab');changed(app,before)
        def bands():return gd.evaluate('g=>g.layout.shapes.filter(s=>s.name?.startsWith("draft:")).map(s=>[s.x0,s.x1])')
        set_limits(26.8,27.2)
        action(add);set_limits(47.8,48.2)
        expect(app.locator('.tof-interval-row')).to_have_count(2)
        assert sorted(bands())==[[26.8,27.2],[47.8,48.2]]
        first=app.locator('.tof-interval-row').first
        action(first.locator('[data-select-interval]'))
        set_limits(26.7,27.3)
        assert sorted(bands())==[[26.7,27.3],[47.8,48.2]]
        before_bands=sorted(bands())
        lower=app.get_by_label('Lower mass limit',exact=True)
        lower.fill('99');lower.press('Tab')
        expect(app.locator('[role="status"]')).to_contain_text('lower < upper',timeout=30000)
        assert sorted(bands())==before_bands
        expect(app.locator('[data-field="source"]')).to_have_text('STORED PEAK CHANNEL')
        print('PASS: add/select/edit and invalid-input rejection preserve the other bands and active signal',flush=True)
        # Remove only the second, then draw it again while maximized.
        action(app.locator('.tof-interval-row').nth(1).get_by_role('button',name='Remove interval',exact=True))
        expect(app.locator('.tof-interval-row')).to_have_count(1)
        action(add);set_limits(47.5,48.5)
        app.get_by_role('button',name='Zoom to window',exact=True).click();page.wait_for_timeout(200)
        app.locator('[data-display="spectrum"] .tof-maximize').click();page.wait_for_timeout(400)
        def point(x):return gd.evaluate('''(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;return {x:r.x+a._offset+a.d2p(x),y:r.y+b._offset+b._length/2}}''',x)
        a,z=point(47.8),point(48.2);before=app.get_attribute('data-revision')
        page.mouse.move(a['x'],a['y']);page.mouse.down();page.mouse.move(z['x'],z['y'],steps=15);page.mouse.up();changed(app,before)
        page.keyboard.press('Escape');page.wait_for_timeout(300)
        actual=sorted(bands());assert len(actual)==2 and abs(actual[1][0]-47.8)<.2 and abs(actual[1][1]-48.2)<.2,actual
        # Use exact limits after testing drawing.
        set_limits(47.8,48.2)
        for label,value in [('First integration frame','0'),('Last integration frame','3')]:
            field=app.get_by_label(label,exact=True)
            if field.input_value()==value:continue
            before=app.get_attribute('data-revision');field.fill(value);field.press('Tab');changed(app,before)
        action(app.get_by_role('button',name='Apply custom window',exact=True))
        expect(app.locator('[data-field="signal"]')).to_contain_text('∪')
        expected=[[26.7,27.3],[47.8,48.2]]
        with page.expect_download() as download:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        recipe=json.loads(Path(download.value.path()).read_text())
        assert recipe['schema_version']==3 and recipe['intervals']==expected,recipe
        assert 'lower_Th' not in recipe and 'upper_Th' not in recipe
        action(app.get_by_role('button',name='Add window to comparisons',exact=True))
        expect(app.locator('.tof-comparison-row')).to_have_count(1)
        expect(app.locator('.tof-comparison-row')).to_contain_text('∪')
        app.get_by_role('tab',name='3D volume',exact=True).click()
        expect(app.locator('[data-field="volume-mass"]')).to_contain_text('∪')
        expect(app.locator('[data-plot="volume"] .gtitle')).to_contain_text('∪',timeout=30000)
        app.get_by_role('tab',name='Explore',exact=True).click()
        print('PASS: a composite drives images, 3D, comparisons and complete JSON export',flush=True)
        # Delete all drafts: analysis stays applied and Apply is unavailable.
        while app.locator('.tof-interval-row').count():
            action(app.locator('.tof-interval-row').first.get_by_role('button',name='Remove interval',exact=True))
        expect(app.get_by_role('button',name='Apply custom window',exact=True)).to_be_disabled()
        expect(app.get_by_role('button',name='Add window to comparisons',exact=True)).to_be_disabled()
        expect(app.locator('[data-field="signal"]')).to_contain_text('∪')
        assert not bands()
        action(add)
        expect(app.get_by_role('button',name='Apply custom window',exact=True)).to_be_enabled()
        assert len(bands())==1
        assert not errors,errors
        page.screenshot(path='/private/tmp/tofscope-window-sets.png')
        print('PASS: empty drafts disable Apply, preserve active signal, and recover without ghost bands',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-window-sets-failure.png');print(errors,flush=True);raise
    finally:b.close()
