# 小红书笔记同步到博客 · 经验总结

> 本文记录「把小七小红书主页公开笔记同步为 Hexo 博客文章」的完整流程与踩坑经验，供后续再次同步时参考。最后更新：2026-09-27（已成功同步 58 篇）。

## 一、目标与原理

把小红书用户「柒柒」(`user_id: 649d592e0000000011000515`) 主页全部公开笔记，转成 `source/_posts/` 下的 Hexo 文章，图片放 `source/img/xhs/<note_id>/`，最终 `pnpm run publish` 发布。

**关键事实**：
- 小红书用户主页/笔记详情/正文图片全部需要**登录态或分享 token**（`xsec_token`），匿名访问跳登录墙（404 error_code 300031 / 重定向 /login）。
- 带有效 cookie 的 **HTTP SSR 请求可读**：主页 SSR、笔记详情 SSR（`/explore/{note_id}?xsec_token=...&xsec_source=pc_user`）。
- **headless 浏览器会被 IP 级风控拦截**（300012 IP存在风险 / 300013 访问频繁），即使带 cookie 也一样；但同 IP 下普通 HTTP 请求正常。

## 二、完整流程（已跑通，2026-09-27）

### 1. 获取有效登录态

会话 = 用户浏览器真实登录成功后导出的最新 cookie。web_session 绑定设备/指纹，**跨会话导出会失效**，所以：
- 用户在已登录的 Chrome 打开 `https://www.xiaohongshu.com`，F12 → Application → Cookies → 复制 `Name=Value` 整段。
- 保存为仓库根目录 `.xhs-cookies-raw.txt`（gitignored），用 `.venv-xhs/scripts/build_cookie_json.py` 转成 `.xhs-cookies.json`。
- ⚠️ 每次会话只维持几小时到一天，失效后 SSR 会跳 `/website-login/captcha` 或 `/login`，需用户重新导出。

### 2. 抓取全部笔记 id + xsecToken

**阶段 A：主页 SSR（第一页约 31 篇）**
```python
# requests + cookie GET https://www.xiaohongshu.com/user/profile/{user_id}
# 解析 window.__INITIAL_STATE__（注意：先把 :undefined 变 :null，new Map/Set(...) 变 null）
# user.notes[0] 数组即最新笔记卡，含 id/xsecToken/displayTitle/time
```

**阶段 B：翻页（剩余笔记）**
- SSR **不接受** cursor/page 参数翻页。
- 有头浏览器（Playwright `channel=chrome`，真实 Chrome 指纹）打开主页，滚动触发页面自身调用 `/api/sns/web/v1/user_posted`，**监听 response 捕获**。
- ⚠️ 响应字段是 `note_id`/`xsec_token`/`display_title`/`time`（不是 `id`/`xsecToken`）。
- ⚠️ 不要自己用 xhshow 直调 API：极易触发风控（406 → 461 登录过期 → 300011 账号异常），代价是账号被标记需要冷却数小时~1天。**让浏览器页面自己签名最安全**。

生产脚本：`.venv-xhs/scripts/fetch_profile_new.py`（SSR）+ 有头浏览器监听 API。

### 3. 逐篇抓详情

```python
# GET https://www.xiaohongshu.com/explore/{note_id}?xsec_token={tok}&xsec_source=pc_user
# 解析 __INITIAL_STATE__ → noteDetailMap → {note_id: {note: {desc, imageList, time, interactInfo, type}}}
```
- `desc` = 正文（含 `#话题[话题]#` 标记，生成文章时清理）
- `imageList[]` = 图片列表（`urlDefault` 或 `infoList[].url`）
- `video` = 视频笔记（取 `desc` 与封面即可）
- `time` = 发布时间（ms 时间戳）
- `interactInfo` = 点赞/收藏/评论数

生产脚本：`.venv-xhs/scripts/fetch_details.py`（含 fetch_details_rest.py 补抓）。

### 4. 下载图片

xhscdn 图片带 `Referer: https://www.xiaohongshu.com/` 即可下载（HTTP 200）。存 `source/img/xhs/<note_id>/NN.jpg`（按图序 01/02/...）。

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
3. **cookie 有效期短**：依赖用户浏览器实时导出。捉到先验证（主页 SSR 含「柒柒 - 小红书」标题 + 笔记卡）再批量。
4. **v11 加密 cookie**：不能直接读 Chrome 数据库解密（app-bound encryption），复制 profile 会被 Chrome 重置；唯一可靠路径 = 用户浏览器 DevTools 导出。
5. **不要开独立的有头浏览器窗口让用户扫二维码**：用户远程看不到该窗口；结论是直接用用户浏览器里已登录的会话。
6. **SSR 的 `__INITIAL_STATE__`** 是 JS 对象不是纯 JSON：需 `:undefined→:null`、`new Map(...)/new Set(...)→null` 才能 `json.loads`。
7. **图片 URL 带有效期**：xhscdn URL 有时间戳路径分段，尽快下载。

## 四、后续再次同步时的快速路线

1. 用户从 Chrome 导出最新 cookie → 存 `.xhs-cookies-raw.txt` → `build_cookie_json.py` 转 json。
2. 跑 `fetch_profile_new.py` 拿 SSR 第一页 → 有头浏览器监听 `user_posted` 拿全部 id。
3. 对比 `source/_posts/` 已有文章，只抓缺失的笔记详情 → 下载图片 → `gen_markdown.py` 生成 → build → publish。