---
title: 博客写作功能演示
date: 2026-09-20 15:30:00
tags: [教程, 博客]
categories: [教程]
description: 演示 Markdown 与 Butterfly 主题常用语法，方便以后写文章时参考。
---

这是一篇功能演示文章，把写博客常用的语法都展示一遍，以后写文章照着用就行～

## 标题与文字

一级到六级标题直接用 `#` 到 `######`。

**加粗**、*斜体*、~~删除线~~、`行内代码`，都是 Markdown 的标准语法。

## 引用

> 生活明朗，万物可爱。
> 人间值得，未来可期。

## 列表

无序列表：

- 苹果
- 香蕉
- 橘子

有序列表：

1. 起床
2. 吃早餐
3. 开始美好的一天

## 代码块

```javascript
const hello = () => {
  console.log("Hello, World!");
};
```

## 提示框（Butterfly note 插件）

{% note primary %}
主要提示信息
{% endnote %}

{% note success %}
成功提示信息
{% endnote %}

{% note warning %}
警告提示信息
{% endnote %}

{% note danger %}
危险提示信息
{% endnote %}

## 图片

![示例图片](/img/gallery/sunset.svg)

## 图册（Butterfly gallery 插件）

{% gallery %}
![落日](/img/gallery/sunset.svg)
![月亮](/img/gallery/moon.svg)
![幸运草](/img/gallery/clover.svg)
![小花](/img/gallery/flower.svg)
{% endgallery %}

点击图片可以放大预览哦（已开启 lightbox）。