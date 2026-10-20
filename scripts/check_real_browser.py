"""Read-only browser qualification of a packaged/source application on one file."""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--also-open", type=Path)
    p.add_argument("--frame-samples", type=int, default=12)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        log = (a.output / "server.log").open("w")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "tofscope.cli",
                "serve",
                "--no-browser",
                "--data-root",
                str(a.file.parent),
                "--runtime-dir",
                d,
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(url + "/readyz", timeout=0.5).close()
                    break
                except OSError:
                    time.sleep(0.1)
            secret = json.loads((Path(d) / "launch.json").read_text())["secret"]
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1660, "height": 1100})
                errors = []
                requests = []
                page.on("request", lambda request: requests.append((request.method, request.url)))
                page.on("pageerror", lambda e: errors.append(str(e)))
                external = []

                def route(r):
                    if r.request.url.startswith(url) or r.request.url.startswith(
                        ("blob:", "data:")
                    ):
                        r.continue_()
                    else:
                        external.append(r.request.url)
                        r.abort()

                page.route("**/*", route)
                page.goto(url + "/#bootstrap=" + secret)
                page.get_by_role("button", name="Open TOFexplorer (.h5) file").click()
                page.get_by_label("Search files").fill(a.file.name)
                t = time.perf_counter()
                page.get_by_role("button", name="◫ " + a.file.name, exact=True).dblclick()
                page.get_by_test_id("panel-front").locator("canvas").first.wait_for(
                    timeout=30000
                )
                page.get_by_test_id("panel-spectrum").locator("canvas").first.wait_for(
                    timeout=30000
                )
                page.get_by_role("button", name="Add signal").click()
                signal_list = page.get_by_role("listbox", name="Stored signals")
                signal_list.wait_for()
                signal_count = signal_list.get_by_role("option").count()
                signal_list_height = signal_list.evaluate(
                    "element => element.getBoundingClientRect().height"
                )
                assert signal_list_height <= 200
                page.get_by_label("Search stored signals").fill("27")
                matching_signals = signal_list.get_by_role("option").count()
                assert 0 < matching_signals < signal_count
                page.get_by_label("Search stored signals").fill("")
                page.keyboard.press("Escape")
                load_ms = (time.perf_counter() - t) * 1000
                page.get_by_role('button', name='Add signal', exact=True).click()
                page.get_by_role('listbox', name='Stored signals').get_by_role('option').first.click()
                from playwright.sync_api import expect
                page.get_by_role("button", name="Manage signals", exact=True).click()
                rows = page.get_by_test_id('signal-row')
                expect(rows).to_have_count(2)
                expect(page.get_by_test_id('panel-profile').get_by_role('listitem')).to_have_count(2)
                requests.clear()
                switch_start = time.perf_counter()
                image_before = page.get_by_test_id('panel-ion').get_attribute('data-content-version')
                rows.last.get_by_role('radio').click()
                page.wait_for_function("old=>document.querySelector('[data-testid=panel-ion]').dataset.contentVersion!==old", arg=image_before)
                switch_ms = (time.perf_counter()-switch_start)*1000
                assert not any(method=='POST' and url.endswith('/jobs') for method,url in requests)
                assert not any('spectrum' in url for _,url in requests if '/data?' in url)
                page.get_by_role("button", name="Close Manage signals", exact=True).click()
                resize_timings = {}
                for name in ("ion", "front"):
                    panel = page.get_by_test_id("panel-" + name)
                    measurements = []
                    for _ in range(3):
                        for action in ("maximize", "restore"):
                            elapsed = panel.evaluate("""async (el) => {
                                const start = performance.now();
                                el.querySelector('button[aria-label^="Maximize"],button[aria-label^="Restore"]').click();
                                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                                return performance.now() - start;
                            }""")
                            measurements.append({"action": action, "ms": elapsed})
                    resize_timings[name] = measurements
                timings = []
                page.get_by_role('button', name='Analysis settings', exact=True).click()
                first_frame = int(page.get_by_label('Analysis first', exact=True).input_value())
                last_frame = int(page.get_by_label('Analysis last', exact=True).input_value())
                page.keyboard.press('Escape')
                for _ in range(min(a.frame_samples, last_frame - first_frame)):
                    revision = page.get_by_test_id("analysis-revision").inner_text()
                    image_before = page.get_by_test_id("panel-ion").get_attribute("data-content-version")
                    t = time.perf_counter()
                    page.get_by_role("button", name="Next frame", exact=True).click()
                    page.wait_for_function(
                        "old=>document.querySelector('[data-testid=analysis-revision]').textContent!==old",
                        arg=revision,
                    )
                    page.wait_for_function("old=>document.querySelector('[data-testid=panel-ion]').dataset.contentVersion!==old", arg=image_before)
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    timings.append((time.perf_counter() - t) * 1000)
                page.screenshot(path=str(a.output / "real-explore.png"), full_page=True)
                if a.also_open:
                    page.get_by_role("button", name="＋ Open TOFexplorer file").click()
                    page.get_by_label("Search files").fill(a.also_open.name)
                    page.get_by_role(
                        "button", name="◫ " + a.also_open.name, exact=True
                    ).dblclick()
                    second_tab = page.get_by_role(
                        "tab", name="2 · " + a.also_open.name
                    )
                    try:
                        second_tab.wait_for(timeout=30000)
                    except Exception:
                        page.screenshot(path=str(a.output / 'multi-open-timeout.png'), full_page=True)
                        print(json.dumps({'tabs': page.get_by_role('tab').all_text_contents(), 'alerts': page.get_by_role('alert').all_text_contents()}),flush=True)
                        raise
                    tabs = page.get_by_role("tab").all_text_contents()
                    if len(tabs) != 2:
                        page.screenshot(path=str(a.output / "multi-open-failure.png"), full_page=True)
                    assert len(tabs) == 2, f"Expected two independent analyses, got tabs: {tabs}"
                    second_tab.click()
                    active_screen = page.locator(".explore-screen:visible")
                    active_screen.get_by_test_id("panel-ion").locator("canvas").first.wait_for(
                        state="visible", timeout=30000
                    )
                    page.get_by_role("tab", name="1 · " + a.file.name).click()
                    assert page.get_by_role(
                        "heading", name=a.file.name
                    ).is_visible()
                assert not errors, errors
                assert not external, external
                result = {
                    "initial_four_panels_ms": load_ms,
                    "resident_stored_signal_switch_ms": switch_ms,
                    "resident_switch_reintegration_jobs": 0,
                    "resident_switch_spectrum_refetches": 0,
                    "image_resize_timings": resize_timings,
                    "frame_step_p50_ms": sorted(timings)[len(timings) // 2] if timings else None,
                    "frame_step_p95_ms": sorted(timings)[min(len(timings) - 1, int(len(timings) * 0.9))] if timings else None,
                    "frame_step_samples": len(timings),
                    "offline": True,
                    "browser_errors": errors,
                    "stored_signal_options": signal_count,
                    "signal_picker_height_px": signal_list_height,
                    "opened_distinct_files": bool(a.also_open),
                }
                (a.output / "browser.json").write_text(json.dumps(result, indent=2))
                print(json.dumps(result))
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == "__main__":
    main()
