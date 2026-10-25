#!/usr/bin/env python3
"""Build TaskNest's static Pages site. Python standard library only."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
import re, shutil, os

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '_site'
# The workflow supplies the exact configured Pages base URL; local builds derive it
# from GITHUB_REPOSITORY, with this verified repository as the standalone default.
from urllib.parse import urlsplit
repository = os.environ.get('GITHUB_REPOSITORY', 'tasknestai/Tasknestai')
owner, repo = repository.split('/', 1)
default_url = 'https://' + owner.lower() + '.github.io/'
if repo.lower() != owner.lower() + '.github.io': default_url += repo + '/'
SITE_URL = os.environ.get('SITE_URL', default_url).rstrip('/') + '/'
parts = urlsplit(SITE_URL)
if parts.scheme != 'https' or not parts.netloc or parts.query or parts.fragment:
    raise RuntimeError('SITE_URL must be an absolute HTTPS site base URL')
START = '<!-- AUTO-GUIDES:START -->'
END = '<!-- AUTO-GUIDES:END -->'

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.heading = []; self.title = []; self.description = ''; self.noindex = False; self.h1 = False; self.in_title = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h1': self.h1 = True
        if tag == 'title': self.in_title = True
        if tag == 'meta':
            name = a.get('name', '').lower()
            if name == 'description': self.description = a.get('content', '')
            if name == 'robots' and 'noindex' in a.get('content', '').lower(): self.noindex = True
    def handle_endtag(self, tag):
        if tag == 'h1': self.h1 = False
        if tag == 'title': self.in_title = False
    def handle_data(self, data):
        if self.h1: self.heading.append(data)
        if self.in_title: self.title.append(data)

if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir()
for p in ROOT.iterdir():
    if p.name.startswith('.') or p.name in {'_site', 'build-guides.py', 'SETUP.txt'}: continue
    if p.is_dir(): shutil.copytree(p, OUT / p.name)
    else: shutil.copy2(p, OUT / p.name)

index = (ROOT / 'index.html').read_text(encoding='utf-8')
assert index.count(START) == index.count(END) == 1, 'Missing or duplicate automatic guide markers in index.html'
cards = []
clean_names = set()
for source in sorted(ROOT.glob('guide-*.html')):
    if source.name.lower() == 'guide-template.html':
        (OUT / source.name).unlink(missing_ok=True); continue
    body = source.read_text(encoding='utf-8')
    meta = Metadata(); meta.feed(body)
    if meta.noindex:
        (OUT / source.name).unlink(missing_ok=True); continue
    clean = source.name[len('guide-'):]
    if clean in clean_names or (ROOT / clean).exists(): raise RuntimeError('Clean URL collision: ' + clean)
    clean_names.add(clean)
    title = ' '.join(''.join(meta.heading or meta.title).split())
    title = re.sub(r'^guide[\s:_-]+', '', title, flags=re.I)
    if not title: title = source.stem[6:].replace('-', ' ')
    description = ' '.join(meta.description.split()) or 'इस विषय की जानकारी और चरणबद्ध मार्गदर्शन पढ़ें।'
    # Keep canonical and social URLs consistent with the published filename.
    body = body.replace(source.name, clean)
    # Replace stale Netlify host on this migrated site's own canonical/social URLs.
    for old_base in ['https://studenthelpclub.netlify.app/', 'https://testnestai.github.io/Testnestai/', 'https://testnestai.github.io/Tasknestai/']:
        body = body.replace(old_base, SITE_URL)
    (OUT / clean).write_text(body, encoding='utf-8')
    # Preserve bookmarks to the original guide filename without keeping duplicate articles.
    target = escape(clean, quote=True)
    redirect = '<!doctype html><html lang="hi"><meta charset="utf-8"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0;url='+target+'"><link rel="canonical" href="'+target+'"><title>लेख का नया पता</title><a href="'+target+'">लेख पढ़ें</a></html>'
    (OUT / source.name).write_text(redirect, encoding='utf-8')
    cards.append('<a lang="hi" class="service-card block bg-white rounded-2xl p-6 shadow-premium border border-gray-100 hover:shadow-premium-hover" href="'+target+'"><div class="icon-wrapper w-12 h-12 rounded-xl bg-gray-50 text-emerald-500 flex items-center justify-center text-xl mb-4 transition-colors" aria-hidden="true"><svg aria-hidden="true" class="inline-icon" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z M20 18v3H6.5a2.5 2.5 0 0 1 0-5"></path></svg></div><h4 class="text-lg font-bold text-gray-900 mb-2">'+escape(title)+'</h4><p class="text-sm text-gray-500">'+escape(description)+'</p></a>')
content = '\n'.join(cards) if cards else '<p class="text-gray-600">अभी कोई प्रकाशित गाइड उपलब्ध नहीं है।</p>'
a = index.index(START)+len(START); b = index.index(END)
(OUT / 'index.html').write_text(index[:a]+'\n'+content+'\n'+index[b:], encoding='utf-8')
(OUT / '.nojekyll').touch()
print('Built', len(cards), 'guide cards in _site; source files unchanged.')

# Automatic sitemap, based on files actually written to _site.
# Change SITE_URL only if the published host or repository path changes.
from urllib.parse import urljoin, urlsplit, quote
import xml.etree.ElementTree as ET
# SITE_URL was resolved once above, shared by guide canonicals and sitemap.
site_parts = urlsplit(SITE_URL)
if site_parts.scheme != 'https' or not site_parts.netloc or site_parts.query or site_parts.fragment:
    raise RuntimeError('SITE_URL must be an absolute HTTPS URL ending at the site folder')

class SitemapMetadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.noindex = False; self.redirect = False; self.canonical = None
    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): v or '' for k, v in attrs}
        if tag.lower() == 'meta':
            if attrs.get('name', '').lower() in {'robots', 'googlebot'} and re.search(r'\b(noindex|none)\b', attrs.get('content', ''), re.I):
                self.noindex = True
            if attrs.get('http-equiv', '').lower() == 'refresh': self.redirect = True
        if tag.lower() == 'link' and 'canonical' in attrs.get('rel', '').lower().split():
            self.canonical = attrs.get('href')

NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)
urlset = ET.Element('{' + NS + '}urlset')
urls = set()
for page in sorted(OUT.rglob('*.html')):
    relative = page.relative_to(OUT)
    if any(part.startswith('.') for part in relative.parts): continue
    if page.name.lower() in {'404.html', 'guide-template.html'}: continue
    details = SitemapMetadata(); details.feed(page.read_text(encoding='utf-8'))
    if details.noindex or details.redirect: continue
    path = relative.as_posix()
    if path == 'index.html': path = ''
    elif path.endswith('/index.html'): path = path[:-len('index.html')]
    location = urljoin(SITE_URL, quote(path, safe='/'))
    if details.canonical:
        canonical = urljoin(location, details.canonical)
        if canonical != location:
            # Treat /index.html and / as the same homepage, but exclude true duplicates
            # and pages whose canonical points outside this site's published base path.
            if canonical != location + 'index.html': continue
    if not location.startswith(SITE_URL): continue
    urls.add(location)
for location in sorted(urls):
    node = ET.SubElement(urlset, '{' + NS + '}url')
    ET.SubElement(node, '{' + NS + '}loc').text = location
# No fake lastmod timestamps, priorities or change frequencies.
ET.indent(urlset, space='  ')
ET.ElementTree(urlset).write(OUT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
print('Built sitemap.xml with', len(urls), 'canonical, indexable page URLs.')
