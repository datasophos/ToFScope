"""Regression for dragging the depth profile from frame 200 to frame 400."""
import json
import time
import base64
import os
from pathlib import Path
import h5py
import numpy as np
from playwright.sync_api import sync_playwright,expect


def point(gd,x):
    return gd.evaluate('''(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
      return {x:r.left+a._offset+a.d2p(x),y:r.top+b._offset+b._length/2};}''',x)


def drag(page,gd,a,b):
    start,end=point(gd,a),point(gd,b)
    page.mouse.move(start['x'],start['y']);page.mouse.down()
    page.mouse.move(end['x'],end['y'],steps=15);page.mouse.up()


def ready(app):
    expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


def window(app):
    return json.loads(app.get_attribute('data-depth-window') or 'null')


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app');ready(app)
        gd=app.locator('[data-plot="profile"]')
        before=app.get_attribute('data-revision')
        drag(page,gd,200,400)
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        interval=window(app)
        assert interval and abs(interval[0]-200)<=2 and abs(interval[1]-400)<=2,interval
        shapes=gd.evaluate('(g)=>g.layout.shapes')
        bands=[s for s in shapes if s['type']=='rect']
        assert len(bands)==1 and bands[0]['y0']==0 and bands[0]['y1']==1,shapes
        assert int(app.get_by_label('First integration frame',exact=True).input_value())==interval[0]
        assert int(app.get_by_label('Last integration frame',exact=True).input_value())==interval[1]
        ion=app.locator('[data-plot="ion"]')
        se=app.locator('[data-plot="se"]')
        assert ion.evaluate('(g)=>g.layout.title.text').startswith('Top projection · frames')
        app.get_by_role('button',name='FIB SE image',exact=True).click()
        expect(se).to_have_class(__import__('re').compile('js-plotly-plot'),timeout=30000)
        assert se.evaluate('(g)=>g.layout.title.text').startswith('SE mean · frames')
        app.get_by_role('button',name='SIMS images',exact=True).click()
        values=ion.evaluate('(g)=>g.data[0].customdata')
        if isinstance(values,dict):
            actual=np.frombuffer(base64.b64decode(values['bdata']),dtype=values['dtype']).reshape(128,128)
        else:
            actual=np.asarray(values)
        path=os.environ.get('TOF_FILE',str(Path(__file__).resolve().parents[2]/'2025-12-05_example_datasets/pfib_1301x128x128_AlTiPt.h5'))
        with h5py.File(path,'r') as f:
            expected=f['PeakData/PeakData'][interval[0]:interval[1]+1,:,:,26].sum(axis=0,dtype=np.float64)
        np.testing.assert_array_equal(actual,expected)
        page.screenshot(path='/private/tmp/tof-depth-window-200-400.png')
        print('PASS: drag 200–400 shows a depth window, exact ion sum and mean SE image',flush=True)

        before=app.get_attribute('data-revision')
        pos=point(gd,300);page.mouse.click(pos['x'],pos['y'])
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        assert window(app) is None
        assert abs(int(app.get_attribute('data-frame'))-300)<=2
        assert ion.evaluate('(g)=>g.layout.title.text').startswith('Ion map · frame')
        print('PASS: click returns the maps to a single frame',flush=True)

        before=app.get_attribute('data-revision')
        drag(page,gd,200,400)
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        interval=window(app)

        before=app.get_attribute('data-revision')
        drag(page,gd,interval[1],500)
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        interval=window(app)
        assert abs(interval[0]-200)<=2 and abs(interval[1]-500)<=2,interval
        print('PASS: dragging the window edge resizes the depth interval',flush=True)

        before=app.get_attribute('data-revision')
        page.keyboard.down('Shift');drag(page,gd,350,450);page.keyboard.up('Shift')
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        moved=window(app)
        assert abs(moved[0]-300)<=3 and abs(moved[1]-600)<=3,moved
        print('PASS: Shift-drag moves the depth window',flush=True)

        app.get_by_role('tab',name='3D volume',exact=True).click()
        volume=app.locator('[data-plot="volume"]')
        deadline=time.monotonic()+20
        while not volume.evaluate('(g)=>!!g.data?.length'):
            assert time.monotonic()<deadline;page.wait_for_timeout(100)
        zr=volume.evaluate('(g)=>g._fullLayout.scene.zaxis.range')
        assert min(zr)>=moved[0]-20 and max(zr)<=moved[1]+20,(zr,moved)
        print('PASS: 3D volume is cropped to the selected depth window',flush=True)

        app.get_by_role('tab',name='Explore',exact=True).click()
        app.get_by_role('button',name='Clear depth window',exact=True).click();ready(app)
        expect(app).to_have_attribute('data-depth-window','null',timeout=30000)
        assert not errors,errors
        print('PASS: clear window and no browser errors',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tof-depth-window-failure.png');raise
    finally:b.close()
