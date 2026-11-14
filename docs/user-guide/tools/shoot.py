"""shoot.py <out_dir> <spec.json>: screenshots of the local app as the demo users."""
import json, os, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(__file__)
sessions = json.load(open(os.path.join(HERE, 'sessions.json')))
out_dir, spec = sys.argv[1], json.load(open(sys.argv[2], encoding='utf-8'))
os.makedirs(out_dir, exist_ok=True)
BASE = 'http://localhost:8000'
CLICK_TAB = """(text) => {
  const norm = t => t.replace(/\s+/g, ' ').trim();
  const all = [...document.querySelectorAll('a, button')];
  const el = all.find(a => norm(a.textContent) === text) || all.find(a => norm(a.textContent).startsWith(text + ' ') || norm(a.textContent).endsWith(' ' + text));
  if (!el) throw new Error('no tab ' + text); el.click(); }"""
UNSTICK = """() => { for (const el of document.querySelectorAll('body *')) {
  const p = getComputedStyle(el).position;
  if ((p === 'sticky' || p === 'fixed') && el.getBoundingClientRect().top > 300) el.style.position = 'static'; } }"""

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge')
    contexts = {}
    for shot in spec:
        user, width, height = shot['user'], shot.get('width', 1440), shot.get('height', 900)
        key = (user, width, height)
        if key not in contexts:
            ctx = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=2,
                                      locale='vi-VN')
            if user != 'anon':
                ctx.add_cookies([{'name': 'sessionid', 'value': sessions[user], 'domain': 'localhost', 'path': '/'}])
            contexts[key] = ctx
        ctx = contexts[key]
        path = os.path.join(out_dir, shot['name'] + '.png')
        if shot.get('pdf'):
            data = ctx.request.get(BASE + shot['url']).body()
            import fitz
            doc = fitz.open(stream=data, filetype='pdf')
            doc[0].get_pixmap(dpi=110).save(path)
            print('saved', shot['name'], 'pdf pages', doc.page_count)
            continue
        page = ctx.new_page()
        page.goto(BASE + shot['url'], wait_until='networkidle')
        for tab in shot.get('tabs', []):
            page.evaluate(CLICK_TAB, tab)
            page.wait_for_timeout(300)
        if shot.get('click'):
            page.click(shot['click']); page.wait_for_timeout(400)
        if shot.get('js'):
            page.evaluate(shot['js']); page.wait_for_timeout(300)
        if shot.get('full'):
            page.evaluate(UNSTICK)
        page.screenshot(path=path, full_page=shot.get('full', False))
        print('saved', shot['name'])
        page.close()
    browser.close()
