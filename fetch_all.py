#!/usr/bin/env python3
"""
fetch_all.py —— 抓取 GitHub 上所有 >1000 星的仓库（约 66,000 个）。

为什么不用简单的 661 次翻页：GitHub Search API 对任意查询最多只返回 1000 条结果
（实测 page=11 返回 HTTP 422 "Only the first 1000 search results are available"），
所以按 spec 的「sort=stars 连续翻 661 页」在技术上拿不到 66k 条。

正确做法（本脚本实现）：按 star 区间递归分桶。每个桶的总数 <= BUCKET_MAX(<1000)
时一次性翻完；否则按 stars 降序取前 BUCKET_MAX 条，把区间上界压到「最后一条的
star 数」，再递归处理剩余区间。实测单个 star 值的仓库数 < 60（1000 星档最多 ~59），
所以递归必然终止。最后按 full_name 去重、按 stars 降序输出。

用法：
    python fetch_all.py               # 全量抓取（断点续跑）
    python fetch_all.py --lo 15000 --hi 16000   # 只抓某 star 区间（测试用）

鉴权：
    优先 GITHUB_TOKEN 环境变量；其次读 hermes 的 .env；都没有就匿名。
    匿名 search 限流 10 次/分钟（本脚本自动 sleep 遵守）；带 token 30 次/分钟。

断点续跑：
    每条写入 repos_raw.jsonl（JSONL，追加）。progress.json 记录待处理区间栈 stack、
    当前正在处理的桶 current（含 phase 与已翻到的页号 page），每翻完一页就写一次。
    中断后重跑先读回已抓数据 + stack + current，从当前桶的下一页接着来，不整轮重来。

失败重试：
    403/429 指数退避，最多 3 次；仍失败写 fetch_failed.json（记录区间/页/原因），继续。
"""
import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_JSONL = HERE / "repos_raw.jsonl"
RAW_JSON = HERE / "repos_raw.json"
PROGRESS = HERE / "progress.json"
FAILED = HERE / "fetch_failed.json"

API = "https://api.github.com/search/repositories"
UA = "no-code-github-fetcher"
BUCKET_MAX = 900          # 单桶 <= 900 条时一次性翻完（留 <1000 的安全余量）
PER_PAGE = 100            # search API 每页上限
RETRY_MAX = 3


def load_token():
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    for p in (Path.home() / "AppData/Local/hermes/.env",
              Path.home() / ".env"):
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GITHUB_TOKEN"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
        except Exception:
            pass
    return ""


TOKEN = load_token()
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": UA}
if TOKEN:
    HEADERS["Authorization"] = "token " + TOKEN


def _do_request(url):
    _throttle()
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


_last_req = 0.0


def _throttle():
    """全局限流：所有请求之间强制最小间隔（匿名 6.5s≈9/min，带 token 2s=30/min）。"""
    global _last_req
    interval = 2.0 if TOKEN else 6.5
    wait = interval - (time.time() - _last_req)
    if wait > 0:
        time.sleep(wait)
    _last_req = time.time()


def request_json(url, retries=RETRY_MAX):
    """请求并解析 JSON；403/429 指数退避，最多 retries 次；仍失败抛异常。"""
    delay = 1.0
    last_err = None
    for attempt in range(retries + 1):
        try:
            return json.loads(_do_request(url))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            if e.code in (403, 429):
                last_err = f"HTTP {e.code} {body[:120]}"
                # 从响应头读 reset 时间，能更精确地等
                reset = e.headers.get("x-ratelimit-reset")
                wait = delay
                if reset:
                    try:
                        wait = max(wait, int(reset) - int(time.time()) + 1)
                    except Exception:
                        pass
                if attempt < retries:
                    time.sleep(min(wait, 60))
                    delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(last_err or "request failed")


def build_query(lo, hi):
    # 用 stars:a..b 区间语法（实测可靠）；开区间用严格大于（stars:>lo-1 == >=lo）
    if hi is not None:
        q = f"stars:{lo}..{hi}"
    else:
        q = f"stars:>{lo - 1}"
    q += " fork:false"
    return q


def count_in_range(lo, hi):
    url = f"{API}?q={urllib.parse.quote(build_query(lo, hi))}&per_page=1"
    return request_json(url).get("total_count", 0)


def page_items(lo, hi, page):
    url = (f"{API}?q={urllib.parse.quote(build_query(lo, hi))}"
           f"&sort=stars&order=desc&per_page={PER_PAGE}&page={page}")
    return request_json(url).get("items", [])


def extract(it):
    return {
        "repo": it.get("full_name", ""),
        "desc": it.get("description") or "",
        "stars": it.get("stargazers_count", 0),
        "owner": (it.get("owner") or {}).get("login", ""),
        "owner_avatar": (it.get("owner") or {}).get("avatar_url", ""),
        "lang": it.get("language") or "",
        "topics": it.get("topics") or [],
        "url": it.get("html_url", ""),
        "updated_at": it.get("updated_at", ""),
    }


def load_state():
    items = {}
    if RAW_JSONL.exists():
        with open(RAW_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                items[d["repo"]] = d
    stack = [[1001, None]]
    current = None
    failed = []
    if PROGRESS.exists():
        try:
            p = json.loads(PROGRESS.read_text(encoding="utf-8"))
            if isinstance(p.get("stack"), list):
                stack = p["stack"]
            if isinstance(p.get("current"), dict):
                current = p["current"]
            failed = p.get("failed", []) or []
        except Exception:
            pass
    return items, stack, current, failed


def save_state(items, stack, current, failed):
    PROGRESS.write_text(
        json.dumps({"stack": stack, "current": current,
                    "count": len(items), "failed": failed},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")


def append_items(items, new_items):
    """把新条目写入 dict（去重）+ 追加 JSONL。"""
    added = 0
    with open(RAW_JSONL, "a", encoding="utf-8") as f:
        for d in new_items:
            key = d["repo"]
            if not key or key in items:
                continue
            items[key] = d
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            added += 1
    return added


def run(lo=1001, hi=None):
    items, stack, current, failed = load_state()
    # 显式指定区间时（测试用），用该区间替换待处理栈与当前桶
    if lo != 1001 or hi is not None:
        stack = [[lo, hi]]
        current = None
    req_count = 0
    t0 = time.time()
    try:
        while stack or current is not None:
            # 当前桶为空时才从栈顶 pop 新桶（不先 pop：中断时在途桶仍挂在 current 上，不会丢）
            if current is None:
                lo, hi = stack.pop()
                current = {"lo": lo, "hi": hi, "total": None,
                           "phase": "count", "page": 0, "batch": []}
            c = current
            lo, hi = c["lo"], c["hi"]
            if hi is not None and lo > hi:
                current = None
                save_state(items, stack, current, failed)
                continue

            if c["phase"] == "count":
                try:
                    total = count_in_range(lo, hi)
                    req_count += 1
                except Exception as e:
                    failed.append({"range": [lo, hi], "page": "count",
                                   "error": str(e)})
                    current = None
                    save_state(items, stack, current, failed)
                    continue
                c["total"] = total
                if total == 0:
                    current = None
                    save_state(items, stack, current, failed)
                    continue
                c["phase"] = "leaf" if total <= BUCKET_MAX else "split"
                c["page"] = 1
                save_state(items, stack, current, failed)
                continue

            if c["phase"] == "leaf":
                pages = (c["total"] + PER_PAGE - 1) // PER_PAGE
                while c["page"] <= pages:
                    p = c["page"]
                    try:
                        batch = page_items(lo, hi, p)
                        req_count += 1
                    except Exception as e:
                        failed.append({"range": [lo, hi], "page": p,
                                       "error": str(e)})
                        current = None
                        save_state(items, stack, current, failed)
                        break
                    append_items(items, [extract(x) for x in batch])
                    c["page"] += 1
                    save_state(items, stack, current, failed)
                else:
                    current = None  # 桶内所有页翻完
                    save_state(items, stack, current, failed)
                continue

            # phase == "split"：取该区间 stars 最高的前 BUCKET_MAX 条，压上限后递归处理剩余
            n_pages = (BUCKET_MAX + PER_PAGE - 1) // PER_PAGE
            while c["page"] <= n_pages:
                p = c["page"]
                try:
                    batch = page_items(lo, hi, p)
                    req_count += 1
                except Exception as e:
                    failed.append({"range": [lo, hi], "page": p,
                                   "error": str(e)})
                    current = None
                    save_state(items, stack, current, failed)
                    break
                ext = [extract(x) for x in batch]
                c["batch"].extend(ext)
                append_items(items, ext)
                c["page"] += 1
                save_state(items, stack, current, failed)
            else:
                top = c["batch"][:BUCKET_MAX]
                if top:
                    last_stars = top[-1]["stars"]
                    # 防死循环：上界必须严格下降（同星并列桶理论上 < BUCKET_MAX，此分支仅兜底）
                    if hi is not None and last_stars >= hi:
                        last_stars = hi - 1
                    # 剩余区间 [lo, last_stars]（含同星并列，去重兜底）
                    if last_stars >= lo:
                        stack.append([lo, last_stars])
                current = None
                save_state(items, stack, current, failed)
            continue
    except KeyboardInterrupt:
        save_state(items, stack, current, failed)
        print(f"\n[中断] 已保存进度：{len(items)} 条，可从断点续跑", flush=True)
        raise

    elapsed = time.time() - t0
    return items, req_count, failed, elapsed


def write_final(items):
    ordered = sorted(items.values(), key=lambda x: x["stars"], reverse=True)
    payload = {
        "updated": datetime.date.today().isoformat(),
        "total": len(ordered),
        "items": ordered,
    }
    RAW_JSON.write_text(json.dumps(payload, ensure_ascii=False),
                        encoding="utf-8")
    return payload


def _arg(name, default):
    if name in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(name) + 1])
        except (ValueError, IndexError):
            return default
    return default


def main():
    lo = _arg("--lo", 1001)
    hi = _arg("--hi", None)

    mode = "带 token" if TOKEN else "匿名"
    print(f"[{mode}] 开始抓取 >1000 星仓库（含 fork:false 过滤）")
    if lo != 1001 or hi is not None:
        print(f"[测试] 只抓 stars {lo}..{hi if hi is not None else '∞'} 的区间")

    items, req_count, failed, elapsed = run(lo, hi)
    payload = write_final(items)

    if FAILED.exists() or failed:
        FAILED.write_text(json.dumps(failed, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    print(f"\n完成：{payload['total']} 条")
    print(f"请求次数：{req_count}")
    print(f"耗时：{elapsed/60:.1f} 分钟")
    print(f"失败：{len(failed)} 条")
    print(f"输出：{RAW_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
