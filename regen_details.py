"""只重新生成 repo/ 下的详情页，不碰 data/ 分片（数据抓取任务正在跑）。"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

t0 = time.time()
with open('data_full.json', encoding='utf-8') as f:
    data = json.load(f)          # 一次读进内存，避免抓取任务中途写文件时读到半个
items = data['items']

gt10k = [it for it in items if (it.get('stars') or 0) > 10000]
print('要生成的详情页：%d 个' % len(gt10k))

made = 0
for i, it in enumerate(gt10k, 1):
    owner, name = it['repo'].split('/', 1)
    d = os.path.join('repo', owner, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build.detail_page_html(it))
    made += 1
    if i % 1000 == 0:
        print('  %d / %d' % (i, len(gt10k)), flush=True)

print('完成 %d 个，耗时 %.0f 秒' % (made, time.time() - t0))
