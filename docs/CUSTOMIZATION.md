# 主题定制说明

定制优先通过 `_config.butterfly.yml` 的 `inject.head` 注入 CSS，尽量不改 `themes/butterfly/` 源码，便于升级主题。

## 站点基础信息

改 `_config.yml`：

```yaml
title: 小七的博客        # 站点标题
subtitle: 记录生活里的小确幸  # 副标题
author: 小七             # 作者
url: https://xiaoqimi1.github.io  # 站点地址（勿改成 localhost）
```

## 网站背景 / 遮罩

- 背景图：`source/img/background.jpg`（本机壁纸压缩版，2560×1440）
- 背景配置：`_config.butterfly.yml` 的 `background`
- 半透明遮罩：`inject.head` 里的 `#web_bg::after`（当前 `rgba(0,0,0,.35)`，改数值可调深浅）
- 全站背景统一由 `#web_bg` 显示，`#page-header` 背景必须保持透明（见 AGENTS.md「已知坑 2」）

## 顶部横幅

- 首页横幅：`index_img`
- 其他页面横幅：`default_top_img`
- 当前都指向 `/img/background.jpg`，所以所有页面横幅背景一致

## footer

- `footer.owner.since`：起始年份（当前 2026）
- `footer.custom_text`：自定义文字
- footer 背景和尺寸由 `inject.head` 的 `#footer` 规则控制

## 头像

- 文件：`source/img/avatar.svg`（占位头像，粉色圆 + "七"字）
- 配置：`_config.butterfly.yml` 的 `avatar.img`
- 换成真实头像：把图片放进 `source/img/`，改 `avatar.img` 路径

## 导航菜单

`_config.butterfly.yml` 的 `menu`：

```yaml
menu:
  首页: / || fas fa-home
  归档: /archives/ || fas fa-archive
  标签: /tags/ || fas fa-tags
  分类: /categories/ || fas fa-folder-open
  关于: /about/ || fas fa-heart
```

## 提醒

1. `inject.head` 里以 `#` 开头的 CSS 行必须用单引号包裹（YAML 注释陷阱）
2. 修改后 `pnpm run build` 本地验证，再 `git push` 部署