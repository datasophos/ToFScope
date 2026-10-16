"""Verify the volume describes its active data and distinguishes pending edits."""
from playwright.sync_api import sync_playwright,expect


def ready(app):
    expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


def changed(app,revision):
    expect(app).not_to_have_attribute('data-revision',revision,timeout=30000)
    ready(app)


with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=b.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app');ready(app)
        app.get_by_role('tab',name='3D volume',exact=True).click()
        panel=app.get_by_role('tabpanel',name='3D volume',exact=True)
        panel.locator('.tof-volume-details summary').click()
        expect(panel.locator('[data-field="volume-mass"]')).to_have_text('26.5000–27.5000 Th')
        expect(panel.locator('[data-field="volume-source"]')).to_have_text('Stored channel from file')
        expect(panel.locator('[data-field="volume-depth"]')).to_contain_text('Frames 0–1300')
        expect(panel.locator('[data-field="volume-roi"]')).to_have_text('X 0–127 · Y 0–127 px')
        expect(panel.locator('[data-field="volume-preview"]')).to_contain_text('93 × 32 × 32')
        expect(panel.locator('[data-field="volume-pending"]')).to_be_hidden()
        print('PASS: volume identifies active ion, exact mass bounds, depth, ROI and preview',flush=True)

        panel.get_by_role('button',name='Edit on spectrum →',exact=True).click()
        expect(app.get_by_role('tab',name='Mass spectrum',exact=True)).to_have_attribute('aria-selected','true')
        before=app.get_attribute('data-revision')
        app.get_by_label('Lower mass limit',exact=True).fill('26.8')
        app.get_by_label('Lower mass limit',exact=True).press('Tab');changed(app,before)
        before=app.get_attribute('data-revision')
        app.get_by_label('Upper mass limit',exact=True).fill('27.2')
        app.get_by_label('Upper mass limit',exact=True).press('Tab');changed(app,before)
        app.get_by_role('tab',name='3D volume',exact=True).click()
        expect(panel.locator('[data-field="volume-pending"]')).to_be_visible()
        expect(panel.locator('[data-field="volume-pending"]')).to_contain_text('26.8000–27.2000 Th')
        expect(panel.locator('[data-field="volume-mass"]')).to_have_text('26.5000–27.5000 Th')
        volume=panel.locator('[data-plot="volume"]')
        assert 'Mass 26.5000–27.5000 Th' in volume.evaluate('(g)=>g.layout.title.text')
        print('PASS: pending mass window is clearly separate from rendered mass integration',flush=True)

        panel.get_by_role('button',name='Select on profile →',exact=True).click()
        profile=app.locator('[data-plot="profile"]')
        coords=profile.evaluate('''g=>{const r=g.getBoundingClientRect(),a=g._fullLayout.xaxis,b=g._fullLayout.yaxis;
          return [200,400].map(x=>({x:r.left+a._offset+a.d2p(x),y:r.top+b._offset+b._length/2}));}''')
        before=app.get_attribute('data-revision')
        page.mouse.move(coords[0]['x'],coords[0]['y']);page.mouse.down()
        page.mouse.move(coords[1]['x'],coords[1]['y'],steps=12);page.mouse.up();changed(app,before)
        app.get_by_role('tab',name='3D volume',exact=True).click()
        expect(panel.locator('[data-field="volume-depth"]')).to_contain_text('Frames 200–400')
        expect(panel.locator('[data-field="volume-mass"]')).to_have_text('26.5000–27.5000 Th')
        print('PASS: depth-profile selection updates the displayed 3D depth context',flush=True)

        panel.get_by_role('button',name='Draw on ion map →',exact=True).click()
        app.get_by_text('Exact pixel limits',exact=True).click()
        for label,value in [('ROI X first','10'),('ROI X last','20'),('ROI Y first','30'),('ROI Y last','40')]:
            app.get_by_label(label,exact=True).fill(value)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Set region',exact=True).click();changed(app,before)
        app.get_by_role('tab',name='3D volume',exact=True).click()
        expect(panel.locator('[data-field="volume-roi"]')).to_have_text('X 10–20 · Y 30–40 px')
        expect(panel.locator('[data-field="volume-preview"]')).to_contain_text('67 × 11 × 11')
        page.screenshot(path='/private/tmp/tof-volume-context.png')
        print('PASS: ROI and actual downsampled dimensions track the displayed volume',flush=True)

        for label,value in [('First integration frame','0'),('Last integration frame','3')]:
            before=app.get_attribute('data-revision')
            app.get_by_label(label,exact=True).fill(value)
            app.get_by_label(label,exact=True).press('Tab');changed(app,before)
        before=app.get_attribute('data-revision')
        app.get_by_role('button',name='Apply custom window',exact=True).click();changed(app,before)
        expect(panel.locator('[data-field="volume-source"]')).to_have_text('Applied custom integration')
        expect(panel.locator('[data-field="volume-mass"]')).to_have_text('26.8000–27.2000 Th')
        expect(panel.locator('[data-field="volume-depth"]')).to_contain_text('Frames 0–3')
        expect(panel.locator('[data-field="volume-pending"]')).to_be_hidden()
        assert 'Mass 26.8000–27.2000 Th' in volume.evaluate('(g)=>g.layout.title.text')
        assert not errors,errors
        print('PASS: Apply updates active source, bounds and plot title; clears pending notice',flush=True)
    except Exception:
        page.screenshot(path='/private/tmp/tof-volume-context-failure.png');raise
    finally:b.close()
