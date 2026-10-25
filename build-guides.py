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
