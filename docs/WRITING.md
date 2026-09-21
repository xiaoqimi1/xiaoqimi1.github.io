# 如何写博客文章

面向小七的使用指南。所有文章都是 Markdown 文件，放在 `source/_posts/` 目录。

## 新建文章

```bash
pnpm new "文章标题"
```

会在 `source/_posts/` 生成一个 `.md` 文件，打开编辑即可。

## 文章格式

每篇文章开头有一段 `front-matter`（`---` 之间的内容），说明这篇文章的标题、日期、标签、分类：

```markdown
---
title: 我的第一篇文章
date: 2026-09-22 10:00:00
tags: [生活]
categories: [日记]
description: 一段简短描述（首页列表会显示）
---

正文内容写在这里…
```

- `title`：标题（必填）
- `date`：日期（不填默认当前时间）
- `tags`：标签，可多个
- `categories`：分类，可多个
- `description`：可选，首页列表摘要

## 常用 Markdown 语法

```markdown
## 二级标题
### 三级标题

**加粗**  *斜体*  `行内代码`

> 引用

![图片说明](/img/图片文件名.png)

- 列表项
1. 有序列表

```js
// 代码块
console.log('hello')
```
```

## Butterfly 特有功能

```markdown
{% note success %}
提示框（primary/success/warning/danger 四种颜色）
{% endnote %}

{% gallery %}
![图1](/img/gallery/a.png)
![图2](/img/gallery/b.png)
{% endgallery %}
```

图片请放到 `source/img/` 下，正文用 `/img/文件名` 引用。

## 发布

```bash
pnpm run publish
```

自动提交并推送到 GitHub，约 1 分钟后线上更新（`https://777.hanphone.cn`）。