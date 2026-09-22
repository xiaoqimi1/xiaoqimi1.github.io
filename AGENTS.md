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
├── .github/workflows/deploy.yml  # 构建并部署到 gh-pages 分支
├── source/
│   ├── _posts/*.md          # 文章（Markdown，front-matter 含 title/date/tags/categories）
│   ├── img/                 # 图片资源（background.jpg 是壁纸背景）
│   ├── img/pwa/             # PWA 图标（由 app-icon.svg 生成，见下文）
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
  - `source/img/pwa/`：图标由 `app-icon.svg`（全铺满渐变 + "七"字）生成，勿直接用 `avatar.svg`（圆形有透明角，不适合做应用图标）
- 换图标流程：改 `source/img/pwa/app-icon.svg`，用 sharp/ImageMagick 等重新导出各尺寸 PNG（icon-192/512、maskable-192/512、apple-touch-icon 180、favicon-16/32），保持 `manifest.json` 里路径不变。
- 已验证：`pnpm run build` 后 `public/` 含 `service-worker.js`（预缓存全部静态资源，约 1.5MB）、`manifest.json`、图标，`index.html` 末尾注入 SW 注册脚本。
- 注意：SW 注册脚本只在 `hexo generate` 阶段写入 `public/`，本地 `hexo server` 预览页不会显示（属正常，部署即生效）。PWA 需 HTTPS，线上已满足。

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

## 隐私 / 公开性

- 仓库当前是**公开**的（GitHub Pages 用户站点免费版要求公开，设为私有会下线站点）。若后续要私有化，需要 GitHub Pro 套餐，且自定义域名配置不变。
- 站点源码里不含任何密钥；token 只在 gitignored 的本地文件里。