"""Native modal dialogs stay centered and within the viewport."""
from playwright.sync_api import sync_playwright,expect


def centered(dialog):
    bounds=dialog.evaluate('(d)=>{const r=d.getBoundingClientRect(),s=getComputedStyle(d);return {x:r.x,y:r.y,w:r.width,h:r.height,vw:innerWidth,vh:innerHeight,margin:s.margin,position:s.position,inset:s.inset}}')
    assert abs(bounds['x']+bounds['w']/2-bounds['vw']/2)<2,bounds
    assert abs(bounds['y']+bounds['h']/2-bounds['vh']/2)<2,bounds
    assert bounds['x']>=0 and bounds['y']>=0,bounds
    assert bounds['x']+bounds['w']<=bounds['vw']+1,bounds
    assert bounds['y']+bounds['h']<=bounds['vh']+1,bounds


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    try:
        page=browser.new_page(viewport={'width':1500,'height':1000})
        page.goto('http://127.0.0.1:2718');app=page.locator('.tof-app')
        expect(app.locator('[role=status]')).to_have_text('Ready',timeout=30000)
        for button,title,close in [('Open file','Open acquisition','Cancel'),('Calibrate depth','Known depths','Done'),('Identify atomic ions','Atomic-ion helper','Done')]:
            app.get_by_role('button',name=button,exact=True).click()
            dialog=app.get_by_role('dialog',name=title,exact=True);expect(dialog).to_be_visible()
            for width,height in [(1500,1000),(900,650),(720,500)]:
                page.set_viewport_size(dict(width=width,height=height));page.wait_for_timeout(100);centered(dialog)
            dialog.get_by_role('button',name=close,exact=True).click();expect(dialog).not_to_be_visible()
            page.set_viewport_size(dict(width=1500,height=1000))
        # Reopening and keyboard dismissal still use the same native dialog.
        app.get_by_role('button',name='Open file',exact=True).click();dialog=app.get_by_role('dialog',name='Open acquisition',exact=True)
        centered(dialog);page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
        print('PASS: file browser, calibration and peak dialogs centered at three viewport sizes, resize/reopen and Escape')
    finally:browser.close()
