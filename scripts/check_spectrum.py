"""Regression checks for one-dimensional mass-window gestures."""
import time
from playwright.sync_api import sync_playwright, expect


def point(gd,x,y=None):
    return gd.evaluate('''(g,c)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
      return {x:r.left+a._offset+a.d2p(c[0]),y:r.top+b._offset+(c[1]===null?b._length/2:b.d2p(c[1]))};}''',[x,y])


def drag(page,a,b):
    page.mouse.move(a['x'],a['y']);page.mouse.down()
    page.mouse.move(b['x'],b['y'],steps=15);page.mouse.up()


def ready(app):
    expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


def check_band(gd):
    shapes=gd.evaluate('(g)=>g.layout.shapes')
    assert len(shapes)==1,shapes
    shape=shapes[0]
    assert shape['yref'] in ('paper','y domain') and shape['y0']==0 and shape['y1']==1,shape


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app');ready(app)
        app.get_by_role('tab',name='Mass spectrum',exact=True).click()
        gd=app.locator('[data-plot="spectrum"]')
        deadline=time.monotonic()+20
        while not gd.evaluate('(g)=>!!g._fullLayout?.xaxis'):
            assert time.monotonic()<deadline;page.wait_for_timeout(100)
        rev=app.get_attribute('data-revision')
        drag(page,point(gd,40),point(gd,60))
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        assert abs(low-40)<.6 and abs(high-60)<.6,(low,high)
        check_band(gd)
        print('PASS: horizontal drag produces one full-height interval',flush=True)

        rev=app.get_attribute('data-revision')
        app.get_by_role('button',name='Restore stored channel',exact=True).click()
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        app.get_by_role('button',name='Zoom to window',exact=True).click();page.wait_for_timeout(150)
        peak=gd.evaluate('''g=>{const d=g._fullData[0];let best=null;
          for(let i=0;i<d.x.length;i++)if(d.x[i]>26.8&&d.x[i]<27.1&&(!best||d.y[i]>best[1]))best=[d.x[i],d.y[i]];return best;}''')
        assert peak, 'Could not locate a real spectrum peak'
        rev=app.get_attribute('data-revision')
        drag(page,point(gd,*peak),point(gd,27.3,peak[1]))
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        assert abs(low-peak[0])<.03 and abs(high-27.3)<.03,(low,high,peak)
        check_band(gd)
        print('PASS: horizontal drag starting on a real peak selects an interval',flush=True)

        rev=app.get_attribute('data-revision')
        drag(page,point(gd,high),point(gd,27.6))
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        assert abs(float(app.get_by_label('Upper mass limit',exact=True).input_value())-27.6)<.03
        check_band(gd)
        print('PASS: dragging the gold edge resizes the interval',flush=True)

        low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        center=(low+high)/2
        rev=app.get_attribute('data-revision')
        page.keyboard.down('Shift')
        drag(page,point(gd,center),point(gd,center+.2))
        page.keyboard.up('Shift')
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        moved_low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        moved_high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        assert abs(moved_low-low-.2)<.03 and abs(moved_high-high-.2)<.03,(moved_low,moved_high)
        check_band(gd)
        print('PASS: Shift-drag moves the band without changing its width',flush=True)

        rev=app.get_attribute('data-revision')
        drag(page,point(gd,28.2),point(gd,27.9))
        expect(app).not_to_have_attribute('data-revision',rev,timeout=20000);ready(app)
        low=float(app.get_by_label('Lower mass limit',exact=True).input_value())
        high=float(app.get_by_label('Upper mass limit',exact=True).input_value())
        assert abs(low-27.9)<.03 and abs(high-28.2)<.03,(low,high)
        check_band(gd)
        assert not errors,errors
        print('PASS: right-to-left selection and no browser errors',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tof-spectrum-regression.png');raise
    finally:b.close()
