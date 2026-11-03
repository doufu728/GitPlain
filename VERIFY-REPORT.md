# 链接双检报告

- 生成时间：2026-11-01T18:41:25+08:00
- 数据文件：`data_full.json`
- 总条数：**65856**
- 结论：**✓ 双检达标**
- 耗时：174.6 分（2000 复用缓存 / 63856 实时请求，并发 40）

## 双检 ① 逐字符比对

`url === "https://github.com/" + repo`，不 trim、不忽略大小写、不补斜杠。

| 项 | 值 |
|---|---|
| 通过 | 65856 / 65856 |
| 通过率 | **100.00%**（要求 100%） |

0 条不通过。

## 双检 ② HEAD 可达性

| 分类 | 条数 | 处理 |
|---|---|---|
| 通过（200/301/302） | 65818 | — |
| 死链（404/451） | 1 | 写入 `dead_links.json`，需剔除 |
| 待查（其他状态码/网络错误） | 0 | 见下方明细 |
| 限流未定（429） | 37 | 见下方明细，建议复跑 |

- 通过率：**99.94%**（要求 ≥98%）
- 跳转（仓库改名/转移，链接仍可用）：13 条

### 死链清单（1 条）

| 域名 | 状态码 | repo | 判断 |
|---|---|---|---|
| github.com | 404 | `ArasTey/lunel` | 仓库不存在（已删除 / 改私有 / 从未公开） |

### 待查清单（37 条）

| 域名 | 状态码 | repo | 判断 |
|---|---|---|---|
| github.com | 429 | `BuilderIO/gpt-crawler` | 被限流，未拿到确定结果 |
| github.com | 429 | `DesignPatternsPHP/DesignPatternsPHP` | 被限流，未拿到确定结果 |
| github.com | 429 | `FreeTubeApp/FreeTube` | 被限流，未拿到确定结果 |
| github.com | 429 | `Homebrew/homebrew-cask` | 被限流，未拿到确定结果 |
| github.com | 429 | `MLEveryday/100-Days-Of-ML-Code` | 被限流，未拿到确定结果 |
| github.com | 429 | `PHPMailer/PHPMailer` | 被限流，未拿到确定结果 |
| github.com | 429 | `PrimeIntellect-ai/prime-agent` | 被限流，未拿到确定结果 |
| github.com | 429 | `PromtEngineer/localGPT` | 被限流，未拿到确定结果 |
| github.com | 429 | `QuantConnect/Lean` | 被限流，未拿到确定结果 |
| github.com | 429 | `SamyPesse/How-to-Make-a-Computer-Operating-System` | 被限流，未拿到确定结果 |
| github.com | 429 | `Tencent/wepy` | 被限流，未拿到确定结果 |
| github.com | 429 | `XiaoMi/ha_xiaomi_home` | 被限流，未拿到确定结果 |
| github.com | 429 | `airbytehq/airbyte` | 被限流，未拿到确定结果 |
| github.com | 429 | `chidiwilliams/buzz` | 被限流，未拿到确定结果 |
| github.com | 429 | `gildas-lormeau/SingleFile` | 被限流，未拿到确定结果 |
| github.com | 429 | `imputnet/helium` | 被限流，未拿到确定结果 |
| github.com | 429 | `izackwu/TeachYourselfCS-CN` | 被限流，未拿到确定结果 |
| github.com | 429 | `jhipster/generator-jhipster` | 被限流，未拿到确定结果 |
| github.com | 429 | `joonspk-research/generative_agents` | 被限流，未拿到确定结果 |
| github.com | 429 | `lima-vm/lima` | 被限流，未拿到确定结果 |
| github.com | 429 | `mack-a/v2ray-agent` | 被限流，未拿到确定结果 |
| github.com | 429 | `meta/flow` | 被限流，未拿到确定结果 |
| github.com | 429 | `micropython/micropython` | 被限流，未拿到确定结果 |
| github.com | 429 | `microsoft/onnxruntime` | 被限流，未拿到确定结果 |
| github.com | 429 | `microsoft/unilm` | 被限流，未拿到确定结果 |
| github.com | 429 | `newsnext/newsnow` | 被限流，未拿到确定结果 |
| github.com | 429 | `ossu/data-science` | 被限流，未拿到确定结果 |
| github.com | 429 | `palantir/blueprint` | 被限流，未拿到确定结果 |
| github.com | 429 | `postcss/autoprefixer` | 被限流，未拿到确定结果 |
| github.com | 429 | `redux-saga/redux-saga` | 被限流，未拿到确定结果 |
| github.com | 429 | `rust-lang/mdBook` | 被限流，未拿到确定结果 |
| github.com | 429 | `scottbez1/smartknob` | 被限流，未拿到确定结果 |
| github.com | 429 | `screenpipe/screenpipe` | 被限流，未拿到确定结果 |
| github.com | 429 | `t4t5/sweetalert` | 被限流，未拿到确定结果 |
| github.com | 429 | `tabler/tabler-icons` | 被限流，未拿到确定结果 |
| github.com | 429 | `vueuse/vueuse` | 被限流，未拿到确定结果 |
| github.com | 429 | `yoheinakajima/babyagi` | 被限流，未拿到确定结果 |

### 跳转清单（前 50 条）

| 原 url | 跳到 |
|---|---|
| `https://github.com/CharonChui/AndroidNote` | `https://github.com/CharonChui/FullStack-Notes` |
| `https://github.com/EhViewer-NekoInverter/EhViewer` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2FEhViewer-NekoInverter%2FEhViewer` |
| `https://github.com/Moham3dRiahi/XAttacker` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2FMoham3dRiahi%2FXAttacker` |
| `https://github.com/ReaJason/MemShellParty` | `https://github.com/MemShellParty/MemShellParty` |
| `https://github.com/esprfid/esp-rfid` | `https://github.com/omersiar/esp-rfid` |
| `https://github.com/gzxx-2025/aid-studio` | `https://github.com/shijue-aid/aid-studio` |
| `https://github.com/htimesnine/DarkSword-RCE` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fhtimesnine%2FDarkSword-RCE` |
| `https://github.com/imfht/fanhaodaquan` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fimfht%2Ffanhaodaquan` |
| `https://github.com/notAI-tech/NudeNet` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2FnotAI-tech%2FNudeNet` |
| `https://github.com/opa334/darksword-kexploit` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fopa334%2Fdarksword-kexploit` |
| `https://github.com/polyfillpolyfill/polyfill-service` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fpolyfillpolyfill%2Fpolyfill-service` |
| `https://github.com/ruicky/jd_sign_bot` | `https://github.com/login?return_to=https%3A%2F%2Fgithub.com%2Fruicky%2Fjd_sign_bot` |
| `https://github.com/scholay/xsime` | `https://github.com/scholay-xsime/xsime` |
