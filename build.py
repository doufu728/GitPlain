#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build.py — GitPlain 站点生成器（可重复运行）

输入：data_full.json（65,856 条完整数据）+ templates/*.html
输出：
    index.html                       首页（叙事页，真实数据内联）
    browse.html                      全部项目（首屏 10 条内联，其余分页拉取）
    repo/{owner}/{name}/index.html   项目详情页（stars > 10000）
    data/page-{n}.json               全量分片（每片 10 条）
    data/f/{cid}-{n}.json            分类分片
    data/s/{char}.json               搜索索引（按仓库名首字符分片）
    data/cats.json                   分类元数据
    data/weekly.json                 本周涨星榜前 100
    data/weekly-last.json            上一版周榜快照（自动归档，用于「上周」开关）
    sitemap.xml                      全站地图

静态页面（不由本脚本生成，手写维护）：
    weekly.html / about.html / contact.html / 404.html

运行：  python build.py
"""
import json
import os
import re
import shutil
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, 'data_full.json')
TPL_DIR = os.path.join(HERE, 'templates')
PAGE_SIZE = 10
GT_STARS = 10000          # stars > 10000 → 独立详情页；<= 10000 → 弹层
SITE = 'https://www.gitplain.com'
VERSION = '20261103'

CAT_FIELDS = ('repo', 'owner', 'owner_avatar', 'category', 'desc_cn', 'who',
              'steps', 'stars', 'stars_week', 'lang', 'updated_at', 'url')


# ---------------------------------------------------------------- 基础工具
def esc(s):
    return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;') \
        .replace('>', '&gt;').replace('"', '&quot;')


def fmt(n):
    return '{:,}'.format(int(n or 0))


def js_json(obj):
    """内联进 <script> 的 JSON：转义 </ 防止提前闭合标签。"""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def read_tpl(name):
    with open(os.path.join(TPL_DIR, name), encoding='utf-8') as f:
        return f.read()


def fill(tpl, mapping):
    for k, v in mapping.items():
        tpl = tpl.replace('{{%s}}' % k, v)
    leftover = re.findall(r'\{\{[A-Z0-9_]+\}\}', tpl)
    if leftover:
        raise SystemExit('模板还有未替换的占位符：%s' % sorted(set(leftover)))
    return tpl


def detail_href(it):
    if (it.get('stars') or 0) > GT_STARS:
        return 'repo/%s/' % it['repo']
    return ''


# ---------------------------------------------------------------- 列表行（与 assets/site.js 的 rowHTML 一致）
def row_html(it, rank, mode='stars', base=''):
    href = (base + detail_href(it)) if detail_href(it) else ''
    avatar = esc(it.get('owner_avatar'))
    name = it.get('repo', '').split('/')[-1] if '/' in it.get('repo', '') else it.get('repo', '')
    gain_cls = 'gain-col' if mode == 'week' else 'gain-col gain-col--stars'
    if mode == 'week':
        main = '<span class="gain">+%s<span class="gain-unit">/周</span></span>' % fmt(it.get('stars_week'))
        sub = '<span class="stars">★ %s</span>' % fmt(it.get('stars'))
    else:
        main = '<span class="gain">%s</span>' % fmt(it.get('stars'))
        sub = ('<span class="stars">+%s/周</span>' % fmt(it.get('stars_week'))) if it.get('stars_week') \
            else '<span class="stars">本周无涨星</span>'
    rank_str = ('0%d' % rank) if rank < 10 else str(rank)
    bar = ' bar--1' if rank == 1 else (' bar--23' if rank <= 3 else '')
    rank_cls = 'rank--top' if rank <= 3 else 'rank--rest'
    name_attr = (' href="%s"' % href) if href else (' href="%s" target="_blank" rel="noopener"' % esc(it.get('url')))
    name_title = ' title="%s"' % esc(it.get('repo', ''))
    avatar_html = ('<img class="avatar" src="%s" alt="" loading="lazy" decoding="async" '
                   'onerror="this.style.visibility=\'hidden\'">' % avatar) if avatar \
        else '<span class="avatar avatar--blank" aria-hidden="true"></span>'
    return (
        '<li class="board-row%s" data-repo="%s" data-href="%s">'
        '<span class="bar%s" aria-hidden="true"></span>'
        '<span class="rank %s" aria-hidden="true">%s</span>'
        '<span class="sr-only">第 %d 名</span>'
        '<div class="body">'
        '<div class="body-head">%s<a class="repo-name"%s%s>%s</a>'
        '<span class="cat">%s</span>'
        '<span class="owner">开发者：%s</span>'
        '</div>'
        '<p class="desc">%s</p>'
        '<p class="who">'
        '<span class="who-owner">开发者：%s</span>'
        '<span class="who-dot" aria-hidden="true"></span>'
        '<span class="who-fit">适合：%s</span>'
        '<span class="who-dot" aria-hidden="true"></span>'
        '<span class="who-stars">★ %s</span>'
        '</p>'
        '</div>'
        '<div class="%s">%s%s</div>'
        '<button class="fav-toggle" type="button" data-fav="%s" aria-pressed="false" aria-label="收藏">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">'
        '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9-4.3-4.1 5.9-.9z"/></svg>'
        '</button>'
        '<a class="visit" href="%s" target="_blank" rel="noopener">打开'
        '<svg class="ext" width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">'
        '<path d="M5 3h6v6M11 3 4 10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        '</a>'
        '</li>'
    ) % (
        ' board-row--top1' if rank == 1 else '', esc(it['repo']), esc(href),
        bar, rank_cls, rank_str, rank,
        avatar_html, name_attr, name_title, esc(name),
        esc(it.get('category')), esc(it.get('owner')),
        esc(it.get('desc_cn')),
        esc(it.get('owner')), esc(it.get('who')), fmt(it.get('stars')),
        gain_cls, main, sub,
        esc(it['repo']), esc(it.get('url')),
    )


# ---------------------------------------------------------------- 发现页任务
# 每个任务：(slug, 场景名, 任务标题, 简介, 筛选方式, 筛选值)
# 筛选方式：'q' = 关键词模糊匹配 repo名/中文说明/分类；'cat' = 精确匹配分类名
TASKS = [
    ('video-cut',      '视频与音频', '剪掉不要的片段', '不重新渲染、几秒就导出，画质一点不掉', 'q', '剪辑'),
    ('video-compress', '视频与音频', '把视频压缩变小', '体积太大发不出去？压到能传的尺寸还不糊', 'q', '压缩'),
    ('video-subtitle', '视频与音频', '自动加字幕', '把视频里的说话内容转成文字、配上字幕', 'q', '字幕'),
    ('video-download', '视频与音频', '下载网页视频', '把网页上的视频、音频扒下来存到本地', 'cat', '音视频'),
    ('data-clean',     '表格与数据', '清洗整理表格', '合并、去重、拆列，把乱糟糟的表一键理顺', 'q', '表格'),
    ('data-excel',     '表格与数据', '做 Excel 报表', '不用会写公式，也能批量处理 Excel 文件', 'q', 'excel'),
    ('data-chart',     '表格与数据', '画图表', '把一堆数字变成看得懂的柱状图、折线图', 'q', '图表'),
    ('data-scrape',    '表格与数据', '抓网页数据', '把网页上的信息批量抓下来，存成表格', 'q', '爬虫'),
    ('design-fix',     '图片与设计', '修图去水印', '去水印、抠背景、美化照片，不用会 PS', 'q', '修图'),
    ('design-poster',  '图片与设计', '做海报封面', '做活动海报、公众号封面、宣传图', 'q', '海报'),
    ('design-logo',    '图片与设计', '生成 Logo', '给项目、店铺做个像样的标志，不用找设计师', 'q', 'logo'),
    ('design-image',   '图片与设计', '生成配图', '写一句话，让 AI 帮你生成需要的图片', 'q', '图片'),
    ('auto-file',      '重复工作自动化', '批量处理文件', '批量改文件名、转换格式、整理文件夹', 'q', '自动化'),
    ('auto-schedule',  '重复工作自动化', '定时抓数据', '设定时间自动去网页上取最新数据', 'q', '爬虫'),
    ('auto-ai',        '重复工作自动化', '让 AI 写文案', '写文案、总结、翻译，让 AI 帮你动笔', 'q', 'ai'),
    ('learn-frontend', '学点新东西', '学做网页（前端）', '从零学会写网页、做界面，有系统学习路线', 'q', '前端'),
    ('learn-backend',  '学点新东西', '学做后端', '学会搭服务、写接口，让网站真正跑起来', 'q', '后端'),
    ('learn-tutorial', '学点新东西', '看教程清单', '别人整理好的免费教程、书单、学习资源合集', 'q', '教程'),
    ('learn-note',     '学点新东西', '做笔记整理', '记笔记、建知识库，把学到的东西沉淀下来', 'q', '笔记'),
]
TASK_TOP = 30  # 每个任务页最多展示的项目数


def task_match(it, mode, value):
    """判断项目是否属于某个任务。"""
    if mode == 'cat':
        return (it.get('category') or '') == value
    # 'q' 关键词：在 repo 名 + 中文说明 + 分类 里模糊匹配
    v = value.lower()
    hay = ' '.join([
        it.get('repo') or '',
        it.get('desc_cn') or '',
        it.get('desc') or '',
        it.get('category') or '',
    ]).lower()
    return v in hay


def build_tasks(items):
    """为每个任务生成独立内容页 discover/<slug>.html，返回 (task_slugs, 页面总数)。"""
    tpl = read_tpl('task.html')
    task_dir = os.path.join(HERE, 'discover')
    if os.path.isdir(task_dir):
        shutil.rmtree(task_dir)
    os.makedirs(task_dir, exist_ok=True)

    count = 0
    for slug, scene, title, lead, mode, value in TASKS:
        matched = [it for it in items if task_match(it, mode, value)]
        matched.sort(key=lambda x: (-(x.get('stars') or 0), x.get('repo') or ''))
        shown = matched[:TASK_TOP]
        rows = ''.join(row_html(it, i + 1, 'stars', '../') for i, it in enumerate(shown))
        html = fill(tpl, {
            'TITLE': esc(title),
            'LEAD': esc(lead),
            'SCENE': esc(scene),
            'COUNT': fmt(len(matched)),
            'CANON': '%s/discover/%s.html' % (SITE, slug),
            'ROWS': rows,
        })
        with open(os.path.join(task_dir, slug + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        count += 1
    return count


# ---------------------------------------------------------------- 首页区块
def hero_tags_html():
    tag_list = [('剪视频', '剪视频'), ('表格', '表格'), ('语音转文字', '语音转文字'), ('修图', '修图')]
    return '\n'.join(
        '        <button class="tag" type="button" data-q="%s">%s</button>' % (esc(q), esc(label))
        for q, label in tag_list
    )


def compare_html(items):
    """招牌对照：用真实项目 mifi/lossless-cut 的英文原话与中文翻译。"""
    by_repo = {it['repo']: it for it in items}
    it = by_repo.get('mifi/lossless-cut')
    if not it:
        # 兜底：取英文简介里含 editing 的最高星项目
        cand = [x for x in items if 'editing' in (x.get('desc') or '').lower()]
        it = cand[0] if cand else items[0]
    en = (it.get('desc') or '').strip()
    if len(en) > 160:
        en = en[:157].rstrip() + '…'
    steps = (it.get('steps') or [])[:2]
    points = '\n'.join(
        '            <div class="cmp-point">'
        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">'
        '<circle cx="8" cy="8" r="7" fill="#E8F1FC"/>'
        '<path d="M5 8.2 7 10.2 11 6" stroke="#0066CC" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg><span>%s</span></div>' % esc(s)
        for s in steps
    )
    meta = '<span>★ %s</span><span>%s</span>' % (fmt(it.get('stars')), esc(it.get('lang') or '—'))
    return {
        'CMP_REPO': esc(it['repo']),
        'CMP_EN': esc(en),
        'CMP_META': meta,
        'CMP_CN': esc(it.get('desc_cn')),
        'CMP_POINTS': points,
        'CMP_URL': esc(it.get('url')),
    }


SCENES = [
    # (锚点名, 真实分类, 一句话说明, 图标 SVG)
    ('视频与音频', '音视频',
     '剪片、转码、配音、下载，把视频音频处理利索',
     '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
     '<rect x="2" y="5" width="20" height="14" rx="3" stroke="currentColor" stroke-width="1.6"/>'
     '<path d="M10 9.5v5l4.5-2.5L10 9.5Z" fill="currentColor"/></svg>'),
    ('表格与数据', '数据分析',
     '清洗表格、做报表、画图表，不用手工一格格改',
     '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
     '<rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.6"/>'
     '<path d="M3 9h18M9 9v11" stroke="currentColor" stroke-width="1.6"/></svg>'),
    ('图片与设计', '设计 / UI',
     '做封面、修图、生成配图，不会设计软件也能出图',
     '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
     '<rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.6"/>'
     '<circle cx="8.5" cy="9.5" r="1.5" fill="currentColor"/>'
     '<path d="M3 17l5-5 4 4 3-3 6 6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>'),
    ('重复工作自动化', 'AI 应用',
     '定时抓数据、批量改文件名，让机器替你做重复动作',
     '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
     '<path d="M4 8h12M16 8l-3-3M16 8l-3 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
     '<path d="M20 16H8M8 16l3-3M8 16l3 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
    ('学点新东西', '学习资源',
     '教程、清单、学习路线，从零开始学一门手艺',
     '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
     '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5V5.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
     '<path d="M8 7h7M8 11h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'),
]


def scene_card_html(scene, cat):
    name, cat_name, desc, icon = scene
    cnt = cat.get('count') or 0
    href = 'browse.html?cat=%s' % quote(cat_name)
    return (
        '        <a class="cat-card" href="%s">%s'
        '<h3 class="cat-name">%s</h3>'
        '<p class="cat-desc">%s</p>'
        '<span class="cat-count">%s 个项目 <span aria-hidden="true">·</span> <span class="cat-enter">看看</span></span>'
        '</a>'
    ) % (href, icon, esc(name), esc(desc), fmt(cnt))


def cat_chips_html(cats):
    return '\n'.join(
        '          <a class="cat-chip" href="browse.html?cat=%s">%s <span class="n">%s</span></a>'
        % (quote(c['name']), esc(c['name']), fmt(c['count']))
        for c in cats
    )


def proj_card_html(it, big=True):
    name = it['repo'].split('/', 1)[1]
    href = detail_href(it) or it.get('url')
    cta = (
        '<span class="p-cta">看懂它'
        '<svg viewBox="0 0 13 13" fill="none" aria-hidden="true">'
        '<path d="M2 6.5h9M7.5 3l3.5 3.5L7.5 10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg></span>'
    ) if big else (
        '<span class="p-link">看懂它'
        '<svg viewBox="0 0 13 13" fill="none" aria-hidden="true">'
        '<path d="M2 6.5h9M7.5 3l3.5 3.5L7.5 10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg></span>'
    )
    metas = ['<span class="w">+%s/周</span>' % fmt(it.get('stars_week')), '<span>★ %s</span>' % fmt(it.get('stars'))]
    if big:
        metas.insert(0, '<span>开发者：%s</span>' % esc(it.get('owner')))
    return (
        '        <a class="p-card%s" href="%s">'
        '<div class="p-preview"><img class="p-avatar" src="%s" alt="" loading="lazy"></div>'
        '<div class="p-body">'
        '<h3 class="p-name">%s</h3>'
        '<p class="p-desc">%s</p>'
        '<div class="p-meta">%s</div>'
        '%s'
        '</div></a>'
    ) % (
        '' if big else ' p-card--sm', esc(href), esc(it.get('owner_avatar')),
        esc(name), esc(it.get('desc_cn')), ''.join(metas), cta,
    )


# ---------------------------------------------------------------- 详情页
def detail_html(it, tpl):
    name = it['repo'].split('/', 1)[1]
    desc_cn = it.get('desc_cn') or ''
    short = desc_cn[:30].rstrip('，。') + ('…' if len(desc_cn) > 30 else '')
    title = '%s · %s - GitPlain' % (it['repo'], short)
    canon = '%s/repo/%s/' % (SITE, it['repo'])
    steps = ''.join('<li>%s</li>' % esc(s) for s in (it.get('steps') or []))
    lang = esc(it.get('lang')) if it.get('lang') else '—'
    upd = (it.get('pushed_at') or it.get('updated_at') or '')[:10]
    week = it.get('stars_week') or 0
    item = {k: it.get(k) for k in CAT_FIELDS}
    item['pushed_at'] = it.get('pushed_at')
    return fill(tpl, {
        'TITLE': esc(title),
        'DESC': esc(desc_cn),
        'CANON': esc(canon),
        'AVATAR': esc(it.get('owner_avatar')),
        'REPO_NAME': esc(name),
        'CATEGORY': esc(it.get('category')),
        'DESC_CN': esc(desc_cn),
        'WHO': esc(it.get('who')),
        'OWNER': esc(it.get('owner')),
        'STEPS': steps,
        'STARS_WEEK': ('+%s' % fmt(week)) if week else '—',
        'STARS': fmt(it.get('stars')),
        'LANG': lang,
        'UPDATED': esc(upd),
        'URL': esc(it.get('url')),
        'REPO': esc(it['repo']),
        'CAT_ENC': quote(it.get('category') or ''),
        'ITEM_JSON': js_json(item),
    })


# ---------------------------------------------------------------- 页面组装
def build_index(items, cats, weekly, total, updated, tpl):
    cat_by_name = {c['name']: c for c in cats}
    scenes = [(s[0], s[1], s[2], s[3]) for s in SCENES if s[1] in cat_by_name]
    wide = '\n'.join(scene_card_html(s, cat_by_name[s[1]]) for s in scenes[:2])
    thirds = '\n'.join(scene_card_html(s, cat_by_name[s[1]]) for s in scenes[2:5])
    top3 = weekly[:3]
    proj = proj_card_html(top3[0], True) if top3 else ''
    for it in top3[1:]:
        proj += '\n' + proj_card_html(it, False)
    mapping = {
        'HERO_TAGS': hero_tags_html(),
        'SCENE_CARDS_WIDE': wide,
        'SCENE_CARDS_THIRDS': thirds,
        'CAT_CHIPS': cat_chips_html(cats),
        'PROJ_CARDS': proj,
        'TOTAL': fmt(total),
        'CAT_N': str(len(cats)),
        'UPDATED': esc(updated),
    }
    mapping.update(compare_html(items))
    return fill(tpl, mapping)


def build_browse(items, cats, total, updated, tpl):
    first = items[:PAGE_SIZE]
    cat_json = {'total': total, 'updated': updated,
                'cats': [{'id': c['id'], 'name': c['name'], 'count': c['count']} for c in cats]}
    return fill(tpl, {
        'TOTAL': fmt(total),
        'UPDATED': esc(updated),
        'CAT_OPTIONS': '\n'.join(
            '          <option value="%s" data-count="%s">%s</option>' % (esc(c['name']), fmt(c['count']), esc(c['name']))
            for c in cats),
        'FIRST_ROWS': ''.join(row_html(it, i + 1, 'stars') for i, it in enumerate(first)),
        'CATS_JSON': js_json(cat_json),
        'FIRST_JSON': js_json(first),
    })


def build_sitemap(items, updated):
    urls = ['%s/' % SITE, '%s/browse.html' % SITE, '%s/discover.html' % SITE,
            '%s/weekly.html' % SITE, '%s/about.html' % SITE, '%s/contact.html' % SITE]
    rows = '\n'.join(
        '  <url><loc>%s</loc><lastmod>%s</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>'
        % (esc(u), updated) for u in urls)
    task_rows = '\n'.join(
        '  <url><loc>%s/discover/%s.html</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>'
        % (SITE, esc(slug), updated)
        for slug, _s, _t, _l, _m, _v in TASKS)
    repo_rows = '\n'.join(
        '  <url><loc>%s/repo/%s/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>'
        % (SITE, esc(it['repo']), updated)
        for it in items if (it.get('stars') or 0) > GT_STARS
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            '%s\n%s\n%s\n</urlset>\n' % (rows, task_rows, repo_rows))


# ---------------------------------------------------------------- 主流程
def main():
    t0 = time.time()
    print('=' * 64)
    print('build.py · GitPlain 站点生成')
    print('=' * 64)

    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)
    items = data['items']
    items.sort(key=lambda x: (-(x.get('stars') or 0), x.get('repo') or ''))
    total = len(items)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    gt10k = [x for x in items if (x.get('stars') or 0) > GT_STARS]
    updated = (data.get('generated_at') or '')[:10]
    print('数据条数      %d' % total)
    print('分片数        %d（每片 %d 条）' % (pages, PAGE_SIZE))
    print('>10000 星     %d 个 → 独立详情页' % len(gt10k))
    print('数据日期      %s' % updated)

    # ---- 分类 ----
    cat_counts = {}
    for it in items:
        cat_counts[it['category']] = cat_counts.get(it['category'], 0) + 1
    cats = []
    for i, (name, count) in enumerate(sorted(cat_counts.items(), key=lambda kv: (-kv[1], kv[0])), 1):
        cats.append({'id': i, 'name': name, 'count': count,
                     'pages': (count + PAGE_SIZE - 1) // PAGE_SIZE})
    print('分类数        %d' % len(cats))

    # ---- 目录准备 ----
    data_dir = os.path.join(HERE, 'data')
    repo_dir = os.path.join(HERE, 'repo')
    # 周榜快照要在清空 data/ 之前读出来
    old_weekly = None
    wp = os.path.join(data_dir, 'weekly.json')
    if os.path.exists(wp):
        try:
            with open(wp, encoding='utf-8') as f:
                old_weekly = f.read()
        except OSError:
            old_weekly = None

    for d in (data_dir, repo_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    cat_dir = os.path.join(data_dir, 'f')
    os.makedirs(cat_dir)

    # ---- 分页分片 + 搜索索引 ----
    def shard_key(repo):
        c = (repo or '')[0:1].lower()
        if 'a' <= c <= 'z':
            return c
        if '0' <= c <= '9':
            return c
        return 'other'

    shards = {}
    print('\n写分片 + 搜索索引…')
    for n in range(1, pages + 1):
        chunk = items[(n - 1) * PAGE_SIZE: n * PAGE_SIZE]
        with open(os.path.join(data_dir, 'page-%d.json' % n), 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, separators=(',', ':'))
        for it in chunk:
            shards.setdefault(shard_key(it['repo']), []).append([
                it['repo'], it.get('desc_cn') or '', it.get('stars') or 0,
                it.get('stars_week') or 0, it.get('category') or '',
                it.get('who') or '', it.get('owner') or '',
                it.get('lang') or '', it.get('url') or '',
            ])

    s_dir = os.path.join(data_dir, 's')
    os.makedirs(s_dir, exist_ok=True)
    order = [chr(c) for c in range(ord('a'), ord('z') + 1)] + \
            [str(d) for d in range(10)] + ['other']
    index_meta = {}
    total_idx = 0
    for key in order:
        if key not in shards:
            continue
        with open(os.path.join(s_dir, key + '.json'), 'w', encoding='utf-8') as f:
            json.dump(shards[key], f, ensure_ascii=False, separators=(',', ':'))
        index_meta[key] = len(shards[key])
        total_idx += len(shards[key])
    with open(os.path.join(s_dir, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index_meta, f, ensure_ascii=False, separators=(',', ':'))
    print('  分片 %d 个 / 搜索分片 %d 个 / 索引 %d 条 ✓' % (pages, len(shards), total_idx))

    # ---- 周榜（先归档旧快照，再写新榜）----
    print('\n写榜单数据…')
    BOARD_FIELDS = ('repo', 'desc_cn', 'category', 'who', 'stars', 'owner',
                    'owner_avatar', 'lang', 'url', 'stars_week', 'pushed_at', 'steps', 'updated_at')
    week_pool = [it for it in items if (it.get('stars_week') or 0) > 0]
    week_pool.sort(key=lambda x: -(x.get('stars_week') or 0))
    weekly = []
    for it in week_pool[:100]:
        row = {k: it.get(k) for k in BOARD_FIELDS}
        weekly.append({k: v for k, v in row.items() if v is not None})
    if weekly:
        with open(os.path.join(data_dir, 'weekly.json'), 'w', encoding='utf-8') as f:
            json.dump(weekly, f, ensure_ascii=False, separators=(',', ':'))
        print('  weekly.json ✓ 前 %d 名，第 1 名 %s (+%s/周)'
              % (len(weekly), weekly[0]['repo'], fmt(weekly[0].get('stars_week'))))
    else:
        print('  weekly.json 跳过：没有 stars_week 数据')

    if old_weekly:
        try:
            prev = json.loads(old_weekly)
            prev_top = prev[0]['repo'] if prev else ''
            new_top = weekly[0]['repo'] if weekly else ''
            if prev and (prev_top != new_top or len(prev) != len(weekly)):
                with open(os.path.join(data_dir, 'weekly-last.json'), 'w', encoding='utf-8') as f:
                    f.write(old_weekly)
                print('  weekly-last.json ✓ 已归档上一版（第 1 名 %s）' % prev_top)
            else:
                print('  weekly-last.json 跳过：周榜没有变化')
        except (ValueError, KeyError, IndexError):
            print('  weekly-last.json 跳过：旧文件不可解析')

    # ---- 分类分片 ----
    print('写分类分片 %d 类…' % len(cats))
    by_cat = {c['name']: [] for c in cats}
    for it in items:
        by_cat[it['category']].append({k: it.get(k) for k in CAT_FIELDS})
    for c in cats:
        rows = by_cat[c['name']]
        for n in range(1, c['pages'] + 1):
            chunk = rows[(n - 1) * PAGE_SIZE: n * PAGE_SIZE]
            with open(os.path.join(cat_dir, '%d-%d.json' % (c['id'], n)), 'w', encoding='utf-8') as f:
                json.dump(chunk, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(data_dir, 'cats.json'), 'w', encoding='utf-8') as f:
        json.dump({'total': total, 'updated': updated, 'cats': cats},
                  f, ensure_ascii=False, separators=(',', ':'))
    print('  分类分片 %d 个 ✓' % sum(c['pages'] for c in cats))

    # ---- 详情页 ----
    print('写详情页 %d 个…' % len(gt10k))
    detail_tpl = read_tpl('detail.html')
    for i, it in enumerate(gt10k, 1):
        owner, name = it['repo'].split('/', 1)
        d = os.path.join(repo_dir, owner, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(detail_html(it, detail_tpl))
        if i % 1000 == 0:
            print('  … %d/%d' % (i, len(gt10k)))
    print('  详情页 %d 个 ✓' % len(gt10k))

    # ---- 发现页任务独立内容页 ----
    task_count = build_tasks(items)
    print('发现页任务内容页 %d 个 ✓' % task_count)

    # ---- 首页 / 全部项目 ----
    with open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_index(items, cats, weekly, total, updated, read_tpl('index.html')))
    print('首页 index.html ✓')

    with open(os.path.join(HERE, 'browse.html'), 'w', encoding='utf-8') as f:
        f.write(build_browse(items, cats, total, updated, read_tpl('browse.html')))
    print('全部项目 browse.html ✓')

    with open(os.path.join(HERE, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(build_sitemap(items, updated))
    print('sitemap.xml ✓')

    # ---- 体积汇总 ----
    def dir_size(p):
        tot = 0
        for root, _dirs, files in os.walk(p):
            for fn in files:
                tot += os.path.getsize(os.path.join(root, fn))
        return tot

    site_bytes = dir_size(data_dir) + dir_size(repo_dir) + dir_size(os.path.join(HERE, 'discover'))
    for a in ('index.html', 'browse.html', 'weekly.html', 'about.html', 'contact.html', '404.html'):
        p = os.path.join(HERE, a)
        if os.path.exists(p):
            site_bytes += os.path.getsize(p)
    for a in ('site.css', 'site.js'):
        p = os.path.join(HERE, 'assets', a)
        if os.path.exists(p):
            site_bytes += os.path.getsize(p)
    print('\n' + '-' * 64)
    print('站点体积      %.1f MB（data + repo + 页面 + assets）' % (site_bytes / 1024 / 1024))
    print('耗时          %.1f 秒' % (time.time() - t0))
    print('-' * 64)


if __name__ == '__main__':
    main()
