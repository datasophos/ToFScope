"""Exercise plot-driven navigation in the running local workspace.

Start Marimo on port 2718, then: uv run python scripts/check_browser.py
Uses the installed Google Chrome browser.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def point(gd, x, y=None):
    return gd.evaluate('''(gd, coords) => {
      const r=gd.getBoundingClientRect(), xa=gd._fullLayout.xaxis, ya=gd._fullLayout.yaxis;
      return {x:r.left+xa._offset+xa.d2p(coords[0]),
        y:r.top+ya._offset+(coords[1]===null?ya._length/2:ya.d2p(coords[1]))};
    }''',[x,y])


def ready(app):
    expect(app.locator('[data-field="status"]')).to_have_text('Ready',timeout=60000)


def drag(page,start,end):
    page.mouse.move(start['x'],start['y'])
    page.mouse.down()
    page.mouse.move(end['x'],end['y'],steps=12)
    page.mouse.up()


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1100})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app')
        app.wait_for(timeout=30000)
        ready(app)
        expect(app.get_by_role('tab')).to_have_count(4)
        expect(page.locator('input[type="range"]')).to_have_count(0)
        print('PASS: tabbed workspace with no sliders',flush=True)

        profile=app.locator('[data-plot="profile"]')
        pos=point(profile,400)
        page.mouse.click(pos['x'],pos['y'])
        expect(app).not_to_have_attribute('data-frame','0',timeout=30000)
        ready(app)
        assert abs(int(app.get_attribute('data-frame'))-400)<=2
        previous_frame=app.get_attribute('data-frame')
        drag(page,point(profile,400),point(profile,700))
        expect(app).not_to_have_attribute('data-frame',previous_frame,timeout=30000)
        ready(app)
        assert abs(int(app.get_attribute('data-frame'))-700)<=2
        depth_window=json.loads(app.get_attribute('data-depth-window'))
        assert abs(depth_window[0]-400)<=2 and abs(depth_window[1]-700)<=2
        print('PASS: click selects a frame; drag selects a depth window',flush=True)

        ion=app.locator('[data-plot="ion"]')
        drag(page,point(ion,2,4),point(ion,6,8))
        expect(app).not_to_have_attribute('data-roi','[0,127,0,127]',timeout=30000)
        ready(app)
        roi=json.loads(app.get_attribute('data-roi'))
        assert all(abs(a-b)<=1 for a,b in zip(roi,[13,37,26,50])),roi
        print('PASS: drawing on ion map updates spatial ROI',flush=True)

        previous_roi=app.get_attribute('data-roi')
        shape=ion.evaluate('(gd)=>gd.layout.shapes.at(-1)')
        corner=point(ion,shape['x1'],shape['y1'])
        page.mouse.click(corner['x'],corner['y'])
        page.wait_for_timeout(200)
        drag(page,point(ion,shape['x1'],shape['y1']),point(ion,8,10))
        expect(app).not_to_have_attribute('data-roi',previous_roi,timeout=30000)
        ready(app)
        edited=json.loads(app.get_attribute('data-roi'))
        assert all(abs(a-b)<=1 for a,b in zip(edited,[13,50,26,63])),edited
        print('PASS: resizing the existing ROI updates shared limits',flush=True)

        app.get_by_role('tab',name='Mass spectrum',exact=True).click()
        spectrum=app.locator('[data-plot="spectrum"]')
        # Ensure lazy tab rendering is complete before translating coordinates.
        deadline=time.monotonic()+30
        while not spectrum.evaluate('(gd)=>!!gd._fullLayout?.xaxis'):
            assert time.monotonic()<deadline
            page.wait_for_timeout(100)
        app.get_by_role('button',name='Zoom to window',exact=True).click()
        page.wait_for_timeout(200)
        yrange=spectrum.evaluate('(gd)=>gd._fullLayout.yaxis.range')
        # Plotly's logarithmic d2p expects the original data value.
        y=10**((yrange[0]+yrange[1])/2)
        drag(page,point(spectrum,26.8,y),point(spectrum,27.2,y*2))
        expect(app.locator('[data-field="draft-tag"]')).to_have_text('DRAFT',timeout=30000)
        ready(app)
        low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        assert abs(low-26.8)<.03 and abs(high-27.2)<.03,(low,high)
        expect(app.locator('[data-field="source"]')).to_have_text('STORED PEAK CHANNEL')
        print('PASS: drawn spectrum interval stages an unapplied mass window',flush=True)

        app.get_by_label('First integration frame',exact=True).fill('0')
        app.get_by_label('Last integration frame',exact=True).fill('3')
        app.get_by_role('button',name='Apply custom window',exact=True).click()
        expect(app.locator('[data-field="source"]')).to_have_text('RECONSTRUCTED RAW EVENTS',timeout=30000)
        ready(app)
        expect(app).to_have_attribute('data-frame','3')
        print('PASS: custom integration uses drawn mass window',flush=True)

        app.get_by_role('tab',name='Cross-sections',exact=True).click()
        expect(app.get_by_role('tabpanel',name='Cross-sections',exact=True)).to_be_visible()
        app.get_by_role('tab',name='3D volume',exact=True).click()
        expect(app.get_by_role('tabpanel',name='3D volume',exact=True)).to_be_visible()
        page.wait_for_timeout(1200)
        page.screenshot(path='/private/tmp/tof-workspace-volume.png')
        print('PASS: cross-section and 3D tabs',flush=True)

        with page.expect_download() as download:
            app.get_by_role('button',name='Profile CSV ↓',exact=True).click()
        csv=Path(download.value.path()).read_text()
        assert len(csv.strip().splitlines())==5
        with page.expect_download() as download:
            app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
        recipe=json.loads(Path(download.value.path()).read_text())
        assert recipe['source']=='custom'
        assert recipe['frames_inclusive']==[0,3]
        assert not errors,errors
        print('PASS: exports and no browser errors',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tof-workspace-failure.png')
        print('Failure screenshot: /private/tmp/tof-workspace-failure.png',flush=True)
        print('Browser errors:',errors,flush=True)
        raise
    finally:
        browser.close()
