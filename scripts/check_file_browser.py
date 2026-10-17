"""Exercise a fixture-configured server: no client acquisition is modified."""
import os
import sys
import json
import tempfile
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_signal_recipes import make_acquisition

repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)/'data';root.mkdir();sub=root/'session';sub.mkdir()
    make_acquisition(sub/'sample.h5');make_acquisition(root/'second.h5')
    (root/'bad.h5').write_text('unsupported')
    for i in range(105):(root/f'empty-{i:03}.h5').touch()
    (root/'escape').symlink_to(root.parent,target_is_directory=True)
    env={**os.environ,'TOFSCOPE_DATA_ROOT':str(root)};env.pop('TOF_FILE',None)
    log=open('/private/tmp/tofscope-browser-fixture.log','w')
    server=subprocess.Popen([str(repo/'.venv/bin/marimo'),'run',str(repo/'app.py'),'--headless','--host','127.0.0.1','--port','2720'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(80):
            try:urllib.request.urlopen('http://127.0.0.1:2720',timeout=1);break
            except OSError:time.sleep(.25)
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
            page=browser.new_page(viewport={'width':1550,'height':1000})
            try:
                page.goto('http://127.0.0.1:2720');app=page.locator('.tof-app')
                expect(app.locator('[data-field="filename"]')).to_have_text('No acquisition open',timeout=30000)
                expect(app.get_by_role('button',name='Profile CSV ↓',exact=True)).to_be_disabled()
                app.get_by_role('button',name='Open file',exact=True).click()
                dialog=app.get_by_role('dialog',name='Open acquisition',exact=True)
                expect(dialog).to_be_visible();expect(dialog.locator('[data-file-path="escape"]')).to_have_count(0)
                expect(dialog.locator('[data-file-path]')).to_have_count(100,timeout=10000)
                dialog.get_by_role('button',name='Next page',exact=True).click()
                expect(dialog.locator('[data-file-path]')).to_have_count(8)
                dialog.get_by_role('button',name='Previous page',exact=True).click()
                dialog.locator('[data-file-path="session"]').dblclick()
                expect(dialog.locator('[data-file-path]')).to_have_count(1)
                dialog.locator('[data-file-path="session/sample.h5"]').click()
                dialog.get_by_role('button',name='Open dataset',exact=True).click()
                expect(app.locator('[data-field="filename"]')).to_have_text('sample.h5',timeout=30000)
                expect(dialog).not_to_be_visible();expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
                with page.expect_download() as d:app.get_by_role('button',name='Settings JSON ↓',exact=True).click()
                settings=json.loads(Path(d.value.path()).read_text());assert settings['dataset']=='session/sample.h5'
                app.get_by_role('button',name='Open file',exact=True).click()
                dialog.get_by_role('button',name='Data',exact=True).click()
                search=dialog.get_by_role('searchbox',name='Filter files',exact=True);search.fill('bad')
                dialog.locator('[data-file-path="bad.h5"]').click();dialog.get_by_role('button',name='Open dataset',exact=True).click()
                expect(dialog.locator('[role="alert"]')).not_to_be_empty(timeout=10000)
                expect(app.locator('[data-field="filename"]')).to_have_text('sample.h5')
                search.fill('second');dialog.locator('[data-file-path="second.h5"]').click()
                (root/'second.h5').unlink()
                dialog.get_by_role('button',name='Open dataset',exact=True).click()
                expect(dialog.locator('[role="alert"]')).to_contain_text('no longer exists',timeout=10000)
                expect(app.locator('[data-field="filename"]')).to_have_text('sample.h5')
                # Keep filtering usable after errors, and close using the keyboard.
                search.fill('nothing');expect(dialog.locator('[data-file-path]')).to_have_count(0)
                expect(dialog).to_contain_text('No matching files')
                page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
                print('PASS: empty startup, paging, breadcrumbs, filtering, opening, relative export, and failed/deleted file preservation',flush=True)
                page.screenshot(path='/private/tmp/tofscope-file-browser.png')
            finally:browser.close()
    finally:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        log.close()
