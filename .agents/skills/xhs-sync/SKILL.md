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
$PY $S fetch        # 3. 抓新增笔记详情 → /tmp/opencode/xhs/detail_*.json
$PY $S images       # 4. 下图片 → source/img/xhs/<note_id>/NN.jpg（WebP 自动转 JPEG）
$PY $S markdown     # 5. 生成文章 → source/_posts/<id 前 7 位>.md

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

### 3. `fetch` — 详情
- `GET /explore/{id}?xsec_token={tok}&xsec_source=pc_user`。
- ⚠️ 详情页 SSR 里有 `new Map([])` 之类 JS 字面量，解析前必须把
  `new (Map|Set|Date|WeakMap|WeakSet|Uint8Array|Array)(...)` 替换成 `null`，
  否则报 `Expecting value`（主页 SSR 一般不需要，详情页需要）。
- 取 `noteDetailMap[id].note`：`desc`（正文，带 `#话题[话题]#`）、`imageList`（图片）、
  `time`（ms）、`type`（video 笔记取 desc + 封面即可）。

### 4. `images` — 图片
- xhscdn 带 `Referer: https://www.xiaohongshu.com/` 即可下载；URL 有时间戳路径，别缓存太久。
- 存 `source/img/xhs/<完整 24 位 id>/NN.jpg`（按图序 01/02/…）。
- ⚠️ xhscdn 现在默认回 **WebP**，仍按 `.jpg` 保存会得到「扩展名是 jpg 的 webp」。
  脚本用 Pillow 转成真 JPEG（quality 88），跟仓库历史图片一致。

### 5. `markdown` — 文章
- front-matter：`title` / `date`（笔记发布时间）/ `cover`(首图) / `cover_type: img` /
  `series`（命中主题词才有）/ `tags` / `categories: ["小红书"]` / `description`。
- 正文：`desc` 去掉话题标记 → `<!-- more -->` → `{% gallery %}` 图片墙 →
  `{% note info %}本文同步自小红书（柒柒）{% endnote %}`。
- ⚠️ `description` / `title` 必须清掉 `@ [ ]` 等 YAML 构造字符，否则 Hexo 报 `Process failed`。
- 纯话题笔记（desc 只有 `#xxx[话题]#`）要兜底标题，正文只剩画廊也正常。
- 文件名 = `id` 前 7 位（`<七位>.md`），图片目录用完整 24 位 id——两者不要搞反。

## 内容取舍规则（用户 2026-10-10 定）

- **出物 / 交易类一律不同步**（卖闲置、出娃/谷/卡、换物、拼团如「自抱盒/成团」）。
  判定看标题和正文，命中 `出物/出闲置/可刀/包非偏/走平台/提确/平换/寄给你/垃圾包…`
  即跳过；`fetch` 默认自动跳过，`--include-trade` 可强制抓。
- 已同步的若后来发现是交易类，要连同 `source/img/xhs/<id>/` 一起删。
- 笔记在 XHS 被用户删掉后，博客对应文章也应删除（第一页范围内可核对，更早的核不到）。

## 发布

- `pnpm run build` 无 ERROR → `git add -A` → commit → push（用 `.gitconfig-xiaoqi` 小七身份）。
- 推送触发 GitHub Actions，约 1–2 分钟上线 `https://777.hanphone.cn`。
- 验证：`curl -o /dev/null -w '%{http_code}' https://777.hanphone.cn/posts/<七位id>/`
  返回 200 即部署完成；新文章刚生成时前几次可能 404，等 Actions 跑完再试。
- 跳过的交易类文章线上应是 404（不要写进站点）。
