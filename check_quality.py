#!/usr/bin/env python3
"""文案质量自动检测（8 条可量化规则，不需要人判断）
用法: python check_quality.py data_zh.json [--sample 200]
输出: 通过率 + 不通过清单（含原因）
"""
import json, sys, re, argparse
from pathlib import Path

# 机翻味禁用词（出现即扣分）
BANNED = [
    "基于", "赋能", "解决方案", "端到端", "多模态", "一体化", "打造",
    "助力", "生态", "闭环", "底层", "抽象", "范式", "维度", "颗粒度",
    "无缝", "沉浸式", "赋能于", "打通", "拉通",
]

# 用途动词（desc_cn 必须至少含一个，否则只是"是什么"不是"能干什么"）
VERBS = ["能", "可以", "让", "帮", "给", "用来", "支持", "一键", "自动", "直接"]

CATEGORIES = {
    "AI 编程工具", "AI Agent 框架", "AI 模型与推理", "AI 应用", "提示词与 Skill",
    "设计 / UI", "安全", "开发工具", "前端框架", "后端框架", "数据库", "DevOps / 部署",
    "编程语言", "学习资源", "操作系统", "编辑器/IDE", "图形图像", "音视频", "游戏",
    "数据分析", "网络 / 爬虫", "区块链", "移动开发", "系统工具", "其他",
}


def check_one(it):
    """返回 (通过?, 问题列表)"""
    problems = []
    desc = (it.get("desc_cn") or "").strip()
    cat = (it.get("category") or "").strip()
    who = (it.get("who") or "").strip()
    steps = it.get("steps") or []

    # 1. 长度 30-80 字（放宽，给中文留余量）
    if not (30 <= len(desc) <= 80):
        problems.append(f"desc_cn 长度 {len(desc)}（应 30-80）")

    # 2. 禁用词
    hit = [w for w in BANNED if w in desc]
    if hit:
        problems.append(f"机翻味词：{'/'.join(hit)}")

    # 3. 含用途动词
    if not any(v in desc for v in VERBS):
        problems.append("没有用途动词（只说了是什么，没说能干什么）")

    # 4. 英文单词数 < 3（专有名词允许少量）
    en_words = re.findall(r"\b[A-Za-z]{2,}\b", desc)
    if len(en_words) > 4:
        problems.append(f"英文词太多（{len(en_words)} 个）：{en_words[:5]}")

    # 5. category 在 25 类里
    if cat not in CATEGORIES:
        problems.append(f"分类非法：{cat}")

    # 6. steps 恰好 3 条
    if len(steps) != 3:
        problems.append(f"steps 有 {len(steps)} 条（应 3）")
    else:
        for i, s in enumerate(steps):
            if not (3 <= len(s) <= 20):
                problems.append(f"steps[{i}] 长度 {len(s)}（应 3-20）")

    # 7. who 10-30 字
    if not (10 <= len(who) <= 30):
        problems.append(f"who 长度 {len(who)}（应 10-30）")

    # 8. 空描述必须如实标注
    orig = (it.get("desc") or "").strip()
    if not orig and "未提供" not in desc and "没有描述" not in desc:
        problems.append("原描述为空，但 desc_cn 没标注'官方未提供描述'")

    return len(problems) == 0, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--sample", type=int, default=0, help="只检查前 N 条")
    ap.add_argument("--show", type=int, default=10, help="列出多少条失败样例")
    a = ap.parse_args()

    d = json.loads(Path(a.path).read_text(encoding="utf-8"))
    items = d.get("items") if isinstance(d, dict) else d
    if a.sample:
        items = items[: a.sample]

    total = len(items)
    failed = []
    for it in items:
        ok, probs = check_one(it)
        if not ok:
            failed.append((it.get("repo", "?"), probs, it))

    passed = total - len(failed)
    rate = passed / total * 100 if total else 0

    print(f"总数 {total} | 通过 {passed} | 不通过 {len(failed)} | 通过率 {rate:.1f}%")
    print()
    if failed:
        print(f"=== 不通过样例（前 {min(a.show, len(failed))} 条）===")
        for repo, probs, it in failed[: a.show]:
            print(f"\n{repo}")
            print(f"  desc_cn: {(it.get('desc_cn') or '')[:60]}")
            for p in probs:
                print(f"  ✗ {p}")

    # 结论
    print()
    if rate >= 90:
        print("✅ 通过（≥90%），可放行全量")
    elif rate >= 70:
        print("⚠️ 勉强（70-90%），建议改 prompt 再跑一轮")
    else:
        print("❌ 不通过（<70%），必须改 prompt，不许跑全量")
    sys.exit(0 if rate >= 90 else 1)


if __name__ == "__main__":
    main()
