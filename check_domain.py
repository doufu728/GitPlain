#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""域名上线自检：DNS、证书、跳转、内容一致性。

用法:
    python check_domain.py                # 检查 www.gitplain.com
    python check_domain.py --wait         # 未生效时每 30 秒重试，最多 10 分钟
"""

import argparse
import socket
import ssl
import sys
import time
import urllib.request

DOMAIN = "www.gitplain.com"
APEX = "gitplain.com"
ORIGIN = "gitplain.pages.dev"
PAGES = "https://gitplain.pages.dev"
CTX = ssl.create_default_context()

OK = "  [OK]  "
BAD = "  [!!]  "
WAIT = "  [..]  "


def step(msg):
    print(f"\n{msg}")


def dns_check():
    """CNAME 是否指向 pages.dev，且能解析出 IP。"""
    try:
        ip = socket.getaddrinfo(DOMAIN, None, socket.AF_INET)[0][4][0]
        print(f"{OK}{DOMAIN} 解析到 {ip}")
    except Exception:
        print(f"{BAD}{DOMAIN} 还解析不出来（CNAME 未生效或未添加）")
        return False

    # CNAME 目标：用系统解析器拿不到就用 dnspython，退化到只看连通性
    try:
        import dns.resolver  # type: ignore
        try:
            ans = dns.resolver.resolve(DOMAIN, "CNAME")
            target = str(ans[0].target).rstrip(".")
            print(f"{OK}CNAME -> {target}")
            if ORIGIN not in target:
                print(f"{BAD}CNAME 指向了 {target}，应为 {ORIGIN}")
                return False
        except Exception:
            print(f"{WAIT}查不到 CNAME 记录（可能已被 CDN 摊平成 A 记录，不算错）")
    except ImportError:
        print(f"{WAIT}未装 dnspython，跳过 CNAME 目标校验（pip install dnspython 可补）")
    return True


def https_check():
    """HTTPS 200 + 证书有效且覆盖该域名。"""
    url = f"https://{DOMAIN}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GitPlain-Check/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            body = r.read()
            print(f"{OK}{url} -> HTTP {r.status}，{len(body)} 字节")
    except ssl.SSLCertVerificationError as e:
        print(f"{BAD}证书校验失败: {e}")
        return False
    except Exception as e:
        print(f"{BAD}HTTPS 打不开: {type(e).__name__}: {e}")
        return False

    try:
        with socket.create_connection((DOMAIN, 443), timeout=15) as s:
            with CTX.wrap_socket(s, server_hostname=DOMAIN) as ss:
                cert = ss.getpeercert()
        issuer = dict(x[0] for x in cert["issuer"]).get("organizationName", "?")
        until = cert["notAfter"]
        print(f"{OK}证书签发者: {issuer}，有效期至 {until}")
    except Exception as e:
        print(f"{WAIT}证书信息读不到: {e}")

    return True


def consistency_check():
    """线上域名与 pages.dev 返回的首页是否一致。"""
    try:
        a = urllib.request.urlopen(
            urllib.request.Request(f"https://{DOMAIN}/", headers={"User-Agent": "GitPlain-Check/1.0"}),
            timeout=20, context=CTX).read()
        b = urllib.request.urlopen(
            urllib.request.Request(f"{PAGES}/", headers={"User-Agent": "GitPlain-Check/1.0"}),
            timeout=20, context=CTX).read()
        if a == b:
            print(f"{OK}首页内容与 {ORIGIN} 完全一致")
            return True
        print(f"{BAD}首页与 {ORIGIN} 不一致（{len(a)} vs {len(b)} 字节）")
        return False
    except Exception as e:
        print(f"{WAIT}内容比对失败: {e}")
        return False


def apex_check():
    """根域名是否跳转到 www。"""
    url = f"https://{APEX}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GitPlain-Check/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            final = r.geturl()
        if final.rstrip("/") == f"https://{DOMAIN}".rstrip("/") or DOMAIN in final:
            print(f"{OK}{APEX} 跳转到 {final}")
            return True
        print(f"{BAD}{APEX} 落在 {final}，没有跳到 {DOMAIN}")
        return False
    except Exception as e:
        print(f"{WAIT}{APEX} 暂时不通（{type(e).__name__}）——根域名可稍后再配")
        return False


def run(wait):
    deadline = time.time() + (600 if wait else 0)
    while True:
        step("1. DNS 解析")
        d = dns_check()
        step("2. HTTPS 与证书")
        h = https_check() if d else False
        step("3. 内容一致性")
        c = consistency_check() if h else False
        step("4. 根域名跳转（可选）")
        a = apex_check()

        print("\n" + "-" * 56)
        if d and h and c:
            print("上线完成。")
            if not a:
                print("提示：根域名 gitplain.com 还未跳转，需要在阿里云配『显性 URL 转发』。")
            return 0
        if time.time() >= deadline:
            print("仍有项目未通过，见上面 [!!] 标记。")
            return 1
        print("30 秒后重试……（Ctrl+C 退出）")
        time.sleep(30)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--wait", action="store_true", help="未生效时轮询重试")
    sys.exit(run(p.parse_args().wait))
