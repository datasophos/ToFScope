"""Exercise multiple mass windows and the simultaneous image/spectrum/profile view."""
import csv
import io
import math
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def ready(app):
    expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=60000)


def changed(app, before):
    expect(app).not_to_have_attribute('data-revision',before,timeout=60000)
    ready(app)


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1660,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app');ready(app)
        ion=app.locator('[data-plot="ion"]');front=app.locator('[data-plot="front"]')
        spectrum=app.locator('[data-plot="spectrum"]');profile=app.locator('[data-plot="profile"]')
        for plot in [ion,front,spectrum,profile]: expect(plot).to_be_visible()
        assert ion.bounding_box()['x'] < spectrum.bounding_box()['x']
        assert spectrum.bounding_box()['y'] < profile.bounding_box()['y']
        assert 'Top projection' in ion.evaluate('g=>g.layout.title.text')
        assert 'sum Y' in front.evaluate('g=>g.layout.title.text')
        print('PASS: top/front SIMS projections left; spectrum and depth profile right',flush=True)
        app.get_by_role('button',name='FIB SE image',exact=True).click()
        se=app.locator('[data-plot="se"]');expect(se).to_be_visible();expect(ion).to_be_hidden()
        expect(spectrum).to_be_visible();expect(profile).to_be_visible()
        app.get_by_role('button',name='SIMS images',exact=True).click();expect(ion).to_be_visible()
        print('PASS: FIB SE toggle preserves the simultaneous analysis plots',flush=True)

        picker=app.locator('[data-picker="comparison"]')
        for count,mass in enumerate(['28','48','193.95','16','69'],1):
            before=app.get_attribute('data-revision')
            picker.get_by_role('button',name='Add comparison channel',exact=True).click()
            picker.get_by_role('combobox').fill(mass)
            picker.get_by_role('option').first.click();changed(app,before)
            expect(app.locator('.tof-comparison-row')).to_have_count(count)
            assert profile.evaluate('g=>g.data.length')==count+1
        traces=profile.evaluate('g=>g.data.map(t=>({name:t.name,color:t.line.color}))')
        assert len(set(t['color'] for t in traces))==6
        assert spectrum.evaluate('g=>g.layout.shapes.length')==6
        print('PASS: five independent stored comparison curves and matching spectrum bands',flush=True)
        # Removing a middle curve must not remove or replace the other selections.
        before=app.get_attribute('data-revision')
        app.locator('.tof-comparison-row').nth(2).get_by_role('button').click();changed(app,before)
        assert profile.evaluate('g=>g.data.length')==5
        expect(app.locator('[data-field="signal"]')).to_contain_text('27.0000')
        print('PASS: individual comparison removal preserves the primary signal',flush=True)

        for label,value in [('Lower mass limit','26.8'),('Upper mass limit','27.2'),('First integration frame','0'),('Last integration frame','3')]:
            if app.get_by_label(label,exact=True).input_value()==value:
                continue
            before=app.get_attribute('data-revision')
            app.get_by_label(label,exact=True).fill(value)
            app.get_by_label(label,exact=True).press('Tab');changed(app,before)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Add window to comparisons',exact=True).click();changed(app,before)
        expect(app.locator('.tof-comparison-row')).to_have_count(5)
        assert profile.evaluate('g=>g.data.length')==6
        custom=profile.evaluate('g=>({name:g.data.at(-1).name,y:Array.from(g._fullData.at(-1).y)})')
        assert custom['name'].startswith('Custom 26.8000–27.2000')
        assert len(custom['y'])==1301, (len(custom['y']),custom['y'][:8])
        assert all(v is not None and math.isfinite(v) for v in custom['y'][:4]) and all(v is None or math.isnan(v) for v in custom['y'][4:]),custom['y'][:8]
        print('PASS: custom mass comparison retains its frame range and leaves missing frames empty',flush=True)
        # Moving the spectrum into its full tab and back preserves one plot instance.
        app.get_by_role('tab',name='Mass spectrum',exact=True).click();expect(spectrum).to_be_visible()
        app.get_by_role('tab',name='Explore',exact=True).click()
        expect(spectrum).to_be_visible();expect(profile).to_be_visible()
        page.wait_for_timeout(500)
        # Drag directly on the embedded spectrum, then on the depth profile.
        def point(g,x):
            return g.evaluate('''(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
              return {x:r.left+a._offset+a.d2p(x),y:r.top+b._offset+b._length/2}}''',x)
        def drag(g,low,high):
            a,b=point(g,low),point(g,high)
            page.mouse.move(a['x'],a['y']);page.mouse.down();page.mouse.move(b['x'],b['y'],steps=12);page.mouse.up()
        before=app.get_attribute('data-revision');drag(spectrum,45,51);changed(app,before)
        assert abs(float(app.get_by_label('Lower mass limit',exact=True).input_value())-45)<.5
        before=app.get_attribute('data-revision');drag(profile,200,400);changed(app,before)
        selection=json.loads(app.get_attribute('data-depth-window'))
        assert abs(selection[0]-200)<3 and abs(selection[1]-400)<3
        assert 'Top projection' in ion.evaluate('g=>g.layout.title.text')
        app.get_by_role('button',name='FIB SE image',exact=True).click()
        expect(se).to_be_visible()
        expect(se).to_have_class(__import__('re').compile('js-plotly-plot'))
        assert 'SE mean' in se.evaluate('g=>g.layout.title.text')
        app.get_by_role('button',name='SIMS images',exact=True).click()
        print('PASS: embedded spectrum drag and depth integration update the linked SIMS/SE views',flush=True)
        with page.expect_download() as download:
            app.get_by_role('button',name='Profile CSV ↓',exact=True).click()
        rows=list(csv.reader(io.StringIO(Path(download.value.path()).read_text())))
        assert len(rows[0])==7 and len(rows)==selection[1]-selection[0]+2
        assert rows[1][-1]==''  # custom frames 0–3 do not overlap selected depth
        print('PASS: CSV includes every comparison, with empty cells outside its coverage',flush=True)
        # Same mass window with different one-frame coverages must remain visible and distinct.
        for changes in [[('First integration frame','0'),('Last integration frame','0')],
                        [('Last integration frame','1'),('First integration frame','1')]]:
            for label,value in changes:
                before=app.get_attribute('data-revision')
                app.get_by_label(label,exact=True).fill(value)
                app.get_by_label(label,exact=True).press('Tab');changed(app,before)
            before=app.get_attribute('data-revision')
            app.get_by_role('button',name='Add window to comparisons',exact=True).click();changed(app,before)
        points=profile.evaluate('g=>g.data.slice(-2).map(t=>({name:t.name,mode:t.mode}))')
        assert points[0]['name']!=points[1]['name']
        assert all('markers' in t['mode'] for t in points)
        assert profile.locator('.points .point').count()>=2
        print('PASS: single-frame windows have visible markers and unique frame-specific names',flush=True)
        page.screenshot(path='/private/tmp/tofscope-comparisons-layout.png')
        for width,height in [(1440,900),(1280,900)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(800)
            for g in [ion,front,spectrum,profile]:
                expect(g).to_be_visible();assert g.bounding_box()['height']>180
        assert not errors,errors
        print('PASS: desktop layouts and no browser errors',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-comparisons-failure.png');print(errors,flush=True);raise
    finally:browser.close()
