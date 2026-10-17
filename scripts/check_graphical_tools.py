"""Click-first spectrum identification and depth anchors on disposable data."""
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
def point(plot,x):
    return plot.evaluate('(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;return {x:r.left+a._offset+a.d2p(x),y:r.top+b._offset+b._length/2}}',x)


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);path=root/'sample.h5';make_acquisition(path)
    with h5py.File(path,'r+') as f:
        for name in ['PeakData/PeakData','PeakData/PeakTable','FullSpectra/MassAxis','FullSpectra/SumSpectrum']:del f[name]
        data=np.empty((5,2,2,2),dtype=np.float32)
        for i,v in enumerate([1,3,9,4,1]):data[i,:,:,0]=v
        for i,v in enumerate([2,8,4,2,1]):data[i,:,:,1]=v
        f['PeakData'].create_dataset('PeakData',data=data)
        dtype=np.dtype([('label','S64'),('mass','f4'),('lower integration limit','f4'),('upper integration limit','f4')])
        f['PeakData'].create_dataset('PeakTable',data=np.array([(b'Al',27,26.5,27.5),(b'Ti',48,47.5,48.5)],dtype=dtype))
        masses=np.linspace(25,50,25001);f['FullSpectra'].create_dataset('MassAxis',data=masses)
        f['FullSpectra'].create_dataset('SumSpectrum',data=1+1e5*np.exp(-((masses-26.981)/.008)**2)+2e4*np.exp(-((masses-47.948)/.008)**2))
    original=path.read_bytes()
    env={**os.environ,'TOFSCOPE_DATA_ROOT':str(root),'TOF_FILE':str(path),'TOFSCOPE_ALLOW_WRITES':'false'}
    with open('/private/tmp/tofscope-graphical-tools.log','w') as log:
        server=subprocess.Popen([str(repo/'.venv/bin/marimo'),'run',str(repo/'app.py'),'--headless','--host','127.0.0.1','--port','2723'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(80):
                try:urllib.request.urlopen('http://127.0.0.1:2723',timeout=1);break
                except OSError:time.sleep(.25)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
                try:
                    page=browser.new_page(viewport={'width':1550,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto('http://127.0.0.1:2723');app=page.locator('.tof-app');ready(app)
                    label=app.locator('[data-field=signal]').inner_text()
                    app.get_by_role('button',name='Identify atomic ions',exact=True).click();peak=app.get_by_role('dialog',name='Atomic-ion helper',exact=True)
                    spectrum=peak.locator('[data-dialog-plot=spectrum]');expect(spectrum.locator('.xtitle')).to_have_text('Mass / charge (Th)',timeout=5000)
                    pos=point(spectrum,26.981);page.mouse.click(**pos)
                    al=peak.locator('[data-candidate="Al-27:+1"]');expect(al).to_be_visible(timeout=10000)
                    assert abs(float(peak.get_by_label('Measured mass',exact=True).input_value())-26.981)<.0011
                    measured=peak.get_by_label('Measured mass',exact=True).input_value()
                    a=point(spectrum,26);b=point(spectrum,28)
                    page.mouse.move(a['x'],a['y']-45);page.mouse.down();page.mouse.move(b['x'],b['y']+45,steps=12);page.mouse.up()
                    page.wait_for_function('g=>g._fullLayout.xaxis.range[1]-g._fullLayout.xaxis.range[0]<3',arg=spectrum.element_handle())
                    expect(peak.get_by_label('Measured mass',exact=True)).to_have_value(measured)
                    al.get_by_role('button',name='Select',exact=True).click()
                    expect(peak.get_by_role('button',name='Annotate signal',exact=True)).to_be_enabled()
                    peak.get_by_role('button',name='Full spectrum',exact=True).click()
                    page.wait_for_function('g=>g._fullLayout.xaxis.range[1]-g._fullLayout.xaxis.range[0]>20',arg=spectrum.element_handle())
                    before=app.get_attribute('data-revision');peak.get_by_role('button',name='Annotate signal',exact=True).click();changed(app,before)
                    expect(app.locator('[data-field=signal]')).to_have_text(label)
                    page.screenshot(path='/private/tmp/tofscope-graphical-identify.png')
                    peak.get_by_role('button',name='Done',exact=True).click()
                    picker=app.locator('[data-picker=comparison]');before=app.get_attribute('data-revision')
                    picker.get_by_role('button',name='Add comparison channel',exact=True).click();picker.get_by_role('combobox').fill('48');picker.get_by_role('option').first.click();changed(app,before)
                    app.get_by_role('button',name='Calibrate depth',exact=True).click();depth=app.get_by_role('dialog',name='Known depths',exact=True)
                    profile=depth.locator('[data-dialog-plot=depth]');expect(profile.locator('.xtitle')).to_have_text('Depth frame',timeout=5000)
                    assert profile.evaluate('g=>g._fullData.length')==2
                    for frame,value in [(2,100),(4,300)]:
                        page.mouse.click(**point(profile,frame));expect(depth.get_by_label('Anchor frame',exact=True)).to_have_value(str(frame))
                        depth.get_by_label('Known depth',exact=True).fill(str(value));before=app.get_attribute('data-revision')
                        depth.get_by_role('button',name='Add anchor',exact=True).click();changed(app,before)
                    before=app.get_attribute('data-revision');depth.get_by_label('Depth coordinates',exact=True).select_option('depth');changed(app,before)
                    before=app.get_attribute('data-revision');depth.locator('[data-anchor-frame="4"]').get_by_role('button',name='Remove anchor',exact=True).click();changed(app,before)
                    # The editor still exposes uncalibrated frames, even in physical display mode.
                    page.mouse.click(**point(profile,4));depth.get_by_label('Known depth',exact=True).fill('320');before=app.get_attribute('data-revision')
                    depth.get_by_role('button',name='Add anchor',exact=True).click();changed(app,before)
                    page.mouse.click(**point(profile,2));expect(depth.get_by_label('Known depth',exact=True)).to_have_value('100')
                    depth.get_by_label('Known depth',exact=True).fill('120');before=app.get_attribute('data-revision')
                    depth.get_by_role('button',name='Update anchor',exact=True).click();changed(app,before)
                    depth.get_by_label('Known depth',exact=True).evaluate('''input=>{
                      for(const value of ['130','140']){
                        input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));
                        input.closest('dialog').querySelector('[data-add]').click();
                      }
                    }''')
                    expect(depth.locator('[data-anchor-frame="2"] input')).to_have_value('140',timeout=10000)
                    expect(depth.get_by_label('Known depth',exact=True)).to_have_value('140')
                    depth.get_by_label('Known depth',exact=True).evaluate('''input=>{
                      input.value='150';input.dispatchEvent(new Event('input',{bubbles:true}));
                      input.closest('dialog').querySelector('[data-add]').click();
                      input.value='160';input.dispatchEvent(new Event('input',{bubbles:true}));
                    }''')
                    expect(depth.locator('[data-anchor-frame="2"] input')).to_have_value('150',timeout=10000)
                    expect(depth.get_by_label('Known depth',exact=True)).to_have_value('160')
                    page.mouse.click(**point(profile,3));depth.get_by_label('Known depth',exact=True).fill('250')
                    before=app.get_attribute('data-revision');depth.get_by_label('Depth display unit',exact=True).select_option('µm');changed(app,before)
                    expect(depth.get_by_label('Known depth',exact=True)).to_have_value('0.25')
                    page.mouse.click(**point(profile,0));expect(depth.get_by_label('Known depth',exact=True)).to_be_disabled()
                    page.screenshot(path='/private/tmp/tofscope-graphical-depth.png')
                    assert not errors,errors;assert path.read_bytes()==original
                    print('PASS: click spectrum→atomic candidates, explicit annotation; current/comparison profiles→add/edit depth, unknown frames accessible, unit drafts and fixed zero; source unchanged')
                finally:browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
