"""Published workspace should fill the viewport, including tall and short windows."""
from playwright.sync_api import sync_playwright,expect


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1000})
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app')
        expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)
        for width,height in [(1550,1000),(1920,1400),(1440,900),(1024,700)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(600)
            rect=app.bounding_box()
            assert abs(rect['x'])<1 and abs(rect['y'])<1,rect
            assert abs(rect['width']-width)<1 and abs(rect['height']-height)<1,rect
            footer=app.locator('.tof-status').bounding_box()
            assert abs(footer['y']+footer['height']-height)<1,footer
            assert app.evaluate('g=>g.scrollWidth<=g.clientWidth'),rect
            print(f'PASS: app fills {width} × {height}, with header and footer inside viewport',flush=True)
        page.set_viewport_size({'width':1550,'height':1000});page.wait_for_timeout(400)
        page.screenshot(path='/private/tmp/tofscope-full-viewport.png')
        app.locator('[data-display="profile"] .tof-maximize').click()
        focus=app.get_by_role('region',name='Maximized display',exact=True)
        expect(focus).to_be_visible();page.keyboard.press('Escape');expect(focus).to_be_hidden()
        print('PASS: maximize and restore work in the full-window workspace',flush=True)
    finally:browser.close()
