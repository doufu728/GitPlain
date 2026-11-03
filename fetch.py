#!/usr/bin/env python3
"""抓 GitHub Trending weekly → data.json（GitPlain 数据源）"""
import json, re, sys, urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "data.js"
UA = {"User-Agent": "Mozilla/5.0"}

# 不适合放在公开推荐站的项目（安全/合规）
BLOCK = ("jailbreak", "破甲", "越狱", "uncensor", "bypass", "nsfw", "uncensored")

# 人工写好的中文解释 + 分类 + 适合谁 + 怎么用。
# 数据更新后，这里的老项目不丢人工内容；新上榜的项目走 main() 里的兜底。
CURATED = {
    "cloudflare/security-audit-skill": {
        "desc_cn": "给 AI 编程助手装一个「安全审计」技能,让它分阶段审查代码、找出安全漏洞,结论能查证。",
        "who": "用 Claude Code / Cursor 写代码,又担心 AI 改出安全问题的人",
        "steps": ["装进 Claude Code / Codex", "让它审查你的项目", "看它给的安全报告"],
        "category": "安全",
    },
    "Nutlope/hallmark": {
        "desc_cn": "教 AI 生成界面时「别那么像 AI 做的」,避开千篇一律的紫蓝渐变和假大空设计。",
        "who": "用 AI 做网页 / 界面,又嫌它做出来一股 AI 味的人",
        "steps": ["装进 Cursor / Claude Code", "让它做界面", "出来的效果更有人味"],
        "category": "设计审美",
    },
    "pbakaus/impeccable": {
        "desc_cn": "一套「设计标准」,教 AI 助手分辨好看和丑,上线前帮你揪出 AI 味界面。",
        "who": "想让 AI 做出来的东西更精致、不想被吐槽像 AI 做的开发者",
        "steps": ["装进你的 agent", "让它 review 界面", "按它的批评改"],
        "category": "设计审美",
    },
    "affaan-m/ECC": {
        "desc_cn": "给 AI 编程助手加「技能、记忆、安全」的一整套系统,让它更聪明、更稳定。",
        "who": "重度用 Claude Code / Codex 做开发的人",
        "steps": ["装进你的 agent", "按它给的技能和记忆配置", "开发效率提升"],
        "category": "AI 编程工具",
    },
    "TauricResearch/TradingAgents": {
        "desc_cn": "用多个 AI 智能体协作做金融交易(分析、决策、下单),是研究用的交易框架。",
        "who": "对 AI 金融交易 / 量化感兴趣的研究者",
        "steps": ["克隆代码", "配置 API key", "跑模拟交易"],
        "category": "AI Agent 框架",
    },
    "obra/superpowers": {
        "desc_cn": "一套「超能力」技能包,教 AI 编程助手按正确流程干活:先想清楚、写计划、TDD、review。",
        "who": "想让 AI 编程更靠谱、不瞎写的开发者",
        "steps": ["装进 Claude Code / Codex", "让它按流程开发", "代码质量更稳"],
        "category": "AI 编程工具",
    },
    "Leonxlnx/taste-skill": {
        "desc_cn": "给 AI 编程助手「品味」,让它做界面时参考真实设计,不生成千篇一律的页面。",
        "who": "用 AI 做前端、想做出有审美的界面的人",
        "steps": ["装进 agent", "给它参考图", "界面更有个性"],
        "category": "设计审美",
    },
    "AgriciDaniel/claude-seo": {
        "desc_cn": "给 AI 编程助手装的「SEO 大全」,26 个小技能覆盖技术 SEO、外链、本地 SEO 等。",
        "who": "做网站 / 内容、想让搜索引擎排名更好的人",
        "steps": ["装进 Claude Code", "让它分析你的网站 SEO", "按建议改"],
        "category": "AI 编程工具",
    },
    "multica-ai/andrej-karpathy-skills": {
        "desc_cn": "一份配置,把 AI 大神 Karpathy 总结的「AI 编程常见坑」喂给 Claude Code,让它少犯错。",
        "who": "用 Claude Code 写代码、想让它少踩坑的人",
        "steps": ["把 CLAUDE.md 放进项目", "重启 Claude Code", "它更懂怎么写"],
        "category": "AI 编程工具",
    },
    "thedotmack/claude-mem": {
        "desc_cn": "给 AI 编程助手加「长期记忆」,记住你上个会话干了啥,下个会话接着用。",
        "who": "长期用 AI 编程、烦它「失忆」的人",
        "steps": ["装进 Claude Code / Codex", "正常开发", "它自动记住上下文"],
        "category": "AI 编程工具",
    },
    "pingdotgg/t3code": {
        "desc_cn": "官方未提供描述。",
        "who": "官方未提供描述",
        "steps": ["点右下角按钮去 GitHub 看详情"],
        "category": "AI 编程工具",
    },
    "AstrBotDevs/AstrBot": {
        "desc_cn": "一个 AI 助手框架,能接入微信 / QQ / 飞书等一堆聊天平台,可当你的私人机器人。",
        "who": "想自己搭一个多平台 AI 聊天机器人的人",
        "steps": ["部署", "接一个聊天平台", "配好模型就能聊"],
        "category": "AI Agent 框架",
    },
    "anthropics/skills": {
        "desc_cn": "Anthropic(Claude 母公司)官方开源的「技能库」,教 Claude 干各种活。",
        "who": "用 Claude Code、想给它加官方技能的人",
        "steps": ["浏览技能列表", "挑想要的装", "Claude 就能干对应的活"],
        "category": "AI 编程工具",
    },
    "jakubkrehel/skills": {
        "desc_cn": "一套教 AI 编程助手「怎么做出好看界面」的技能合集。",
        "who": "用 AI 做界面、想让它做得更好看的人",
        "steps": ["装进 agent", "让它做界面", "效果更好"],
        "category": "设计审美",
    },
}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def parse_trending(html):
    items = []
    for art in re.findall(r'<article class="Box-row">(.*?)</article>', html, re.S):
        m = re.search(r'<h2[^>]*>.*?href="/([^"]+)"', art, re.S)
        if not m:
            continue
        full = m.group(1).strip()
        if full.count("/") != 1 or full.startswith("sponsors/"):
            continue
        desc = re.search(r'<p class="col-9[^"]*">\s*(.*?)</p>', art, re.S)
        desc = re.sub(r"<[^>]+>", " ", desc.group(1)).strip() if desc else ""
        desc = re.sub(r"\s+", " ", desc)
        stars = re.search(r'([\d,]+)\s*stars?\s*(?:this|today)', art)
        stars = int(stars.group(1).replace(",", "")) if stars else 0
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        items.append({
            "repo": full,
            "desc": desc,
            "stars_week": stars,
            "lang": lang.group(1) if lang else "",
        })
    return items


def enrich(items):
    """用 GitHub API 补总数和 topics；失败就用抓到的"""
    for it in items:
        try:
            d = json.loads(fetch(f"https://api.github.com/repos/{it['repo']}"))
            it["stars"] = d.get("stargazers_count", 0)
            it["topics"] = (d.get("topics") or [])[:5]
            it["url"] = d.get("html_url", f"https://github.com/{it['repo']}")
            it["owner"] = d.get("owner", {}).get("login", it["repo"].split("/")[0])
            it["owner_avatar"] = d.get("owner", {}).get("avatar_url", "")
            if not it["desc"]:
                it["desc"] = d.get("description") or ""
            if not it["lang"]:
                it["lang"] = d.get("language") or ""
        except Exception as e:
            it["stars"] = 0
            it["topics"] = []
            it["url"] = f"https://github.com/{it['repo']}"
            it["owner"] = it["repo"].split("/")[0]
            it["owner_avatar"] = ""
            print(f"  ! {it['repo']}: {e}", file=sys.stderr)
    return items


def main():
    html = fetch("https://github.com/trending?since=weekly")
    items = parse_trending(html)
    print(f"抓到 {len(items)} 个 trending 项目")
    items = enrich(items)
    items = [i for i in items if i["repo"]]
    before = len(items)
    items = [i for i in items
             if not any(b in (i["repo"] + " " + i["desc"]).lower() for b in BLOCK)]
    if before != len(items):
        print(f"  已过滤 {before - len(items)} 条（合规）")
    # 合并人工内容：有条目的用人工中文，没条目的兜底（desc_cn=原文 desc，category=待分类）
    for it in items:
        c = CURATED.get(it["repo"], {})
        it["desc_cn"] = c.get("desc_cn") or it.get("desc") or ""
        it["category"] = c.get("category") or "待分类"
        it["who"] = c.get("who") or "待补充"
        it["steps"] = c.get("steps") or []
    items.sort(key=lambda x: x["stars_week"], reverse=True)
    payload = {"updated": __import__("datetime").date.today().isoformat(), "items": items}
    OUT.write_text("window.GH_DATA = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n",
                   encoding="utf-8")
    print(f"已写入 {OUT}（{len(items)} 条）")


if __name__ == "__main__":
    main()
