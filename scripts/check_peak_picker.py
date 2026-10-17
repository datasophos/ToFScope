"""Browser checks for searchable ion and comparison channel pickers."""
from playwright.sync_api import sync_playwright,expect


def ready(app):
    expect(app.locator('[role="status"]')).to_have_text('Ready',timeout=30000)


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto('http://127.0.0.1:2718')
        app=page.locator('.tof-app');ready(app)
        primary=app.locator('[data-picker="peak"]')
        comparison=app.locator('[data-picker="comparison"]')
        primary.get_by_role('button',name='Choose ion channel',exact=True).click()
        search=primary.get_by_role('combobox',name='Search ion channels',exact=True)
        expect(search).to_be_focused()
        assert primary.get_by_role('option').count()<=8
        search.fill('48')
        expect(primary.get_by_role('option')).to_have_count(1)
        primary.get_by_role('option').click()
        expect(app).to_have_attribute('data-peak','47',timeout=30000);ready(app)
        expect(primary.get_by_role('button',name='Choose ion channel',exact=True)).to_contain_text('48.0000')
        print('PASS: mass search selects a stored ion channel without a long dropdown',flush=True)

        primary.get_by_role('button',name='Choose ion channel',exact=True).click()
        search.fill('Pt')
        expect(primary.get_by_role('option')).to_have_count(1)
        primary.get_by_role('option').click()
        expect(app).to_have_attribute('data-peak','216',timeout=30000);ready(app)
        expect(app.locator('[data-field="signal"]')).to_contain_text('[194Pt]')
        print('PASS: search by file label finds the Pt channel',flush=True)

        primary.get_by_role('button',name='Use recent 48.0000 Th',exact=True).click()
        expect(app).to_have_attribute('data-peak','47',timeout=30000);ready(app)
        print('PASS: recent channels switch with one click',flush=True)

        primary.get_by_role('button',name='Choose ion channel',exact=True).click()
        search.fill('193')
        expect(primary.get_by_role('option')).to_have_count(2)
        search.press('ArrowDown');search.press('Enter')
        expect(app).to_have_attribute('data-peak','216',timeout=30000);ready(app)
        primary.get_by_role('button',name='Choose ion channel',exact=True).click()
        search.fill('nothing matches this ion')
        expect(primary.get_by_role('option')).to_have_count(0)
        expect(primary.locator('[data-picker-count]')).to_have_text('No matching stored channels')
        search.press('Escape')
        expect(primary.locator('[data-picker-popup]')).to_be_hidden()
        expect(primary.get_by_role('button',name='Choose ion channel',exact=True)).to_be_focused()
        print('PASS: keyboard selection, empty results and Escape',flush=True)

        comparison.get_by_role('button',name='Add comparison channel',exact=True).click()
        comparison.get_by_role('combobox',name='Search comparison channels',exact=True).fill('27')
        comparison.get_by_role('option').click()
        expect(app).to_have_attribute('data-comparisons','[0]',timeout=30000);ready(app)
        assert app.locator('[data-plot="profile"]').evaluate('(g)=>g.data.length')==2
        app.get_by_role('button',name='Clear comparisons',exact=True).click()
        expect(app).to_have_attribute('data-comparisons','[]',timeout=30000);ready(app)
        assert app.locator('[data-plot="profile"]').evaluate('(g)=>g.data.length')==1
        assert not errors,errors
        print('PASS: searchable comparison and clearing the second curve',flush=True)

        primary.get_by_role('button',name='Choose ion channel',exact=True).click()
        search.fill('193.95')
        page.screenshot(path='/private/tmp/tof-peak-picker.png')
    except Exception:
        page.screenshot(path='/private/tmp/tof-peak-picker-failure.png');raise
    finally:browser.close()
