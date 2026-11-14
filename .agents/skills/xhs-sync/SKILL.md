---
name: 小红书笔记同步
description: 把小七（柒柒）小红书主页的公开笔记同步成 Hexo 博客文章（抓笔记、下图片、生成文章、发布），或排查同步时的登录态/风控/解析问题。用户说「同步小红书」「更新小红书笔记」时使用。
---

# 小红书 → 博客同步

把小红书用户「柒柒」(`user_id: 649d592e0000000011000515`) 主页公开笔记同步为
`source/_posts/` 下的 Hexo 文章，图片放 `source/img/xhs/<完整 note_id>/`。
全程 **requests + cookie 纯 HTTP**，一条龙脚本：`scripts/xhs_sync.py`。

## 铁律（违反会直接搞坏用户的账号会话）

1. **绝对不要新开浏览器实例**（Playwright、新 Chrome 窗口、新 user-data-dir 都算）。
   小红书会判成「新设备登录」，触发「电脑登录设备超限」，把用户当前登录踢下线，
   同步当场报废，只能请用户重新登录。2026-11-01 踩过。
2. **不要自己直调 `/api/sns/web/*`**（签名直调）：406 → 461 → 300011 账号异常，
   需要冷却数小时到一天。
3. **不要新建/复制 Chrome profile** 去「顺便拿 cookie」，也不需要 DevTools 手动导出——
   直接解本机 Chrome 的 cookie 库（下面第 1 步）。
4. 频率克制：详情页之间 `sleep 2`，图片之间 `sleep 0.4`（脚本已内置，别调小）。

## 一次性准备

```bash
cd <repo>
python3 -m venv .venv-xhs --system-site-packages   # 需要能 import gi（读 keyring）
.venv-xhs/bin/pip install requests pillow cryptography
```

`.venv-xhs/`、`.xhs-cookies*` 都在 `.gitignore` 里，不会提交。

## 一键流程

```bash
PY=.venv-xhs/bin/python
S=.agents/skills/xhs-sync/scripts/xhs_sync.py

$PY $S cookies      # 1. 从 Chrome cookie 库解出登录态 → .xhs-cookies.json
$PY $S list         # 2. 主页 SSR 第一页 + 与 source/_posts 比对，标出新增/交易类
$PY $S tokens       # 2b. 从本机 Chrome 缓存捞历史笔记的 id+xsec_token（可选）
$PY $S fetch        # 3. 抓新增笔记详情 → /tmp/opencode/xhs/detail_*.json
                    #    历史笔记：fetch --tokens .xhs-tokens.json（全量重抓）
$PY $S images       # 4. 下图片 → source/img/xhs/<note_id>/NN.webp（统一 WebP）
$PY $S videos       # 4b. 视频笔记下 mp4 → source/img/xhs/<note_id>/video.mp4（h264 优先）
$PY $S markdown     # 5. 生成文章 → source/_posts/<id 前 7 位>.md
$PY $S check        # 5b. 资产自检：图片都是真 WebP、视频都被文章引用

pnpm run clean && pnpm run build     # 6. 本地验证，必须无 ERROR
git add -A && git commit -m "同步小红书新增N篇…" && GIT_CONFIG_GLOBAL=$PWD/.gitconfig-xiaoqi git push
```

`$PY $S all` 会串起 1–5 步；发布这一步脚本不代劳（需要看 build 结果、写 commit message）。

## 每一步怎么工作 / 出问题怎么查

### 1. `cookies` — 登录态
- 复制 `~/.config/google-chrome/Default/Cookies`（只读快照，不动原库）。
- 取 gnome-keyring 里 label 为 `Chrome Safe Storage` 的口令，
  `PBKDF2-SHA1(salt='saltysalt', iter=1, dkLen=16)` → AES-128-CBC key，IV = 16 个空格。
- 解 `v10/v11` 前缀密文；新版 Chrome 明文前有 32 字节 host_key 哈希，需剥掉。
- 产物 `.xhs-cookies.json` / `.xhs-cookies-raw.txt`，`chmod 600`。
- **cookie 只在用户真正访问小红书时才刷新落盘**：读出来若已失效，请用户先在 Chrome
  打开/刷新一次 `https://www.xiaohongshu.com` 再重跑。

### 2. `list` — 笔记清单（自检就在这一步）
- `GET /user/profile/{user_id}`，解析 `window.__INITIAL_STATE__`：
  先 `:undefined → :null`、`,undefined → ,null`，再 `json.JSONDecoder().raw_decode`。
- 数据位置：`user.notes[0]`（数组），每项 `{id, xsecToken, noteCard{displayTitle, time, type}}`。
- **登录态有效的两个标志**：HTTP 200 且 HTML 含昵称；每项 `id` 是完整 24 位 hex。
  - 302 → `/login`：没登录。
  - 200 但 `id` / `noteCard.noteId` 全是空字符串：被降级（会话不可信），只能拿到标题，
    必须先把登录态弄好再看。
- 第一页 30 篇、按时间倒序，通常已覆盖半年内的新增，**增量同步够用**。
  SSR 不接受 cursor/page 翻页；要更早的历史只能靠浏览器滚动拦 `user_posted` 接口，
  而那违反铁律 1，除非用户明确授权，否则不要做（也接受「老笔记是否被删」无法全量核对）。

### 2b. `tokens` — 历史笔记的 xsec_token（不开浏览器）

**先搞清 token 是什么**：`xsec_token` 不是 cookie，是**单篇笔记**的访问凭证。
cookie 只有登录态（`web_session` / `id_token` / `a1` 等 16 个），主页 SSR 返回 200 且带昵称
就说明登录完全正常；但 `/explore/<id>` 不带 token 一律 302 到 `/404/sec_xxx`
（实测裸链接、`/discovery/item/`、`?xsec_source=pc_share` 全是 302）。
所以「没退出登录却没有 token」是正常现象，不是登录失效。

token 只由 `user_posted` 翻页接口下发，主页 SSR 只给第一页 30 条；直接调该接口要签名，
违反铁律 2。**替代方案：从本机 Chrome 磁盘缓存里捞**——浏览器自己签名的响应会落盘。

```bash
$PY $S tokens      # 扫 ~/.cache/google-chrome/Default/Cache，解析 user_posted 的 JSON
```

- 产物 `.xhs-tokens.json`（`chmod 600`，已 gitignore）：`{note_id: {tok,title,type,time}}`。
- 缓存条目是 Chrome simple cache 格式：头部 `\0` 分隔，body 是 gzip/zlib 流，
  靠魔数 `1f 8b 08` 定位后 `zlib.decompress(..., 31)`；直接 `gzip.GzipFile` 会报错。
- 只有「在过去某次滚动中加载过」的页才在缓存里。想覆盖更早历史：让用户自己在
  Chrome 里打开主页滚到底（同设备同 profile，**不要**用 Playwright 新开浏览器），
  然后重跑 `tokens`。
- 实测 2026-11-14：缓存捞到 56 条（2024-12-01 → 2026-09-27），加上首页第一页 30 条
  共覆盖博客 64 篇里的 62 篇；剩下 2 篇在所有缓存页里都不存在（多半已被用户删除）。

### 3. `fetch` — 详情
- `GET /explore/{id}?xsec_token={tok}&xsec_source=pc_user`。
- ⚠️ 详情页 SSR 里有 `new Map([])` 之类 JS 字面量，解析前必须把
  `new (Map|Set|Date|WeakMap|WeakSet|Uint8Array|Array)(...)` 替换成 `null`，
  否则报 `Expecting value`（主页 SSR 一般不需要，详情页需要）。
- 取 `noteDetailMap[id].note`：`desc`（正文，带 `#话题[话题]#`）、`imageList`（图片）、
  `time`（ms）、`type`（normal / video）。
- 视频笔记 `imageList` 只有封面，真正的视频在 `video.media.stream`；必须跑 `videos` 步骤。
- 给**已同步过**的老笔记补抓（如补视频）：`fetch --ids <完整24位id> …` 会强制重抓，
  之后 `videos --ids …` + `markdown` 重生成同名文章。
- 全量历史重抓：`fetch --tokens .xhs-tokens.json`（池里的 id 一律重抓，不受「已有文章跳过」影响），
  接着 `images --ids <池里所有 id>` → `videos` → `markdown`。重抓前 `images` 会先清空该篇旧图。
- ⚠️ 老笔记（不在第一页）没有 `xsec_token`，`/explore/{id}` 会 302，抓不到，只能放弃。

### 4. `images` — 图片
- xhscdn 带 `Referer: https://www.xiaohongshu.com/` 即可下载；URL 有时间戳路径，别缓存太久。
- 存 `source/img/xhs/<完整 24 位 id>/NN.webp`（按图序 01/02/…）。
- xhscdn 回的是 **WebP**，脚本原样落盘（不重编码）；万一回 JPEG/PNG 才用 Pillow
  转 WebP（quality 82, method=6）。

**格式约定：一律 WebP（用户 2026-11-14 定，当日先定 JPEG 后又改回 WebP）**
- 图片统一存 `.webp`：扩展名与内容一致，体积比 JPEG 小约 28%（全站 191 张 33MB → 24MB）。
- xhscdn 原本就回 WebP → 直接落盘，别转来转去；换来的是零重编码损失。
- 引用一律按**磁盘实际文件名**生成（`.webp`），cover / gallery / video poster 三处都要跟上；
  老文章迁移后要同步改 md 里的 `/img/xhs/<id>/NN.jpg` → `.webp`。
- 历史图若当年被转过 JPEG，可以用 `fetch --tokens` + `images --ids` 重抓原图：
  xhscdn 给的就是 WebP，原样落盘即**零重编码**（重抓前脚本会先清空该篇旧图）。
- 校验魔数（不要只信扩展名）：WebP 头 `RIFF....WEBP`。`check` 会同时报「格式异常」
  和「遗留 .jpg」，两者都必须是 0。

### 4b. `videos` — 视频
- 视频直链在 `video.media.stream`，`EF4`=h264（兼容最好，**默认选它**），
  `EF5`=h265/hevc（Firefox、部分安卓播不了，别当默认）。
- ⚠️ `sns-video-v2.xhscdn.com` 的 masterUrl 一律 **403**；要改用 `backupUrls` 里的
  `sns-bak-v*.xhscdn.com`（**只走 http**），带 `Referer` 才能拿到 mp4。
- 存 `source/img/xhs/<id>/video.mp4`；实测 15 秒左右的视频 h264 约 1–6MB，
  长的录屏能到几十 MB（2026-11 有条 4 分 24 秒的 95MB），用户要求原样保留、不转码。
- mp4 不在 `hexo-offline.config.cjs` 的预缓存 glob 里，不会被塞进 Service Worker，按需加载。

### 5. `markdown` — 文章
- front-matter：`title` / `date`（笔记发布时间）/ `cover`(首图) / `cover_type: img` /
  `series`（命中主题词才有）/ `tags` / `categories: ["小红书"]` / `description`。
- 正文：`desc` 去掉话题标记 → `<!-- more -->` → 视频（有 `video.mp4` 时放原生
  `<video controls poster=首图>`）→ `{% gallery %}` 图片墙 →
  `{% note info %}本文同步自小红书（柒柒）{% endnote %}`。
- 视频笔记只有封面一张图时不再重复出画廊（poster 已经显示封面）。
- ⚠️ `description` / `title` 必须清掉 `@ [ ]` 等 YAML 构造字符，否则 Hexo 报 `Process failed`。
- 纯话题笔记（desc 只有 `#xxx[话题]#`）要兜底标题，正文只剩画廊也正常。
- 文件名 = `id` 前 7 位（`<七位>.md`），图片目录用完整 24 位 id——两者不要搞反。
- ⚠️ 详情 SSR 的 `title` 经常为空（纯话题笔记），标题必须能兜底到卡片标题：
  `fetch` 会把主页/缓存卡片的 `displayTitle` 写进 detail json 的 `meta`，
  `markdown` 的顺序是 详情 title → noteCard → meta.displayTitle → 正文前 20 字。
  漏了这层兜底，重抓会把已有标题覆盖成「小红书笔记 xxxxxxxx」。

### 6. `check` — 资产自检
- 扫 `source/img/xhs` 下所有图片：`.webp` 必须真是 WebP，出现 `.jpg` 算「未迁移」。
- 扫 `source/img/xhs/*/video.mp4`，确认 `source/_posts/<七位>.md` 里引用了它，
  防止视频下了却忘了重跑 `markdown`（或文章被手改丢了播放器）。
- 有异常就 `exit 1`；`all` 末尾会自动跑一次。

## 内容取舍规则（用户 2026-10-10 定）

- **出物 / 交易类一律不同步**（卖闲置、出娃/谷/卡、换物、拼团如「自抱盒/成团」）。
  判定看标题和正文，命中 `出物/出闲置/可刀/包非偏/非偏/出/换/出换/走平台/提确/平换/寄给你/垃圾包…`
  即跳过；`fetch` 默认自动跳过，`--include-trade` 可强制抓。
- 已同步的若后来发现是交易类，要连同 `source/img/xhs/<id>/` 一起删。
- 笔记在 XHS 被用户删掉后，博客对应文章也应删除（第一页范围内可核对，更早的核不到）。

## 发布

- `pnpm run build` 无 ERROR → `git add -A` → commit → push（用 `.gitconfig-xiaoqi` 小七身份）。
- 推送触发 GitHub Actions，约 1–2 分钟上线 `https://777.hanphone.cn`。
- 验证：`curl -o /dev/null -w '%{http_code}' https://777.hanphone.cn/posts/<七位id>/`
  返回 200 即部署完成；新文章刚生成时前几次可能 404，等 Actions 跑完再试。
- 跳过的交易类文章线上应是 404（不要写进站点）。
