#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_pushed_at.py — 用 GitHub GraphQL 批量补「最后推送时间」pushed_at

背景：data_full.json 里的 updated_at 是假的（4 个项目值全挤在抓取那一刻 10-31 21:1x）。
GitHub 的 updated_at 是「仓库对象最后刷新时间」，不是创作者的时间；真正反映活跃度的是
pushed_at（最后一次 push）。

实现要点：
- GraphQL 批量：一次查 BATCH(默认 50) 个 repo（r0/r1/... 别名），每个查询固定消耗 1 点配额
  （实测：1 个、10 个、20 个 repo 的查询 cost 都是 1）
- 断点续跑：进度存 pushed_at_progress.json（results 字典），中断后跳过已完成的 repo
- 限流：每个查询内嵌 rateLimit{cost remaining resetAt} 字段，剩余 < 阈值时主动等到 reset；
  遇到 403/429 时读 X-RateLimit-Reset 响应头等
- 并发 CONCURRENCY(默认 3) 个 worker

用法：
    python fetch_pushed_at.py                 # 全量 65,856 个
    python fetch_pushed_at.py --limit 20      # 小样本测试（只跑前 20 个）
    python fetch_pushed_at.py --batch 100     # 每批 100 个
    python fetch_pushed_at.py --concurrency 2
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, 'data_full.json')
OUT_FILE = os.path.join(HERE, 'pushed_at.json')
PROGRESS_FILE = os.path.join(HERE, 'pushed_at_progress.json')

API = 'https://api.github.com/graphql'
BATCH = 50
CONCURRENCY = 3
UA = {'User-Agent': 'GitPlain pushed_at fetcher', 'Accept': 'application/json'}

_token = None
_rl_lock = threading.Lock()
_rl = {'remaining': 5000, 'reset_epoch': time.time() + 3600}


def get_token():
    global _token
    if _token:
        return _token
    for var in ('GITHUB_TOKEN', 'GH_TOKEN'):
        v = os.environ.get(var)
        if v:
            _token = v
            return _token
    try:
        out = subprocess.run(['gh', 'auth', 'token'],
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            _token = out.stdout.strip()
            return _token
    except Exception:
        pass
    return None


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def iso_to_epoch(s):
    # GraphQL resetAt 形如 '2026-11-01T17:34:32Z'
    try:
        return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(
            tzinfo=timezone.utc).timestamp()
    except Exception:
        return time.time() + 3600


def throttle():
    """配额快用完时主动等到 reset。"""
    with _rl_lock:
        if _rl['remaining'] < 10:
            wait = _rl['reset_epoch'] - time.time() + 5
            if wait > 0:
                print('  [限流] 配额即将用尽，等待 %.0f 秒到 reset ...' % wait, flush=True)
                time.sleep(wait)
            _rl['remaining'] = 5000


def update_ratelimit(remaining, reset_at):
    with _rl_lock:
        _rl['remaining'] = remaining
        _rl['reset_epoch'] = iso_to_epoch(reset_at) if reset_at else time.time() + 3600


def remaining_quota():
    with _rl_lock:
        return _rl['remaining']


def graphql(query):
    """发送单个 GraphQL 查询，返回响应 JSON。403/429 时读 X-RateLimit-Reset 头等待重试。"""
    token = get_token()
    if not token:
        raise RuntimeError('找不到 GitHub token')
    body = json.dumps({'query': query}).encode('utf-8')
    headers = dict(UA)
    headers['Authorization'] = 'bearer ' + token
    headers['Content-Type'] = 'application/json'
    for attempt in range(1, 5):
        req = urllib.request.Request(API, data=body, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                reset = e.headers.get('X-RateLimit-Reset')
                wait = max(0.0, float(reset) - time.time() + 5) if reset else 60 * attempt
                print('  [限流] HTTP %d，等 %.0f 秒 ...' % (e.code, wait), flush=True)
                time.sleep(wait)
                continue
            if e.code >= 500 and attempt < 4:
                time.sleep(attempt * 2)
                continue
            raise
        except Exception:
            if attempt < 4:
                time.sleep(attempt * 2)
                continue
            raise
    raise RuntimeError('graphql 请求失败')


def build_query(batch):
    """batch: [(owner, name), ...] → 带 rN 别名的 GraphQL 查询（内嵌 rateLimit）。"""
    fields = []
    for i, (owner, name) in enumerate(batch):
        fields.append('r%d:repository(owner:%s,name:%s){pushedAt}'
                      % (i, json.dumps(owner), json.dumps(name)))
    return 'query{rateLimit{cost remaining resetAt} ' + ' '.join(fields) + '}'


def fetch_batch(batch):
    """查询一批 repo，返回 {repo: pushedAt_or_None} 和 (remaining, resetAt)。"""
    throttle()
    query = build_query(batch)
    payload = graphql(query)
    data = payload.get('data') or {}
    errors = payload.get('errors') or []
    not_found = set()
    for e in errors:
        path = e.get('path') or []
        if path and str(path[0]).startswith('r'):
            not_found.add(str(path[0]))
    results = {}
    for i, (owner, name) in enumerate(batch):
        alias = 'r%d' % i
        repo = '%s/%s' % (owner, name)
        if alias in not_found:
            results[repo] = None
        else:
            node = data.get(alias)
            results[repo] = (node or {}).get('pushedAt')
    rl = data.get('rateLimit') or {}
    return results, rl.get('remaining', 5000), rl.get('resetAt')


def split_owner_name(repo):
    if '/' not in repo:
        return None
    owner, name = repo.split('/', 1)
    if not owner or not name:
        return None
    return owner, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个 repo（0=全量）')
    ap.add_argument('--batch', type=int, default=BATCH)
    ap.add_argument('--concurrency', type=int, default=CONCURRENCY)
    args = ap.parse_args()

    if not get_token():
        print('错误：找不到 GitHub token。请先 `gh auth login` 或设置 GITHUB_TOKEN / GH_TOKEN。')
        sys.exit(1)

    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)
    all_repos = []
    for it in data['items']:
        p = split_owner_name(it['repo'])
        if p:
            all_repos.append(p)
    total_all = len(all_repos)
    if args.limit:
        all_repos = all_repos[:args.limit]
    total = len(all_repos)
    print('repo 总数 %d（全量 %d），每批 %d，并发 %d'
          % (total, total_all, args.batch, args.concurrency))

    # 断点续跑：results 按 repo 记（found 的记 pushedAt，missing 的记 null），
    # pending = 不在 results 里的 repo，天然跳过已完成
    prog = load_json(PROGRESS_FILE, {'results': {}})
    results = prog.get('results', {})
    pending = []
    for (owner, name) in all_repos:
        if '%s/%s' % (owner, name) not in results:
            pending.append((owner, name))
    print('断点续跑：已完成 %d，待处理 %d' % (len(results), len(pending)))

    batches = [pending[i:i + args.batch] for i in range(0, len(pending), args.batch)]
    done = total - len(pending)   # 已完成的 repo 数（含续跑）
    batch_done = 0
    t0 = time.time()
    failed_batches = []

    if batches:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            queue = [(b, 0) for b in batches]
            futures = {}

            def submit():
                while queue and len(futures) < args.concurrency:
                    b, tries = queue.pop(0)
                    futures[pool.submit(fetch_batch, b)] = (b, tries)

            submit()
            while futures:
                fut = next(as_completed(list(futures.keys())))
                b, tries = futures.pop(fut)
                try:
                    res, remaining, reset_at = fut.result()
                except Exception as e:
                    if tries < 3:
                        print('  [错误] 批次失败，重试 %d/3：%s' % (tries + 1, e), flush=True)
                        queue.append((b, tries + 1))
                    else:
                        print('  [错误] 批次放弃（3 次失败）：%s' % e, flush=True)
                        failed_batches.append(b)
                    submit()
                    continue
                for k, v in res.items():
                    results[k] = v
                update_ratelimit(remaining, reset_at)
                done += len(b)
                batch_done += 1
                if batch_done % 50 == 0:
                    print('[%d/%d] done, 剩余配额 %d' % (done, total, remaining_quota()),
                          flush=True)
                    save_json(PROGRESS_FILE, {'results': results, 'total': total})
                submit()

    save_json(PROGRESS_FILE, {'results': results, 'total': total})
    found = {k: v for k, v in results.items() if v}
    n_missing = len(results) - len(found)
    print('完成，耗时 %.0f 秒：%d 个有 pushed_at，%d 个 missing（不存在/已改名/空仓）'
          % (time.time() - t0, len(found), n_missing))
    if failed_batches:
        print('失败批次 %d 个（未写入结果）' % len(failed_batches))

    # 输出 pushed_at.json
    save_json(OUT_FILE, found)
    print('pushed_at.json 已保存（%d 条）' % len(found))

    # 写回 data_full.json
    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)
    n_written = 0
    for it in data['items']:
        repo = it.get('repo')
        if repo in results:
            it['pushed_at'] = results[repo]
            n_written += 1
    tmp = DATA_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)
    print('data_full.json 已写回 pushed_at（%d 条）' % n_written)
    print('DONE')


if __name__ == '__main__':
    main()
