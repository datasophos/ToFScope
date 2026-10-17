"""Exercise explicit saves, cancellation and stale sessions on disposable H5."""
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

repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(repo),str(repo/'tests')]
from test_signal_recipes import make_acquisition
from integration_store import list_saved_integrations,read_saved_integration

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);path=root/'sample.h5';make_acquisition(path)
    env={**os.environ,'TOFSCOPE_DATA_ROOT':str(root),'TOF_FILE':str(path),
         'TOFSCOPE_ALLOW_WRITES':'true','TOFSCOPE_ALLOW_UNVERIFIED_NATIVE':'true'}
    with open('/private/tmp/tofscope-writeback-browser.log','w') as log:
        server=subprocess.Popen([str(repo/'.venv/bin/marimo'),'run',str(repo/'app.py'),'--headless','--host','127.0.0.1','--port','2721'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(80):
                try:urllib.request.urlopen('http://127.0.0.1:2721',timeout=1);break
                except OSError:time.sleep(.25)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
                try:
                    page=browser.new_page(viewport={'width':1600,'height':1050})
                    other=browser.new_page(viewport={'width':1600,'height':1050})
                    for tab in [page,other]:
                        tab.goto('http://127.0.0.1:2721');expect(tab.locator('.tof-app [role=status]')).to_have_text('Ready',timeout=30000)
                    app=page.locator('.tof-app');old=other.locator('.tof-app')
                    app.get_by_label('Lower mass limit',exact=True).fill('1');app.get_by_label('Lower mass limit',exact=True).press('Tab')
                    app.get_by_label('Upper mass limit',exact=True).fill('2');app.get_by_label('Upper mass limit',exact=True).press('Tab')
                    app.get_by_role('button',name='Apply custom window',exact=True).click()
                    expect(app.locator('[data-field=source]')).to_have_text('RECONSTRUCTED RAW EVENTS',timeout=10000)
                    before=path.read_bytes()
                    app.get_by_role('button',name='Save integration…',exact=True).click()
                    dialog=app.get_by_role('dialog',name='Save integration',exact=True)
                    expect(dialog).to_contain_text('sample.h5');expect(dialog).to_contain_text('unverified')
                    expect(dialog.get_by_role('button',name='Save to acquisition',exact=True)).to_be_enabled(timeout=10000)
                    dialog.get_by_role('button',name='Cancel',exact=True).click()
                    assert path.read_bytes()==before
                    app.get_by_role('button',name='Save integration…',exact=True).click()
                    dialog.get_by_label('Native peak label',exact=True).fill('ToFScope_test')
                    dialog.get_by_role('button',name='Save to acquisition',exact=True).click()
                    expect(dialog).to_contain_text('Saved successfully',timeout=30000)
                    expect(app.locator('[data-field=source]')).to_have_text('SAVED INTEGRATION')
                    records=list_saved_integrations(path);assert len(records)==1
                    np.testing.assert_array_equal(read_saved_integration(path,records[0]['id']),[[[.75,0]],[[.75,.25]],[[.75,.5]]])
                    with h5py.File(path,'r') as f:
                        assert f['PeakData/PeakData'].shape[-1]==2
                        assert f['PeakData/PeakTable'][1]['label']==b'ToFScope_test'
                    assert any(root.glob('.*.bak'))
                    old.get_by_label('Depth frame',exact=True).fill('1');old.get_by_label('Depth frame',exact=True).press('Tab')
                    expect(old.locator('[role=status]')).to_contain_text('Reload acquisition',timeout=10000)
                    old.get_by_role('button',name='Reload acquisition',exact=True).click()
                    expect(old.locator('[role=status]')).to_have_text('Ready',timeout=15000)
                    old.get_by_label('Saved integrations',exact=True).select_option(records[0]['id'])
                    expect(old.locator('[data-field=source]')).to_have_text('SAVED INTEGRATION')
                    dialog.get_by_role('button',name='Close',exact=True).click()
                    page.screenshot(path='/private/tmp/tofscope-writeback.png')
                    print('PASS: save review, cancel unchanged, native + extension values, backup, reload and stale-session protection')
                finally:browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
