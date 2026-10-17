"""Three stored layers: styles, tiles/overlay, visibility, cameras and budget."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=60000)
def changed(app,before):expect(app).not_to_have_attribute('data-revision',before,timeout=60000);ready(app)
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader']);page=b.new_page(viewport={'width':1660,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        picker=app.locator('[data-picker="comparison"]')
        for mass in ['48','193.95']:
            before=app.get_attribute('data-revision');picker.get_by_role('button',name='Add comparison channel',exact=True).click();picker.get_by_role('combobox').fill(mass);picker.get_by_role('option').first.click();changed(app,before)
        app.get_by_role('tab',name='3D volume',exact=True).click()
        app.get_by_role('button',name='3D layers',exact=True).click();dialog=app.get_by_role('dialog',name='3D layers',exact=True)
        start=time.monotonic()
        for _ in range(2):
            before=app.get_attribute('data-revision');dialog.get_by_role('button',name='Add layer',exact=True).click();changed(app,before)
        expect(dialog.locator('[data-layer-id]')).to_have_count(3)
        for i,scale in enumerate(['Reds','Blues','Greens']):
            before=app.get_attribute('data-revision');dialog.locator('[data-layer-id]').nth(i).get_by_label('Layer colormap',exact=True).select_option(scale);changed(app,before)
        dialog.get_by_role('button',name='Done',exact=True).click();gd=app.locator('[data-plot="volume"]')
        assert gd.evaluate('g=>g.layout.meta.layers.length')==3
        assert len(set(gd.evaluate('g=>g.data.map(t=>t.scene)')))==3
        app.locator('[data-display="volume"] .tof-maximize').click();page.keyboard.press('Escape')
        app.get_by_role('button',name='3D layers',exact=True).click()
        before=app.get_attribute('data-revision');dialog.get_by_label('3D arrangement',exact=True).select_option('overlay');changed(app,before)
        dialog.get_by_role('button',name='Done',exact=True).click()
        assert len(set(gd.evaluate('g=>g.data.map(t=>t.scene)')))==1
        details=gd.evaluate('g=>({layers:g.layout.meta.layers})');metrics=json.loads(app.get_attribute('data-volume-details'));details['bytes']=metrics['encoded_bytes']
        assert sum(__import__('math').prod(l['shape']) for l in details['layers'])<=500000
        assert details['bytes']<=32*2**20,details['bytes']
        timings=gd.evaluate("""async g=>{const times=[];for(let i=0;i<30;i++){const t=performance.now();await window.Plotly.relayout(g,{'scene.camera':{eye:{x:1.5*Math.cos(i*.08),y:1.5*Math.sin(i*.08),z:.9}}});await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));times.push(performance.now()-t);}return times.sort((a,b)=>a-b);}""")
        metrics['camera_update_p95_ms']=timings[28]
        before_camera=gd.evaluate('g=>JSON.stringify(g._fullLayout.scene._scene.getCamera())')
        point=gd.evaluate('g=>{const r=g.getBoundingClientRect(),s=g._fullLayout.scene;const a=s.domain;return {x:r.left+g._fullLayout._size.l+g._fullLayout._size.w*(a.x[0]+a.x[1])/2,y:r.top+g._fullLayout._size.t+g._fullLayout._size.h*(1-(a.y[0]+a.y[1])/2)}}');page.mouse.move(point['x'],point['y']);page.mouse.down();page.mouse.move(point['x']+60,point['y']+40,steps=10);page.mouse.up();page.wait_for_timeout(200)
        assert gd.evaluate('g=>JSON.stringify(g._fullLayout.scene._scene.getCamera())')!=before_camera
        drag_times=[]
        for i in range(30):
            started=time.monotonic();page.mouse.move(point['x'],point['y']);page.mouse.down();page.mouse.move(point['x']+10+(i%3)*2,point['y']+8);page.mouse.up()
            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');drag_times.append((time.monotonic()-started)*1000)
        metrics['drag_to_frame_p95_ms']=sorted(drag_times)[28]
        app.get_by_role('button',name='3D layers',exact=True).click()
        before=app.get_attribute('data-revision');dialog.locator('[data-layer-id]').nth(1).get_by_label('Show layer',exact=True).uncheck();changed(app,before)
        dialog.get_by_role('button',name='Done',exact=True).click();assert gd.evaluate('g=>g.data.length')==2
        app.get_by_role('button',name='3D layers',exact=True).click()
        before=app.get_attribute('data-revision');dialog.get_by_label('3D arrangement',exact=True).select_option('tiles');changed(app,before)
        dialog.get_by_role('button',name='Done',exact=True).click()
        cameras=gd.evaluate("""async g=>{await window.Plotly.relayout(g,{'scene.camera':{eye:{x:2,y:1,z:.7}}});await new Promise(r=>setTimeout(r,150));return [g.layout.scene.camera.eye,g.layout.scene2.camera.eye];}""")
        assert cameras[0]==cameras[1],cameras
        app.get_by_role('button',name='3D layers',exact=True).click();dialog.get_by_label('Link tile cameras',exact=True).uncheck();dialog.get_by_role('button',name='Done',exact=True).click()
        cameras=gd.evaluate("""async g=>{await window.Plotly.relayout(g,{'scene2.camera':{eye:{x:1,y:2,z:.3}}});await new Promise(r=>setTimeout(r,150));return [g.layout.scene.camera.eye,g.layout.scene2.camera.eye];}""")
        assert cameras[0]!=cameras[1],cameras
        assert not errors,errors
        page.screenshot(path='/private/tmp/tofscope-multi-volume.png')
        print('PASS: three styled layers, tiled/overlay coordinates, visibility, maximize and total preview/payload budget',flush=True)
        print(json.dumps(dict(workflow_seconds=round(time.monotonic()-start,2),payload_bytes=details['bytes'],preparation_seconds=metrics['preparation_seconds'],camera_update_p95_ms=round(metrics['camera_update_p95_ms'],1),drag_to_frame_p95_ms=round(metrics['drag_to_frame_p95_ms'],1),preview_shapes=[l['shape'] for l in details['layers']])),flush=True)
    finally:b.close()
