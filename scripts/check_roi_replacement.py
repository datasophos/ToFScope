"""Drawing a new spatial ROI must replace the previous Plotly shape."""
import json
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100})
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        ion=app.locator('[data-plot="ion"]')
        ion.evaluate('g=>window.Plotly.relayout(g,{"xaxis.range":[0,18],"yaxis.range":[0,18]})')
        zoom=ion.evaluate('g=>g._fullLayout.xaxis.range')
        def point(x,y):
            return ion.evaluate('''(g,p)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
              return {x:r.x+a._offset+a.d2p(p[0]),y:r.y+b._offset+b.d2p(p[1])}}''',[x,y])
        for bounds in [[2,6,3,7],[9,14,8,13],[3,8,10,16]]:
            a,z=point(bounds[0],bounds[2]),point(bounds[1],bounds[3]);before=app.get_attribute('data-revision')
            page.mouse.move(a['x'],a['y']);page.mouse.down();page.mouse.move(z['x'],z['y'],steps=12);page.mouse.up()
            expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
            info=ion.evaluate('g=>({shapes:g.layout.shapes.map(s=>[s.x0,s.x1,s.y0,s.y1]),paths:g.querySelectorAll(".shapelayer path").length,xrange:g._fullLayout.xaxis.range})')
            print('ROI',app.get_attribute('data-roi'),'Plotly',info,flush=True)
            assert len(info['shapes'])==1 and info['paths']==1,info
            roi=json.loads(app.get_attribute('data-roi'));scale=20/128
            expected=[roi[0]*scale,(roi[1]+1)*scale,roi[2]*scale,(roi[3]+1)*scale]
            assert all(abs(a-b)<1e-9 for a,b in zip(info['shapes'][0],expected)),info
            assert all(abs(a-b)<.4 for a,b in zip(info['shapes'][0],bounds)),info
            assert info['xrange']==zoom,(info,zoom)
        print('PASS: repeated drawing retains only the most recent ROI',flush=True)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Reset to full field',exact=True).click()
        expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)
        expect(app).to_have_attribute('data-roi','[0,127,0,127]')
        assert ion.evaluate('g=>g.layout.shapes.length')==1
        assert ion.evaluate('g=>g.querySelectorAll(".shapelayer path").length')==1
        print('PASS: resetting to the full field removes every old ROI outline',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-roi-replacement-failure.png');raise
    finally:b.close()
