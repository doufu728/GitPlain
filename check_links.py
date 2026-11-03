# -*- coding: utf-8 -*-
"""一次性检查：全站内部链接、静态资源引用、SEO 基础标签。"""
import os
import re
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {'_archive', 'dist', '.git', 'data.bak', 'cache', 'tasks', 'ref', '__pycache__', 'templates'}
A_TAG = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.I)
SRC_TAG = re.compile(r'<(?:img|script|link)\b[^>]*\b(?:src|href)="([^"]*)"', re.I)


def walk_html():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('_')]
        for fn in files:
            if fn.endswith('.html'):
                yield os.path.join(base, fn)


def resolve(page, ref):
    if not ref or ref.startswith(('#', 'http://', 'https://', 'mailto:', 'javascript:', 'data:')):
        return None
    path = unquote(urlparse(ref).path)
    if not path:
        return None
    target = os.path.join(ROOT, path.lstrip('/')) if path.startswith('/') else os.path.join(os.path.dirname(page), path)
    if target.endswith(os.sep) or os.path.isdir(target):
        target = os.path.join(target, 'index.html')
    return os.path.normpath(target)


def main():
    pages = 0
    bad = []
    missing_seo = []
    for page in walk_html():
        pages += 1
        rel = os.path.relpath(page, ROOT)
        with open(page, encoding='utf-8') as f:
            html = f.read()
        for m in list(A_TAG.finditer(html)) + list(SRC_TAG.finditer(html)):
            ref = m.group(1)
            t = resolve(page, ref)
            if t and not os.path.exists(t):
                bad.append((rel, ref))
        if rel in ('index.html', 'browse.html', 'weekly.html', 'about.html', 'contact.html'):
            if '<link rel="canonical"' not in html:
                missing_seo.append((rel, 'canonical'))
            if '<meta name="description"' not in html:
                missing_seo.append((rel, 'description'))
        if 'assets/style.css' in html or 'assets/app.js' in html:
            bad.append((rel, '旧资源引用 style.css/app.js'))

    print('检查页面  %d 个' % pages)
    print('坏链接    %d 条' % len(bad))
    for rel, ref in bad[:25]:
        print('   ✗ %s → %s' % (rel, ref))
    print('缺 SEO    %d 项 %s' % (len(missing_seo), missing_seo[:5]))


if __name__ == '__main__':
    main()
