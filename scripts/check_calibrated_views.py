"""Exercise nonlinear physical-depth views with disposable acquisition data."""
import os
import sys
import tempfile
import subprocess
import time
import urllib.request
from pathlib import Path
import h5py
import numpy as np
from playwright.sync_api import sync_playwright,expect
repo=Path(__file__).resolve().parents[1];sys.path[:0]=[str(repo),str(repo/'tests')]
from test_signal_recipes import make_acquisition


def ready(app):expect(app.locator('[role=status]')).to_have_text('Ready',timeout=30000)
def changed(app,before):expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
def point(plot,value):
    return plot.evaluate('(g,v)=>{const r=g.getBoundingClientRect(),x=g._fullLayout.xaxis,y=g._fullLayout.yaxis;return {x:r.left+x._offset+x._length/2,y:r.top+y._offset+y.d2p(v)}}',value)


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);path=root/'sample.h5';make_acquisition(path)
    with h5py.File(path,'r+') as f:
        del f['PeakData/PeakData'];del f['PeakData/PeakTable']
        f['PeakData'].create_dataset('PeakData',data=np.arange(1,25,dtype=np.float32).reshape(3,2,2,2))
        dtype=np.dtype([('label','S64'),('mass','f4'),('lower integration limit','f4'),('upper integration limit','f4')])
        f['PeakData'].create_dataset('PeakTable',data=np.array([(b'first',2,1,3),(b'second',4,3.5,4.5)],dtype=dtype))
        f.create_group('FIBParams').attrs['ViewField']=.001
    before_bytes=path.read_bytes()
    env={**os.environ,'TOFSCOPE_DATA_ROOT':str(root),'TOF_FILE':str(path),'TOFSCOPE_ALLOW_WRITES':'false'}
    with open('/private/tmp/tofscope-calibrated-views.log','w') as log:
        server=subprocess.Popen([str(repo/'.venv/bin/marimo'),'run',str(repo/'app.py'),'--headless','--host','127.0.0.1','--port','2722'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(80):
                try:urllib.request.urlopen('http://127.0.0.1:2722',timeout=1);break
                except OSError:time.sleep(.25)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
                try:
                    page=browser.new_page(viewport={'width':1650,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto('http://127.0.0.1:2722');app=page.locator('.tof-app');ready(app)
                    app.get_by_role('button',name='Calibrate depth',exact=True).click();dialog=app.get_by_role('dialog',name='Known depths',exact=True)
                    for frame,depth in [(1,100),(2,400)]:
                        dialog.get_by_label('Anchor frame',exact=True).fill(str(frame));dialog.get_by_label('Known depth',exact=True).fill(str(depth))
                        before=app.get_attribute('data-revision');dialog.get_by_role('button',name='Add anchor',exact=True).click();changed(app,before)
                    before=app.get_attribute('data-revision');dialog.get_by_label('Depth coordinates',exact=True).select_option('depth');changed(app,before)
                    before=app.get_attribute('data-revision');dialog.get_by_label('Depth display unit',exact=True).select_option('µm');changed(app,before)
                    dialog.get_by_role('button',name='Done',exact=True).click()
                    front=app.locator('[data-plot=front]');expect(front.locator('.ytitle')).to_have_text('Depth (µm)')
                    app.get_by_role('tab',name='Cross-sections',exact=True).click()
                    xz=app.locator('[data-plot=xz]');expect(xz.locator('.ytitle')).to_have_text('Depth (µm)')
                    pos=point(xz,.1);before=app.get_attribute('data-revision');page.mouse.click(**pos);changed(app,before)
                    assert app.get_attribute('data-frame')=='1'
                    assert xz.evaluate('g=>g.layout.shapes[0].y0')==.1
                    app.get_by_role('tab',name='Explore',exact=True).click()
                    pos=point(front,.4);before=app.get_attribute('data-revision');page.mouse.click(**pos);changed(app,before)
                    assert app.get_attribute('data-frame')=='2'
                    picker=app.locator('[data-picker=comparison]');before=app.get_attribute('data-revision')
                    picker.get_by_role('button',name='Add comparison channel',exact=True).click();picker.get_by_role('combobox').fill('2.0000');picker.get_by_role('option').first.click();changed(app,before)
                    app.get_by_role('tab',name='3D volume',exact=True).click();volume=app.locator('[data-plot=volume]')
                    expect(app.get_by_label('Z display stretch',exact=True)).to_have_value('1')
                    scene=volume.evaluate('g=>({title:g.layout.scene.zaxis.title.text,ratio:g.layout.scene.aspectratio.z,kind:g.layout.meta.axis_kind})')
                    assert scene==dict(title='Depth (µm)',ratio=.4,kind='depth'),scene
                    app.get_by_role('button',name='3D layers',exact=True).click();layers=app.get_by_role('dialog',name='3D layers',exact=True)
                    before=app.get_attribute('data-revision');layers.get_by_role('button',name='Add layer',exact=True).click();changed(app,before)
                    layers.get_by_role('button',name='Done',exact=True).click()
                    assert volume.evaluate('g=>g.layout.scene2.zaxis.title.text')=='Depth (µm)'
                    app.get_by_role('button',name='Calibrate 3D depth',exact=True).click()
                    before=app.get_attribute('data-revision');dialog.get_by_label('Depth display unit',exact=True).select_option('nm');changed(app,before)
                    before=app.get_attribute('data-revision');dialog.locator('[data-anchor-frame="2"]').get_by_role('button',name='Remove anchor',exact=True).click();changed(app,before)
                    dialog.get_by_role('button',name='Done',exact=True).click()
                    assert volume.evaluate('g=>g.layout.scene.aspectratio.z')==.1
                    expect(app.locator('[data-field=volume-depth]')).to_contain_text('unknown')
                    app.get_by_role('button',name='3D layers',exact=True).click()
                    before=app.get_attribute('data-revision');layers.get_by_label('3D arrangement',exact=True).select_option('overlay');changed(app,before)
                    layers.get_by_role('button',name='Done',exact=True).click()
                    assert volume.evaluate('g=>g.data.every(t=>t.scene==="scene")')
                    assert volume.evaluate('g=>g._fullData.every(t=>Math.max(...t.z)<=100)')
                    app.locator('[data-display=volume] .tof-maximize').click();page.keyboard.press('Escape')
                    app.get_by_role('button',name='Calibrate 3D depth',exact=True).click()
                    before=app.get_attribute('data-revision');dialog.get_by_label('Depth coordinates',exact=True).select_option('frame');changed(app,before)
                    dialog.get_by_role('button',name='Done',exact=True).click()
                    assert volume.evaluate('g=>g.layout.scene.zaxis.title.text')=='Depth frame'
                    assert max(volume.evaluate('g=>Array.from(g._fullData[0].z)'))==2
                    assert not errors,errors;assert path.read_bytes()==before_bytes
                    page.screenshot(path='/private/tmp/tofscope-calibrated-views.png')
                    print('PASS: calibrated section/front clicks, nonlinear 3D spacing, physical aspect, units, tiles/overlay, unknown-depth clipping, maximize and frame fallback; source unchanged')
                finally:browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
