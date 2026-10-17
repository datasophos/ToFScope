"""Verify shared plot geometry, help tooltips and maximize/restore behavior."""
from playwright.sync_api import sync_playwright,expect


def geometry(g): return g.evaluate('g=>{const r=g.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}')


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1660,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app')
        expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
        def plot(key):return app.locator(f'[data-plot="{key}"]')
        def aligned():
            a,b,c,d=map(lambda k:geometry(plot(k)),['ion','spectrum','front','profile'])
            assert abs(a['y']-b['y'])<2,(a,b)
            assert abs(c['y']-d['y'])<2,(c,d)
            assert abs(a['h']-b['h'])<2 and abs(c['h']-d['h'])<2,(a,b,c,d)
            assert abs(a['h']-c['h'])<2,(a,c)
        for width,height in [(1660,1100),(1440,900),(1280,900)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(600);aligned()
        page.set_viewport_size({'width':1660,'height':1100});page.wait_for_timeout(400)
        print('PASS: top/bottom plot frames align and have equal heights at three desktop sizes',flush=True)
        for name in ['Image help','SIMS top map help','Depth profile help','Mass spectrum help']:
            info=app.get_by_role('button',name=name,exact=True)
            tip=info.locator('..').get_by_role('tooltip')
            expect(tip).to_be_hidden();info.hover();expect(tip).to_be_visible()
            info.focus();page.mouse.move(20,20);expect(tip).to_be_visible()
            info.press('Tab');expect(tip).to_be_hidden()
        print('PASS: instructions appear on info hover and keyboard focus',flush=True)
        for key in ['ion','front','spectrum','profile','se']:
            if key=='se':app.get_by_role('button',name='FIB SE image',exact=True).click()
            before=geometry(plot(key))
            plot(key).evaluate('(g)=>{g._testIdentity=123;}')
            frame=app.locator(f'[data-display="{key}"]')
            frame.locator('.tof-maximize').click()
            focus=app.get_by_role('region',name='Maximized display',exact=True)
            expect(focus).to_be_visible()
            page.wait_for_timeout(500)
            big=geometry(plot(key))
            assert big['w']>before['w']+100 and big['h']>before['h']+(10 if key=='se' else 100),(key,before,big)
            assert plot(key).evaluate('g=>g._testIdentity')==123
            if key=='profile':
                # Interact while enlarged: click selects a frame and updates the same instance.
                pos=plot(key).evaluate('''g=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
                  return {x:r.x+a._offset+a.d2p(500),y:r.y+b._offset+b._length/2}}''')
                page.mouse.click(pos['x'],pos['y'])
                expect(app).to_have_attribute('data-frame','500',timeout=30000)
                expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
            if key in ['ion','spectrum','se']:page.keyboard.press('Escape')
            else:app.get_by_role('button',name='Restore layout',exact=True).click()
            expect(focus).to_be_hidden();page.wait_for_timeout(350)
            restored=geometry(plot(key))
            assert abs(restored['h']-before['h'])<2 and abs(restored['w']-before['w'])<2,(key,before,restored)
            assert plot(key).evaluate('g=>g._testIdentity')==123
            if key=='se':app.get_by_role('button',name='SIMS images',exact=True).click()
        aligned()
        print('PASS: each primary display maximizes and restores; enlarged plots stay interactive',flush=True)
        page.screenshot(path='/private/tmp/tofscope-clean-grid.png')
        app.locator('[data-display="profile"] .tof-maximize').click();page.wait_for_timeout(400)
        page.screenshot(path='/private/tmp/tofscope-maximized-profile.png')
        page.keyboard.press('Escape')
        app.get_by_role('tab',name='Mass spectrum',exact=True).click();expect(plot('spectrum')).to_be_visible()
        app.locator('[data-display="spectrum"] .tof-maximize').click()
        expect(app.get_by_role('region',name='Maximized display',exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        app.get_by_role('tab',name='Explore',exact=True).click();page.wait_for_timeout(400);aligned()
        assert not errors,errors
        print('PASS: spectrum tab round-trip and no browser errors',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tofscope-display-failure.png');print(errors,flush=True);raise
    finally:b.close()
