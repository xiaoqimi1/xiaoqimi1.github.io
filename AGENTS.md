# AGENTS.md — 小七的博客（xiaoqi-blog）

面向 AI / 开发者接手本项目的手册。请先读完本文件再动手。

## 项目是什么

小七（GitHub: `xiaoqimi1`）的个人博客，Hexo 静态站，主题为 Butterfly。
线上地址：`https://777.hanphone.cn`（自定义域名，CNAME 指向 `xiaoqimi1.github.io`）。

> 注意：`777.hanphone.cn` 是寒枫（`HanphoneJan`）的域名，GitHub Pages 站点属于小七（`xiaoqimi1`）。两者的 GitHub 账号相互独立。

## 技术栈与环境

- Hexo `^8.1`，主题 `hexo-theme-butterfly 5.7`（源码放在 `themes/butterfly/`，随仓库一起管理）
- 包管理：**pnpm**（Node 24，`.nvm` 管理）。`pnpm-workspace.yaml` 里有 `allowBuilds: hexo-util: true`（pnpm10+ 默认拦截依赖构建脚本，必须保留否则 hexo-util 无法编译）
- 渲染插件：`hexo-renderer-pug`、`hexo-renderer-stylus`、`hexo-generator-search`（本地搜索）、`hexo-generator-feed`
- 增强插件：`hexo-generator-sitemap`（sitemap.xml）、`hexo-wordcount`（字数/阅读时长，主题 `wordcount.enable: true`）、`hexo-filter-nofollow`（外链 nofollow）、图片懒加载用主题自带 `lazyload.enable: true, native: true`（浏览器原生，无需插件）
- PWA：`hexo-offline`（基于 workbox-build 生成 Service Worker + 注入注册脚本）
- **不要**安装/使用 `hexo-deployer-git`，部署走 GitHub Actions

## 目录结构

```
xiaoqi-blog/
├── _config.yml              # Hexo 站点配置（标题/作者/url/permalink）
├── _config.butterfly.yml    # Butterfly 主题配置（导航/背景/PWA/注入CSS）
├── package.json             # 脚本: new/build/server/publish
├── pnpm-workspace.yaml      # allowBuilds（勿删）
├── hexo-offline.config.cjs  # PWA / Service Worker 缓存配置
├── AGENTS.md                # 本文档
├── docs/                    # 文档（WRITING.md 写作、CUSTOMIZATION.md 定制、XHS-SYNC.md 小红书同步经验）
├── .github/workflows/deploy.yml  # 构建并部署到 gh-pages 分支
├── source/
│   ├── _posts/*.md          # 文章（Markdown，front-matter 含 title/date/tags/categories）
│   ├── img/                 # 图片资源（background.jpg 是壁纸背景，avatar.jpg 是头像）
│   ├── img/xhs/<note_id>/   # 小红书同步的笔记图片（文件名 NN.jpg 按序）
│   ├── img/pwa/             # PWA 图标 + favicon（由头像照片 avatar.jpg 生成，见下文）
│   ├── manifest.json        # PWA 应用清单（构建后进入 public 根目录）
│   ├── CNAME                # 自定义域名 777.hanphone.cn（构建后进入 public 根目录，勿删）
│   ├── tags|categories|about/index.md  # 三个独立页面
└── themes/butterfly/        # 主题源码
```

## 常用命令

```bash
pnpm new "文章标题"        # 新建文章（source/_posts/）
pnpm run build            # 本地生成到 public/
pnpm run clean            # 清空 public/
pnpm run server           # 本地预览 http://localhost:4000
pnpm run publish          # git add -A + commit + push（推 main 触发 Actions 自动部署）
```

**发文章流程**：写 Markdown → `pnpm run publish`（或手动 `git add/commit/push`）→ GitHub Actions 构建 → 发布到线上，约 1 分钟。

> 📌 同步小红书笔记成文章的完整流程与踩坑经验见 [`docs/XHS-SYNC.md`](docs/XHS-SYNC.md)。一句话版：登录态取自用户已登录 Chrome 导出的最新 cookie（存 `.xhs-cookies*`，gitignored）→ SSR 抓主页第一页 + 有头浏览器监听 `user_posted` 接口拿全部笔记（禁止自己直调 API，会触发风控）→ 逐篇抓详情 → 图片下载到 `source/img/xhs/<note_id>/` → `gen_markdown.py` 生成文章 → build → publish。

## 部署架构（重要）

- **main 分支** = 博客源码
- **gh-pages 分支** = 构建产物（`public/`），由 GitHub Actions 自动生成并推送
- GitHub Pages 设置：**Deploy from a branch → gh-pages / (root)**
- 修改 `_config.yml` / `_config.butterfly.yml` 后必须重新 `pnpm run build` 验证，再 `git push` 触发部署

## PWA（离线 / 可安装）

- 由 `hexo-offline` 实现：构建时用 workbox 生成 `public/service-worker.js`，并把注册脚本注入 `public/index.html`；同时在 `<head>` 注入 manifest / apple-touch-icon / favicon 链接（来自主题自带 `pwa` 配置）。
- 关键文件：
  - `hexo-offline.config.cjs`：workbox 配置（预缓存 glob、jsdelivr/unpkg/字体 CDN 运行时缓存、`skipWaiting` + `clientsClaim`）
  - `source/manifest.json`：应用清单（name/theme_color/start_url/icons），构建后落到 `public/` 根目录
  - `source/img/pwa/`：图标由**头像照片**（`source/img/avatar.jpg`）生成（favicon-16/32、icon-192/512、maskable-192/512、apple-touch-icon 180），与头像取景一致
- 换图标流程：重新裁好 `source/img/avatar.jpg`（400×400）后，用 sharp 从它导出各尺寸 PNG（512/192 建议 `png({palette:true, colours:256})` 压缩，否则照片 PNG 可达 450KB），覆盖 `source/img/pwa/` 下同名文件，保持 `manifest.json` 里路径不变。
- 已验证：`pnpm run build` 后 `public/` 含 `service-worker.js`（预缓存全部静态资源，约 1.5MB）、`manifest.json`、图标，`index.html` 末尾注入 SW 注册脚本。
- 注意：SW 注册脚本只在 `hexo generate` 阶段写入 `public/`，本地 `hexo server` 预览页不会显示（属正常，部署即生效）。PWA 需 HTTPS，线上已满足。

## 远程图片接收流程（OpenChamber 附件）

用户通过 OpenChamber 远程对话时，发的图片附件**不会落到磁盘**，而是以 base64 存在 opencode 会话库里。新会话收到"图片已发给你"这类消息时，按以下步骤提取：

1. 查最新附件（找 `"type":"file"` 的 part）：
```bash
python3 -c "
import sqlite3, json
con=sqlite3.connect('/home/hanphone/.local/share/opencode/opencode.db')
for r in con.execute(\"SELECT id, time_created, data FROM part ORDER BY time_created DESC LIMIT 20\"):
    d=json.loads(r[2])
    if d.get('type')=='file':
        print(r[0], r[1], d.get('filename'), d.get('mime'))
"
```
2. 提取并保存为文件（把 `<part_id>` 换成上面输出的 id）：
```bash
python3 -c "
import sqlite3, json, base64
con=sqlite3.connect('/home/hanphone/.local/share/opencode/opencode.db')
d=json.loads(con.execute(\"SELECT data FROM part WHERE id='<part_id>'\").fetchone()[0])
url=d['url']; ext=d['mime'].split('/')[-1]
open('/tmp/opencode/attachment.'+ext,'wb').write(base64.b64decode(url.split(',',1)[1]))
print('saved /tmp/opencode/attachment.'+ext)
"
```
3. 校验：`file /tmp/opencode/attachment.jpg` + sharp 读尺寸 → 拷进 `source/img/`（或 `source/img/pwa/` 等）。

注意事项：
- 本会话的 AI 模型**无法直接查看图片内容**（无视觉能力）。拿到图后应向用户确认图片内容/主体位置，再决定裁切。
- 定位照片主体可用 sharp 边缘方差启发式（下采样 → 分块方差 → 加权质心），或直接问用户主体在画面哪个区域。
- 竖版照片做方形头像默认居中裁，主体偏离中心时按主体位置重裁。
- 头像容器是 110px 圆形 + `object-fit: cover`，最终产物生成 400×400 即可，避免把原图大文件塞进站点。

## 账号与凭据

- 站点作者：**小七** `2556997014@qq.com`，GitHub 用户名 `xiaoqimi1`
- 本机 git 全局身份是寒枫（`HanphoneJan` / `1195560097@qq.com`），**不要改动全局配置**
- 推送到小七仓库时用小七的凭据：
  - 凭据文件：`.git-xiaoqi-credentials`（含 token，`chmod 600`，已 gitignore，勿提交、勿外泄）
  - git 配置：`.gitconfig-xiaoqi`（user=小七 + 指向上面的凭据文件，已 gitignore）
  - `pnpm run publish` 脚本会通过 `GIT_CONFIG_GLOBAL=$PWD/.gitconfig-xiaoqi` 自动用小七身份推送
- 本项目仓库本地 git 身份也设成了小七（`git config --local`）

## 已知坑（务必注意）

1. **YAML 注释陷阱**：`_config.butterfly.yml` 里 `inject.head` 的每行 CSS 若以 `#` 开头会被 YAML 当成注释吞掉，必须用单引号包裹，例如 `- '  #footer { ... }'`。
2. **背景统一方案**：全站背景由 `#web_bg` 一个固定图层显示，`inject` 里把 `#page-header` 背景设为透明，避免首页（100vh+fixed）与内页（短横幅）对同一张壁纸产生不同裁剪，导致切换页面时背景"缩放"。**不要**把 `background-attachment: fixed` 加回 header。
   - 移动端背景"缩放"（下滑时背景突然变大）：是 `#web_bg { height: 100% }` 跟随视口高度变化，URL 栏收起时视口变高、`cover` 重算导致。已在 inject 里改为 `height: 100lvh !important`（大视口恒定高度）修复，勿改回 `100%` 或 `100vh`。
3. `source/CNAME` 会进入 `public/` 根目录，是自定义域名生效的关键，勿删。
4. 修改主题时优先用 `inject.head` 注入 CSS，尽量不改 `themes/butterfly/` 源码，便于升级。
5. 本机 `hexo server` 会常驻后台，重建前先停掉（用端口 PID 精确 kill，别用 `pkill -f 'hexo server'`，会误杀执行命令的 shell）。
6. token 轮换：更新 `.git-xiaoqi-credentials`（格式 `https://xiaoqimi1:<token>@github.com`）。

## 2026-09-28 会话 · 经验沉淀

本节记录本会话新增的定制与经验，便于后续维护/接手。

### 外观与布局
- **首页卡片图**：`#recent-posts .post_cover` 里 `.post-bg` 用 `object-fit: contain`（图片保持比例、高度=卡片同高），两侧留白由 JS 注入的同图模糊层 `.cover-blur-bg` 铺底（`blur(16px)+brightness(0.68)`），见 `inject.head` CSS 与 `inject.bottom` JS。仅作用于 `#recent-posts`，不影响文章页。
- **主题色**：`theme_color.enable: true`，主色 `#64997b`（绿松石，与头像/背景一致），配套 `paginator/button_hover/link/scrollbar/blockquote` 等全部绿色系。改完主色后必须 `pnpm run clean && pnpm run build`，否则 stylus 缓存会残留旧色。
- **背景加速**：`source/img/background.webp`（75KB，主）+ `background.jpg`（153KB，回退）。`inject` 里对 `#web_bg` 用 `image-set(url webp, url jpg)`，现代浏览器自动用 WebP，旧浏览器回退 JPEG。
- **头像**：`avatar.img` 直接指向 QQ 开放头像 URL `https://q1.qlogo.cn/g?b=qq&nk=2556997014&s=640`（QQ 头像更新即同步）。PWA 图标仍由本地 `source/img/avatar.jpg` 生成，未动。
- **PWA 图标**：重新生成时避免白边——`maskable` 图标应让内容铺满画布，勿用白底缩小居中；本项目头像背景色是 `(100,153,123)`，四角用此色。
- **暗色模式**：`darkmode.enable: true` + `button: true` 本就开启，切换按钮在右侧栏 `#darkmode`（fa-adjust 图标）。注意右侧栏默认 `opacity:0` 需悬停页面右边缘才滑出（原生行为，勿强行改成常驻）。

### 链接结构
- **短链接**：`permalink: posts/:title/`，文章文件名用 7 位短 id（24 位 hex id 前 7 位，唯一）。旧长链接按用户要求不保留。
- **友链**：`source/_data/link.yml` + `source/link/index.md`（`type: link`），菜单加 `/link/`。友链含小七自己 + 云林有风。
- **RSS**：`hexo-generator-feed` 生成 `/atom.xml`（含最新 20 篇），页脚 `custom_text` 里加了 RSS 链接（fa-rss 图标），侧边栏 social 也有。

### 功能开启（可选类，已收敛）
- 开启：PJAX（局部刷新）、Series（文章系列，按主题给 41 篇打了系列）、canvas_nest 粒子背景、fireworks 点击烟花、translate 简繁切换、preloader 加载动画、structured_data（SEO）。
- **收敛（调试中发现叠加会乱/卡，故关闭）**：canvas_ribbon/fluttering（背景彩带）、click_heart/clickShowText/activate_power_mode（点击增强，与烟花叠加过载）。教训：**多个全屏 canvas 特效勿同时开**，背景留一个粒子、点击留一个烟花最清爽。
- **PJAX 兼容**：`inject.bottom` 的 blur/lazy JS 要监听 `pjax:complete` 事件重跑，否则页面切换后封面模糊层/懒加载失效。
- **Giscus 评论**：需先在 `giscus.app` 手动授权安装到仓库（无法用 token 自动化）。配置在 `comments.use: Giscus` + `giscus` 节，`option` 里加 `data-lang: zh-CN` 使界面中文。

### 其他经验
- **功能全开前先评估叠加效果**：同一类功能（多个背景动画、多个点击特效）全开会互相干扰并拖慢性能，逐项开启并本地截图验证再发布。
- **`public/` 旧目录残留**：改 permalink 后本地 `public/` 可能残留旧结构目录（已空），不影响线上；线上旧链接经实测已 404，用户若仍能打开是浏览器/PWA 缓存，硬刷新或清站点数据即可。
- **Playwright 验证注意**：本地 `hexo server` 会缓存旧渲染，build 后需重启 server 再验证；`__INITIAL_STATE__` 解析、gallery JS 渲染等已在 XHS-SYNC.md 记录。

## 隐私 / 公开性

- 仓库当前是**公开**的（GitHub Pages 用户站点免费版要求公开，设为私有会下线站点）。若后续要私有化，需要 GitHub Pro 套餐，且自定义域名配置不变。
- 站点源码里不含任何密钥；token 只在 gitignored 的本地文件里。