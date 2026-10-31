# 小红书笔记同步到博客 · 经验总结

> 本文记录「把小七小红书主页公开笔记同步为 Hexo 博客文章」的完整流程与踩坑经验，供后续再次同步时参考。最后更新：2026-11-01（已同步 62 篇）。

## 一、目标与原理

把小红书用户「柒柒」(`user_id: 649d592e0000000011000515`) 主页全部公开笔记，转成 `source/_posts/` 下的 Hexo 文章，图片放 `source/img/xhs/<note_id>/`，最终 `pnpm run publish` 发布。

**关键事实**：
- 小红书用户主页/笔记详情/正文图片全部需要**登录态或分享 token**（`xsec_token`），匿名访问跳登录墙（404 error_code 300031 / 重定向 /login）。
- 带有效 cookie 的 **HTTP SSR 请求可读**：主页 SSR、笔记详情 SSR（`/explore/{note_id}?xsec_token=...&xsec_source=pc_user`）。
- **headless 浏览器会被 IP 级风控拦截**（300012 IP存在风险 / 300013 访问频繁），即使带 cookie 也一样；但同 IP 下普通 HTTP 请求正常。

## 二、完整流程（已跑通，2026-09-27）

### 1. 获取有效登录态

会话 = 用户浏览器真实登录后的最新 cookie。web_session 绑定设备/指纹，**跨会话导出会失效**。

**首选：直接从本机 Chrome 的 cookie 库读（2026-11 打通，无需用户手动导出）**
- `.venv-xhs/scripts/extract_cookies_from_chrome.py`：复制 `~/.config/google-chrome/Default/Cookies` → 用 gnome-keyring 里 label 为 `Chrome Safe Storage` 的口令，`PBKDF2-SHA1(salt='saltysalt', iter=1, dkLen=16)` 派生 AES-128-CBC key、IV=16 个空格，解 `v10/v11` 密文；新版 Chrome 明文前有 32 字节 host_key 哈希，要剥掉。产物写 `.xhs-cookies-raw.txt` / `.xhs-cookies.json`（均 chmod 600、gitignored）。
- 会话空闲很久后 cookie 只在用户**真正访问一次小红书**时才会刷新落盘，读出来若是失效的旧会话，让用户在 Chrome 打开/刷新一次主页再读即可。
- 备选（Chrome 打不开时）：F12 → Application → Cookies → 复制 `Name=Value` 整段存 `.xhs-cookies-raw.txt`，跑 `build_cookie_json.py`。

**⚠️ 绝对不要新开浏览器实例**（Playwright / 新 Chrome 窗口都算）：
- 小红书会把它当成**新设备登录**，触发「电脑登录设备超限」，直接把正式会话踢下线——2026-11-01 就是踩了这个坑，登录态当场失效，只能请用户重新登录。
- 同步全程只用「cookie + requests 纯 HTTP」：主页 SSR、详情 SSR、图片下载都够用，完全不需要浏览器。

**登录态自检**（花的请求最少的一步）：
- 用 cookie 请求主页 `/user/profile/{user_id}`，返回 302 → `/login` 即失效；200 且 HTML 里有昵称 → 有效。
- 有效的标志还有一个：SSR 里 `user.notes[0]` 每项的 `id` / `noteCard.noteId` 是完整 24 位 id。**若 id、noteId 全是空字符串，就是被降级（未登录/会话不可信），只能拿到标题和时间**，别拿它继续往下跑。

### 2. 抓取全部笔记 id + xsecToken

**阶段 A：主页 SSR（第一页 30 篇，覆盖约半年）**
```python
# requests + cookie GET https://www.xiaohongshu.com/user/profile/{user_id}
# 解析 window.__INITIAL_STATE__（注意：先把 :undefined 变 :null，new Map/Set(...) 变 null）
# user.notes[0] 数组即最新笔记卡，含 id/xsecToken/displayTitle/time
```

**增量同步时阶段 A 就够了**：第一页按时间倒序排 30 篇，通常已经覆盖上次同步之后的全部新增。跑完先比对 `source/_posts/`（文件名是 id 前 7 位），只要「新增」那几篇都落在这一页里、最老一篇博客里已有，就可以跳过阶段 B。

**阶段 B：翻页（补历史 / 需要全量时）**
- SSR **不接受** cursor/page 参数翻页。
- 只能靠浏览器滚动触发页面自身调用 `/api/sns/web/v1/user_posted` 再监听 response——但这会新开浏览器实例，**会触发设备上限踢号**（见第 1 节），除非用户明确同意，否则不要做。
- ⚠️ 响应字段是 `note_id`/`xsec_token`/`display_title`/`time`（不是 `id`/`xsecToken`）。
- ⚠️ 不要自己用 xhshow 直调 API：极易触发风控（406 → 461 登录过期 → 300011 账号异常），代价是账号被标记需要冷却数小时~1天。

生产脚本：`.venv-xhs/scripts/fetch_profile_new.py`（SSR）+ `fetch_new_details_2026_11.py`（只抓新增笔记详情）。

### 3. 逐篇抓详情

```python
# GET https://www.xiaohongshu.com/explore/{note_id}?xsec_token={tok}&xsec_source=pc_user
# 解析 __INITIAL_STATE__ → noteDetailMap → {note_id: {note: {desc, imageList, time, interactInfo, type}}}
```
- ⚠️ 详情页 SSR 里会出现 `new Map([])` 等 JS 字面量，解析前必须
  `re.sub(r"new (Map|Set|Date|WeakMap|WeakSet|Uint8Array|Array)\([^()]*\)", "null", s)`，
  否则 `raw_decode` 直接报 `Expecting value`（主页 SSR 一般不需要，详情页需要）。
- `desc` = 正文（含 `#话题[话题]#` 标记，生成文章时清理）
- `imageList[]` = 图片列表（`urlDefault` 或 `infoList[].url`）
- `video` = 视频笔记（取 `desc` 与封面即可）
- `time` = 发布时间（ms 时间戳）
- `interactInfo` = 点赞/收藏/评论数

生产脚本：`.venv-xhs/scripts/fetch_details.py`（含 fetch_details_rest.py 补抓）。

### 4. 下载图片

xhscdn 图片带 `Referer: https://www.xiaohongshu.com/` 即可下载（HTTP 200）。存 `source/img/xhs/<note_id>/NN.jpg`（按图序 01/02/...）。

- ⚠️ 现在 xhscdn 默认回 **WebP**，但文件按 `.jpg` 命名保存，`file` 一看就是 `RIFF ... Web/P`。仓库里历史图片是真 JPEG，为保持一致（也避免个别环境/缓存按扩展名判断类型），下完用 Pillow 转一次：
  ```python
  from PIL import Image
  im = Image.open(p); im.convert("RGB").save(p, "JPEG", quality=88, optimize=True)
  ```

生产脚本：`.venv-xhs/scripts/download_images.py`。

### 5. 生成 Markdown

`.venv-xhs/scripts/gen_markdown.py` 负责转换：
- front-matter：`title`（笔记标题，纯话题笔记兜底）、`date`（笔记发布时间）、`tags`（按主题关键词映射：BJD/洛克王国/chiikawa/邦倪兔/王者荣耀/棉布娃娃）、`categories: [小红书]`、`description`。
- 正文：`desc`（清理 `#xxx[话题]#` 标记），结尾加图片画廊。
- ⚠️ **front-matter 坑**：
  - `description` 要清理 `#`/`@`/`[`/`]` 等 YAML 特殊字符，否则 Hexo 构建报 `Process failed`。
  - `title` 也需清理话题标记；纯话题笔记用主题关键词兜底标题。
- 文件名 = `note_id.md`（24 位 hex，唯一且与图片目录对应）。

### 6. 发布

```bash
pnpm run build   # 本地验证，无 ERROR
pnpm run publish # git add -A + commit + push（自动用 .gitconfig-xiaoqi 小七身份，触发 Actions）
```
- GitHub Actions 自动 build 并部署到 gh-pages，约 1 分钟。
- ⚠️ PWA Service Worker 会缓存新文件；改 `_config*.yml` 需重新 build 验证再 push。

## 三、踩坑清单（务必记住）

1. **不要在本机反复直调 API**：签名直调极易触发风控，后果是账号被标记（需冷却），严重时影响用户正常使用。用「有头浏览器 + 页面自身签名」。
2. **headless 必被拦**：Playwright 请用 `channel="chrome"` 有头 + 真实系统 Chrome；注入 cookie 时 headless 页面打不开 xhs（风控）。
3. **cookie 有效期短**：依赖用户浏览器实时访问刷新。读出来先验证（主页 SSR 含「柒柒 - 小红书」标题 + 笔记卡 + 非空 24 位 id）再批量。
4. **v11 加密 cookie 在本机是可解的**（2026-11-01 验证）：Chrome Linux 用 gnome-keyring 的 `Chrome Safe Storage` 作口令，详见 `.venv-xhs/scripts/extract_cookies_from_chrome.py`。不需要 DevTools 手动导出。
5. **绝对不要新开浏览器（Playwright / 新 Chrome 窗口 / 新 profile）**：小红书判定为「新设备登录」，触发「电脑登录设备超限」，会把用户正式会话踢下线，同步立刻断。2026-11-01 踩过一次，代价是请用户重新登录。全程只用 requests + cookie。
6. **SSR 的 `__INITIAL_STATE__`** 是 JS 对象不是纯 JSON：需 `:undefined→:null`、`new Map(...)/new Set(...)→null` 才能 `json.loads`。
7. **图片 URL 带有效期**：xhscdn URL 有时间戳路径分段，尽快下载。
8. **SSR 里 id 为空 = 会话被降级**：主页 SSR 每项 `id`/`noteCard.noteId` 都为空字符串时，说明服务端没把你当登录用户（登录态失效或指纹不匹配），此时只能拿到标题和时间，必须先解决登录态。

## 四、后续再次同步时的快速路线

1. `.venv-xhs/bin/python .venv-xhs/scripts/extract_cookies_from_chrome.py`（前提：用户在 Chrome 里登录着小红书，且最近访问过一次让 cookie 落盘）。
2. `fetch_profile_new.py` 拿 SSR 第一页 → 与 `source/_posts/` 的 7 位 id 比对，得到新增列表。
3. `fetch_new_details_2026_11.py` 只抓新增笔记详情（顺带按交易类关键词跳过）→ `download_images.py`（之后 WebP→JPEG）→ `gen_markdown.py` → 把 24 位文件名改成 `id[:7].md` → `pnpm run clean && pnpm run build` → build 无 ERROR 后 commit + push。

## 五、内容取舍规则（2026-10-10 定）

- **出物 / 交易类笔记一律不同步，且已同步的要删除**：卖闲置、出娃/谷/卡、换物、拼团（含「自抱盒/成团」等团购协调）都算交易类，用户要求「有关于出物的全部删除」。
- 判定看正文而非只看标题：命中 `出物/出闲置/可刀/包非偏/走平台/提确/平换/寄给你` 等交易话术的即交易类。
- 同步后要**双向核对**笔记集合：`source/_posts/` 有、而 XHS 已没有的（用户自己删了）也要从博客删除（连同 `source/img/xhs/<note_id>/`）。
- **拼团 ≠ 内容笔记**：如「推推不落幕幻梦集自抱盒团」这类团购帖，用户明确按交易类跳过。
- 注意 `gen_markdown.py` 生成的文件名是**完整 24 位 note_id**，与仓库既有习惯（7 位短 id）不一致，生成后需手动重命名为 `id[:7].md`。

### 本机快速核对命令
```bash
# 读 Chrome 登录态（不开浏览器）
.venv-xhs/bin/python .venv-xhs/scripts/extract_cookies_from_chrome.py
# SSR 首页第一页（cookie 有效时）
.venv-xhs/bin/python .venv-xhs/scripts/fetch_profile_new.py
# 比对差集：NEW=博客缺、GONE=博客多（用户已从 XHS 删除）
```

> ⚠️ 本次踩坑：`fetch_profile.py` 的 `INITIAL_STATE` 正则新版本会截断，需改为「定位 `__INITIAL_STATE__=` 后 `json.JSONDecoder().raw_decode`，并先 replace `:undefined`→`:null`」。浏览器端 `JSON.stringify(window.__INITIAL_STATE__)` 会因循环引用报错，改为只提取 `user.notes` 的纯字段。