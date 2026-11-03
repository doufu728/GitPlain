#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_stars_week.py — 用 GH Archive 补「本周涨星」字段

原理：GH Archive 记录 GitHub 所有公开事件，WatchEvent 就是一次 star。
下载过去 N 天每小时的事件流（NDJSON.gz），流式统计每个 repo 的 WatchEvent 次数，
写进 data_full.json / data_zh.json 的 stars_week 字段。

用法：
    python fetch_stars_week.py --days 7          # 过去 7 天（默认到今天的前一天）
    python fetch_stars_week.py --start 2026-10-25 --end 2026-10-31
    python fetch_stars_week.py --clean           # 删除已下载的 gz 缓存，清空断点

特性：
    - 断点续跑：progress_stars.json 记录时间范围 + 已处理小时 + 累计结果，中断后接着跑
    - 流式解析：gzip.open 逐行读，先字符串预判 WatchEvent 再 json.loads（省 ~97% 解析）
    - 并发下载 5 线程，失败重试 3 次，仍失败记 failed_hours.json 不中断
    - 可复用：时间范围变了（下周再跑）自动从头统计
"""
import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = r'D:\小顾的hermes\工作资料\gharchive'  # 63GB，必须在 D 盘
DATA_FILE = os.path.join(HERE, 'data_full.json')
ZH_FILE = os.path.join(HERE, 'data_zh.json')
STARS_FILE = os.path.join(HERE, 'stars_week.json')
PROGRESS_FILE = os.path.join(HERE, 'progress_stars.json')
FAILED_FILE = os.path.join(HERE, 'failed_hours.json')

BASE = 'https://gharchive.open-digger.cn/'
UA = {'User-Agent': 'Mozilla/5.0 (GitPlain star counter)'}
CONCURRENCY = 8
RETRIES = 3


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


def hour_list(start, end):
    """[start, end] 之间所有小时，格式 YYYY-MM-DD-H"""
    out = []
    d = start
    while d <= end:
        for h in range(24):
            out.append('%s-%d' % (d.isoformat(), h))
        d += timedelta(days=1)
    return out


def cache_path(hour):
    return os.path.join(CACHE_DIR, hour + '.json.gz')


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


def download(hour):
    """下载单个小时文件，失败重试 RETRIES 次。返回 (hour, ok, reason)。"""
    url = BASE + hour + '.json.gz'
    path = cache_path(hour)
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=900) as r:
                with open(path + '.part', 'wb') as f:
                    while True:
                        chunk = r.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
            os.replace(path + '.part', path)
            return hour, True, ''
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return hour, False, '404'
            if attempt < RETRIES:
                time.sleep(attempt * 2)
                continue
            return hour, False, 'HTTP %s' % e.code
        except Exception as e:
            if attempt < RETRIES:
                time.sleep(attempt * 2)
                continue
            return hour, False, str(e)[:80]
    return hour, False, 'retry-exhausted'


def parse_hour(hour):
    """流式解析单个小时文件，只统计 WatchEvent，返回 {repo: count}"""
    counts = {}
    path = cache_path(hour)
    with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'WatchEvent' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get('type') == 'WatchEvent':
                repo = (e.get('repo') or {}).get('name')
                if repo:
                    counts[repo] = counts.get(repo, 0) + 1
    return counts


def merge(acc, counts):
    for k, v in counts.items():
        acc[k] = acc.get(k, 0) + v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--clean', action='store_true')
    args = ap.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)

    # --clean：删缓存 + 清空断点（结果已合并进 data_full.json，这里只清磁盘）
    if args.clean:
        removed = 0
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith('.json.gz'):
                os.remove(os.path.join(CACHE_DIR, fn))
                removed += 1
        for p in (PROGRESS_FILE, FAILED_FILE):
            if os.path.exists(p):
                os.remove(p)
        print('--clean 删除 %d 个 gz 缓存，断点已清空' % removed)
        return

    # 时间范围：默认 end = 昨天（今天的文件可能没生成全），start = end - (days-1)
    end = parse_date(args.end) if args.end else (datetime.now(timezone.utc).date() - timedelta(days=1))
    start = parse_date(args.start) if args.start else end - timedelta(days=args.days - 1)
    hours = hour_list(start, end)
    print('时间范围 %s ~ %s，共 %d 个小时文件' % (start, end, len(hours)))

    # 断点续跑：时间范围一致才恢复，否则从头
    prog = load_json(PROGRESS_FILE, {'start': None, 'end': None, 'done': [], 'stars': {}})
    same_range = (prog.get('start') == start.isoformat() and prog.get('end') == end.isoformat())
    done = set(prog.get('done', [])) if same_range else set()
    stars = prog.get('stars', {}) if same_range else {}
    failed = load_json(FAILED_FILE, [])
    print('断点：已处理 %d 小时，已累计 %d 个 repo（%s）' % (
        len(done), len(stars), '续跑' if same_range else '新范围从头'))

    # ---- 每线程独立跑「下载→解析→删」：下载不再等解析，吞吐翻倍 ----
    todo = [h for h in hours if h not in done]
    print('待处理 %d 个（每线程独立 下载+解析+删，峰值磁盘 ~%d MB）' % (len(todo), CONCURRENCY * 450))
    t0 = time.time()
    total_stars = sum(stars.values())
    new_failed = []
    processed = 0

    def process_one(h):
        _, ok, reason = download(h)
        if not ok:
            return h, False, None, reason
        try:
            counts = parse_hour(h)
        except Exception as e:
            return h, False, None, 'parse: ' + str(e)[:60]
        try:
            os.remove(cache_path(h))   # 边下边删
        except OSError:
            pass
        return h, True, counts, ''

    if todo:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futs = {pool.submit(process_one, h): h for h in todo}
            for fut in as_completed(futs):
                h, ok, counts, reason = fut.result()
                if not ok:
                    new_failed.append({'hour': h, 'reason': reason})
                    continue
                for k, v in counts.items():
                    stars[k] = stars.get(k, 0) + v
                    total_stars += v
                done.add(h)
                processed += 1
                if processed % 10 == 0:
                    print('[%d/%d] %s done, 累计 %d stars (%.0fs)' % (
                        len(done), len(hours), h, total_stars, time.time() - t0), flush=True)
                    save_json(PROGRESS_FILE, {'start': start.isoformat(), 'end': end.isoformat(),
                                              'done': sorted(done), 'stars': stars})
    failed = [f for f in failed if f['hour'] not in hours] + new_failed
    save_json(FAILED_FILE, failed)
    print('处理完成 %.0f 秒，共 %d 个 repo 有 star，总 star 事件 %d，失败 %d' % (
        time.time() - t0, len(stars), total_stars, len(new_failed)), flush=True)

    # ---- 保存 ----
    save_json(PROGRESS_FILE, {'start': start.isoformat(), 'end': end.isoformat(),
                              'done': sorted(done), 'stars': stars})
    save_json(STARS_FILE, stars)
    print('stars_week.json 已保存（%d 个 repo）' % len(stars))

    # ---- 合并到 data_full.json ----
    print('合并到 data_full.json ...', flush=True)
    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)
    items = data['items']
    filled = 0
    for it in items:
        it['stars_week'] = stars.get(it['repo'], 0)
        filled += 1
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print('data_full.json 已更新（%d 条全部补 stars_week）' % filled)

    # ---- 同步 data_zh.json ----
    if os.path.exists(ZH_FILE):
        with open(ZH_FILE, encoding='utf-8') as f:
            zh = json.load(f)
        zitems = zh['items'] if isinstance(zh, dict) else zh
        n = 0
        for it in zitems:
            it['stars_week'] = stars.get(it['repo'], 0)
            n += 1
        with open(ZH_FILE, 'w', encoding='utf-8') as f:
            json.dump(zh, f, ensure_ascii=False)
        print('data_zh.json 已同步（%d 条）' % n)

    # ---- 异常小时报告 ----
    if failed:
        print('异常小时 %d 个：' % len(failed))
        for f in failed[:30]:
            print('  %s: %s' % (f['hour'], f['reason']))
    print('DONE')


if __name__ == '__main__':
    main()
