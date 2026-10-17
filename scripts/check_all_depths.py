"""Return from a single frame or interval to the complete loaded depth range."""
from playwright.sync_api import sync_playwright,expect


def ready(app):expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


def changed(app,before):
    expect(app).not_to_have_attribute('data-revision',before,timeout=30000);ready(app)


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app');ready(app)
        all_depths=app.get_by_role('button',name='All depths',exact=True)
        expect(all_depths).to_be_visible(timeout=5000)
        expect(all_depths).to_have_attribute('aria-pressed','true')
        profile=app.locator('[data-plot="profile"]');ion=app.locator('[data-plot="ion"]')
        def point(frame):
            return profile.evaluate('''(g,x)=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
              return {x:r.x+a._offset+a.d2p(x),y:r.y+b._offset+b._length/2}}''',frame)
        before=app.get_attribute('data-revision');pos=point(400);page.mouse.click(pos['x'],pos['y']);changed(app,before)
        expect(all_depths).to_have_attribute('aria-pressed','false')
        assert 'Ion map · frame 400' in ion.evaluate('g=>g.layout.title.text')
        before=app.get_attribute('data-revision');all_depths.click();changed(app,before)
        expect(all_depths).to_have_attribute('aria-pressed','true')
        assert 'frames 0–1300' in ion.evaluate('g=>g.layout.title.text')
        assert profile.evaluate('g=>g.layout.shapes[0].visible') is False
        expect(app.locator('[data-field="selection-summary"]')).to_contain_text('All loaded depths')
        print('PASS: visible All depths returns a single-frame map to the full-depth projection',flush=True)
        a,z=point(200),point(500);before=app.get_attribute('data-revision')
        page.mouse.move(a['x'],a['y']);page.mouse.down();page.mouse.move(z['x'],z['y'],steps=12);page.mouse.up();changed(app,before)
        expect(all_depths).to_have_attribute('aria-pressed','false')
        before=app.get_attribute('data-revision');all_depths.click();changed(app,before)
        expect(app).to_have_attribute('data-depth-window','null')
        expect(all_depths).to_have_attribute('aria-pressed','true')
        expect(app.get_by_label('First integration frame',exact=True)).to_have_value('0')
        expect(app.get_by_label('Last integration frame',exact=True)).to_have_value('1300')
        print('PASS: All depths clears a range and restores the full integration frame limits',flush=True)
        before=app.get_attribute('data-revision');pos=point(600);page.mouse.click(pos['x'],pos['y']);changed(app,before)
        app.locator('[data-display="profile"] .tof-maximize').click()
        clear=app.get_by_role('button',name='Clear depth window',exact=True)
        expect(clear).to_be_visible()
        before=app.get_attribute('data-revision');clear.click();changed(app,before)
        expect(clear).to_be_hidden();page.keyboard.press('Escape')
        expect(all_depths).to_have_attribute('aria-pressed','true')
        assert not errors,errors
        print('PASS: enlarged depth profile also offers All depths after selecting one slice',flush=True)
        page.screenshot(path='/private/tmp/tofscope-all-depths.png')
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-all-depths-failure.png');raise
    finally:b.close()
