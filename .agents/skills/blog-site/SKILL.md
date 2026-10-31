---
name: 小七博客维护
description: 维护小七的 Hexo 博客（777.hanphone.cn）：写/改文章、调主题外观（背景、头像、PWA 图标、导航、主题色）、本地构建预览与发布部署，以及踩坑排查。涉及本仓库文章、_config*.yml、public/、GitHub Actions 部署时使用。
---

# 小七博客（xiaoqi-blog）维护

Hexo 8 + Butterfly 5.7，部署在 GitHub Pages（`gh-pages` 分支，域名 `https://777.hanphone.cn`）。
脚本：`pnpm new/build/clean/server/publish`；包管理 pnpm。

## 写文章

- 新建：`pnpm new "标题"`，文件落在 `source/_posts/`。
- front-matter：`title` / `date` / `tags`(数组) / `categories`(数组) / `description`（首页摘要）
  可选 `cover` + `cover_type: img`、`series`（连载系列）。
- 文件名约定：**手写文章用可读 slug 或日期；从小红书同步的文章用笔记 id 前 7 位**
  （详见 `xhs-sync` 技能）。
- 正文支持一般 Markdown；Butterfly 扩展：
  - 提示框：`{% note success %}…{% endnote %}`（primary/success/warning/danger）
  - 图片墙：`{% gallery %}…{% endgallery %}`
  - `<!-- more -->` 之后的正文不进首页摘要
- 图片放 `source/img/`，正文写 `/img/xxx.jpg`。

## 发布

```bash
pnpm run clean && pnpm run build      # 本地验证，必须无 ERROR
pnpm run publish                      # = git add -A + commit + GIT_CONFIG_GLOBAL=.gitconfig-xiaoqi git push
```

- main = 源码；gh-pages = 构建产物（Actions 生成）。
- 推送后约 1–2 分钟上线；`curl -o /dev/null -w '%{http_code}' https://777.hanphone.cn/posts/<slug>/` 返回 200 即部署成功。
- 推送必须用小七身份：`GIT_CONFIG_GLOBAL=$PWD/.gitconfig-xiaoqi`（`pnpm run publish` 已内置）。
  本机全局 git 身份是寒枫，**不要改全局配置**；凭据在 `.git-xiaoqi-credentials`（chmod 600，勿提交）。

## 外观定制

优先用 `_config.butterfly.yml` 的 `inject.head`（CSS）/ `inject.bottom`（JS）注入，
尽量不改 `themes/butterfly/` 源码，便于升级主题。

| 想改的 | 改哪里 |
| --- | --- |
| 站点标题/副标题/作者/url | `_config.yml` |
| 主题色 | `theme_color`（主色 `#64997b`；改完必须 `pnpm run clean` 再 build，否则 stylus 缓存留旧色） |
| 全站背景 | `source/img/background.webp`（主）+ `background.jpg`（回退），`inject` 里给 `#web_bg` 用 `image-set()` |
| 遮罩深浅 | `inject.head` 的 `#web_bg::after`（当前 `rgba(0,0,0,.35)`） |
| 头像 | `avatar.img`（当前直接指向 QQ 头像 URL，换 QQ 头像即同步） |
| favicon / PWA 图标 | `source/img/pwa/*` + `source/manifest.json`，由 `source/img/avatar.jpg` 导出 |
| 导航菜单 | `_config.butterfly.yml` 的 `menu`（含 `/link/` 友链） |
| 评论 | Giscus（`comments.use: Giscus`，需先在 giscus.app 对仓库授权安装，token 自动化不了） |
| 文章短链接 | `_config.yml` 的 `permalink: posts/:title/`，配合 7 位 id 文件名 |

## 已知坑（务必注意）

1. **YAML 注释陷阱**：`inject.head` 里以 `#` 开头的 CSS 行会被 YAML 当注释吞掉，
   必须用单引号包裹：`- '  #footer { ... }'`。
2. **背景统一方案**：全站背景只由 `#web_bg` 一个固定图层显示，`#page-header` 背景必须透明
   （否则首页 100vh 与内页短横幅对同一张壁纸裁剪不同，切页会「缩放」）。
   **不要**给 header 加回 `background-attachment: fixed`。
3. **移动端背景突变**：`#web_bg { height: 100lvh !important }`（大视口恒定高度）用来修复
   URL 栏收起导致视口变高、`cover` 重算的问题，勿改回 `100%` / `100vh`。
4. **public/ 缓存**：改配置后本地 `hexo server` 会用旧渲染；改主题色/样式先 `clean` 再 `build`，
   需要预览就重启 server。停 server 用端口 PID 精确 kill，别 `pkill -f 'hexo server'`（会误杀命令自身 shell）。
5. **PWA/Service Worker**：`hexo-offline` 只在 `hexo generate` 时写 `public/service-worker.js` 并注入注册脚本
   （本地 `hexo server` 看不到属正常）。改完内容后旧页面可能仍显示缓存，硬刷新或清站点数据即可。
6. **PWA 图标别留白边**：maskable 图标要让内容铺满画布，头像背景色 `rgb(100,153,123)` 铺四角；
   512/192 用 `png({palette:true, colours:255})` 压缩，否则照片 PNG 会到 450KB。
7. **CNAME 不能删**：`source/CNAME` 会进 `public/` 根目录，是自定义域名生效的关键。
8. **功能叠加**：全屏 canvas 类特效（背景粒子/彩带、点击烟花/爱心）不要同时开多个，
   会互相干扰并卡顿；已收敛为「背景一个粒子 + 点击一个烟花」。PJAX 生效时，
   `inject.bottom` 的 JS 要监听 `pjax:complete` 重跑（封面模糊层、懒加载）。
9. **仓库是公开的**：GitHub Pages 免费版要求公开；源码里不能出现密钥，token 只在 gitignored 的本地文件里。

## 已做过的外观/功能定制（别重复试）

- **首页卡片图**：`#recent-posts .post_cover` 的 `.post-bg` 用 `object-fit: contain`（图片保比例），
  两侧留白由 JS（`inject.bottom`）注入同图模糊层 `.cover-blur-bg`（`blur(16px) + brightness(0.68)`）铺底；
  仅作用于 `#recent-posts`，不影响文章页。
- **暗色模式**：`darkmode.enable: true` + `button: true`，切换按钮在右侧栏 `#darkmode`（fa-adjust）。
  右侧栏默认 `opacity: 0`，需鼠标悬停页面右边缘才滑出——这是原生行为，别改成常驻。
- **链接结构**：`permalink: posts/:title/` + 7 位短 id 文件名（旧长链接已废弃，不保留）。
  友链 = `source/_data/link.yml` + `source/link/index.md`（`type: link`）+ 菜单 `/link/`。
  RSS = `hexo-generator-feed` 生成 `/atom.xml`（最新 20 篇），页脚 `custom_text` 与侧栏 social 都有入口。
- **已开启**：PJAX、Series（文章系列）、canvas_nest 背景粒子、fireworks 点击烟花、简繁切换、
  preloader、structured_data(SEO)、wordcount、lazyload(native)、Giscus 评论（`data-lang: zh-CN`）。
- **已试过并关掉**（叠加会乱/卡）：canvas_ribbon / fluttering（背景彩带）、
  click_heart / clickShowText / activate_power_mode（点击增强）。结论：全屏 canvas 特效同类只留一个。
- **PJAX 兼容**：`inject.bottom` 里给封面模糊层/懒加载写的 JS 必须监听 `pjax:complete` 重跑。
- **public/ 残留**：改 permalink 后本地 `public/` 可能有空目录残留，不影响线上；线上旧链接是 404，
  用户还能打开基本是浏览器/PWA 缓存，硬刷新即可。

## 本机环境

- Node 24（`.nvm`），pnpm。`pnpm-workspace.yaml` 里的 `allowBuilds: hexo-util: true` 必须保留，
  否则 pnpm10+ 拦依赖构建、hexo-util 编不出来。
- 本机 `hexo server` 常驻时，重建前先停掉（见坑 4）。
