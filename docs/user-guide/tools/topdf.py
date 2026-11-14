import pathlib, sys
from playwright.sync_api import sync_playwright
src = pathlib.Path(sys.argv[1]).resolve(); out = pathlib.Path(sys.argv[2]).resolve()
# Footer title: an optional third argument, else the Vietnamese guide's.
title = sys.argv[3] if len(sys.argv) > 3 else 'Loan Workflow · Hướng dẫn sử dụng'
footer = ('<div style="width:100%;font-family:Segoe UI,Arial;font-size:8px;color:#5b6272;padding:0 16mm;'
          'display:flex;justify-content:space-between"><span>' + title + '</span>'
          '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge'); pg = b.new_page()
    pg.goto(src.as_uri(), wait_until='networkidle')
    pg.pdf(path=str(out), format='A4', print_background=True, prefer_css_page_size=True,
           display_header_footer=True, header_template='<div></div>', footer_template=footer,
           margin={'top': '18mm', 'bottom': '20mm', 'left': '16mm', 'right': '16mm'}, outline=True, tagged=True)
    b.close()
print(out, out.stat().st_size // 1024, 'KB')
