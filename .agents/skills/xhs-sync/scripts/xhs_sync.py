#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书 → Hexo 博客同步工具（纯 HTTP，绝不开浏览器）。

子命令：
  cookies   从本机已登录的 Chrome cookie 库解出登录态 → .xhs-cookies.json
  list      抓主页 SSR 第一页，和 source/_posts 比对，列出「新增 / 已有」
  fetch     抓新增笔记的详情 SSR（自动跳过交易/出物类）
  images    下载详情里的图片到 source/img/xhs/<note_id>/，WebP 转 JPEG
  markdown  生成 Hexo 文章（文件名取 id 前 7 位）
  all       cookies → list → fetch → images → markdown

依赖（一次性）：
  python3 -m venv .venv-xhs --system-site-packages
  .venv-xhs/bin/pip install requests pillow cryptography

用法示例：
  .venv-xhs/bin/python .agents/skills/xhs-sync/scripts/xhs_sync.py all
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# --- 路径 -------------------------------------------------------------------
HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]                      # <repo>/  （scripts/xhs-sync/skills/.agents）
POSTS = ROOT / "source" / "_posts"
IMG_XHS = ROOT / "source" / "img" / "xhs"
WORK = Path("/tmp/opencode/xhs")            # 抓取中间产物
COOKIE_JSON = ROOT / ".xhs-cookies.json"
COOKIE_RAW = ROOT / ".xhs-cookies-raw.txt"
CHROME_COOKIES = Path.home() / ".config/google-chrome/Default/Cookies"

USER_ID = "649d592e0000000011000515"        # 柒柒
SITE = "https://www.xiaohongshu.com"
KEYRING_LABEL = "Chrome Safe Storage"
DEFAULT_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

# 交易 / 出物类关键词：命中即不同步（内容取舍规则，见 SKILL.md）
TRADE_WORDS = ("出物", "出闲置", "可刀", "包非偏", "走平台", "提确", "平换",
               "寄给你", "出娃", "出谷", "出卡", "换物", "拼团", "自抱盒",
               "成团", "出掉", "垃圾包", "收出", "出bjd", "出个", "收主页")

# 主题关键词 → 标签
TOPIC_TAGS = {
    "洛克王国": "洛克王国", "bjd": "BJD", "乌萨奇": "chiikawa",
    "chiikawa": "chiikawa", "邦倪兔": "邦倪兔", "喵喵喵次方": "喵喵喵次方",
    "王者荣耀": "王者荣耀", "崩铁": "崩坏星穹铁道", "崩坏星穹铁道": "崩坏星穹铁道",
    "娃衣": "棉花娃娃", "月光童话": "BJD", "mjd": "BJD", "悸动瞬息": "BJD",
}

# 主题关键词 → 系列（Butterfly series）
SERIES_MAP = {
    "洛克王国": "洛克王国", "乌萨奇": "chiikawa 收藏", "chiikawa": "chiikawa 收藏",
    "邦倪兔": "邦倪兔", "喵喵喵次方": "喵喵喵次方", "王者荣耀": "王者荣耀",
    "崩铁": "崩坏星穹铁道", "国崩": "崩坏星穹铁道", "棉花娃娃": "棉花娃娃",
    "娃衣": "棉花娃娃",
}

NEW_MAP_RE = re.compile(r"new (Map|Set|Date|WeakMap|WeakSet|Uint8Array|Array)\([^()]*\)")


# --- 通用 -------------------------------------------------------------------
def log(*a):
    print(*a, flush=True)


def chrome_ua() -> str:
    try:
        out = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out or "")
        if m:
            return DEFAULT_UA.replace("154.0.0.0", m.group(1))
    except Exception:
        pass
    return DEFAULT_UA


def headers() -> dict:
    return {
        "User-Agent": chrome_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": SITE + "/",
        "Upgrade-Insecure-Requests": "1",
    }


def load_cookies() -> dict:
    if not COOKIE_JSON.exists():
        raise SystemExit("缺少 .xhs-cookies.json，先跑 `xhs_sync.py cookies`")
    return {c["name"]: c["value"] for c in json.load(open(COOKIE_JSON))}


def parse_state(html: str) -> dict | None:
    i = html.find("window.__INITIAL_STATE__=")
    if i < 0:
        return None
    s = html[i + len("window.__INITIAL_STATE__="):]
    s = s.replace(":undefined", ":null").replace(",undefined", ",null")
    s = NEW_MAP_RE.sub("null", s)
    try:
        st, _ = json.JSONDecoder().raw_decode(s)
        return st
    except Exception as e:
        log("  !! INITIAL_STATE 解析失败:", str(e)[:90])
        return None


def existing_ids() -> set[str]:
    return {p.stem for p in POSTS.glob("*.md")}


# --- 1. 登录态 ---------------------------------------------------------------
def keyring_password(label: str = KEYRING_LABEL) -> bytes:
    import gi
    gi.require_version("Secret", "1")
    from gi.repository import Secret

    service = Secret.Service.get_sync(Secret.ServiceFlags.LOAD_COLLECTIONS, None)
    for coll in service.get_collections():
        coll.load_items_sync(None)
        for it in coll.get_items():
            if it.get_label() != label:
                continue
            v = it.get_secret()
            if v is None:
                it.load_secret_sync(None)
                v = it.get_secret()
            if v is not None:
                return bytes(v.get())
    raise SystemExit(f"keyring 里没有 {label}（Chrome 可能没在用 gnome-keyring）")


def decrypt_cookie(value: bytes, key: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if not value:
        return ""
    if value[:3] not in (b"v10", b"v11"):
        return value.decode("utf-8", "replace")
    d = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    out = d.update(value[3:]) + d.finalize()
    pad = out[-1]
    if 0 < pad <= 16:
        out = out[:-pad]
    # 新版 Chrome 在明文前塞了 32 字节 host_key 哈希
    if len(out) > 32 and not out[:32].isascii():
        out = out[32:]
    return out.decode("utf-8", "replace")


def cmd_cookies(_args) -> None:
    if not CHROME_COOKIES.exists():
        raise SystemExit(f"找不到 {CHROME_COOKIES}")
    tmp = Path(tempfile.mkdtemp(prefix="xhs-cookies-")) / "Cookies"
    shutil.copy2(CHROME_COOKIES, tmp)
    con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    rows = con.execute(
        "select host_key, name, encrypted_value, value from cookies "
        "where host_key like '%xiaohongshu%' order by name").fetchall()
    con.close()
    tmp.unlink(missing_ok=True)

    key = hashlib.pbkdf2_hmac("sha1", keyring_password(), b"saltysalt", 1, 16)
    cookies, seen, pairs = [], set(), []
    for host, name, enc, plain in rows:
        if name in seen:
            continue
        val = plain or decrypt_cookie(enc, key)
        if not val:
            continue
        seen.add(name)
        pairs.append(f"{name}={val}")
        domain = host if host.startswith(".") else "." + host
        cookies.append({
            "name": name, "value": val, "domain": domain, "path": "/",
            "expires": -1,
            "httpOnly": name in ("web_session", "id_token", "last_web_session"),
            "secure": name in ("web_session", "id_token", "last_web_session"),
            "sameSite": "Lax",
        })
    if not cookies:
        raise SystemExit("Chrome cookie 库里没有小红书 cookie（浏览器里没登录？）")

    COOKIE_RAW.write_text("; ".join(pairs))
    os.chmod(COOKIE_RAW, 0o600)
    COOKIE_JSON.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    os.chmod(COOKIE_JSON, 0o600)
    log(f"从 Chrome 解出 {len(cookies)} 个 cookie -> {COOKIE_JSON.name}")
    log("  自检：.venv-xhs/bin/python ... list 能列出笔记即为有效")


# --- 2. 列出笔记 -------------------------------------------------------------
def fetch_profile() -> list[dict]:
    import requests

    r = requests.get(f"{SITE}/user/profile/{USER_ID}", headers=headers(),
                     cookies=load_cookies(), timeout=25, allow_redirects=False)
    log(f"主页 SSR: status={r.status_code} len={len(r.text)}")
    if r.status_code != 200:
        raise SystemExit("主页请求被判未登录（302 → /login）。请在 Chrome 里打开一次"
                         " https://www.xiaohongshu.com 再跑 cookies。")
    st = parse_state(r.text)
    if not st:
        raise SystemExit("解析不到 INITIAL_STATE")
    user = st.get("user") or {}
    items = [it for b in (user.get("notes") or []) if isinstance(b, list) for it in b]
    notes = []
    for it in items:
        nc = it.get("noteCard") or {}
        nid = it.get("id") or nc.get("noteId")
        if not nid:
            raise SystemExit(
                "SSR 里笔记 id 为空 = 登录态被降级（浏览器里重新访问一次小红书再读 cookie）。")
        notes.append({"id": nid, "xsecToken": it.get("xsecToken", ""),
                      "displayTitle": nc.get("displayTitle", ""),
                      "time": nc.get("time"), "type": nc.get("type")})
    return notes


def cmd_list(_args) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    notes = fetch_profile()
    (WORK / "notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2))
    have = existing_ids()
    new = [n for n in notes if n["id"][:7] not in have]
    log(f"SSR 第一页 {len(notes)} 篇；博客已有 {len(have)} 篇；新增 {len(new)} 篇：")
    for n in notes:
        d = datetime.fromtimestamp((n["time"] or 0) / 1000).strftime("%Y-%m-%d %H:%M")
        mark = "新增" if n["id"][:7] not in have else "已有"
        flag = "  [交易类]" if any(w in (n["displayTitle"] or "") for w in TRADE_WORDS) else ""
        log(f"  {mark} {n['id'][:7]} {d} {(n['displayTitle'] or '')[:28]}{flag}")
    if new:
        oldest = datetime.fromtimestamp(min(n["time"] or 0 for n in new) / 1000)
        log(f"\n最老新增笔记: {oldest:%Y-%m-%d}；若该日期之前还有没同步过的，说明超出第一页范围"
            "（无法翻页，需另想办法）。")


# --- 3. 抓详情 ---------------------------------------------------------------
def extract_note(st: dict) -> dict | None:
    acc: list = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                acc.append(v) if k == "noteDetailMap" else walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(st)
    if acc and isinstance(acc[0], dict):
        for detail in acc[0].values():
            if isinstance(detail, dict):
                note = detail.get("note") or detail
                if note.get("desc") or note.get("imageList"):
                    return note
    return None


def cmd_fetch(args) -> None:
    import requests

    WORK.mkdir(parents=True, exist_ok=True)
    notes = json.load(open(WORK / "notes.json")) if (WORK / "notes.json").exists() else fetch_profile()
    have = existing_ids()
    todo, skipped = [], []
    for n in notes:
        if n["id"][:7] in have:
            continue
        if not getattr(args, "include_trade", False) and any(
                w in (n["displayTitle"] or "") for w in TRADE_WORDS):
            skipped.append(n)
        else:
            todo.append(n)

    log(f"待抓 {len(todo)} 篇；按规则跳过 {len(skipped)} 篇交易类")
    for n in skipped:
        log("  SKIP", n["id"][:7], n["displayTitle"])
    cookies = load_cookies()
    ok = 0
    for n in todo:
        nid, tok = n["id"], n.get("xsecToken", "")
        url = f"{SITE}/explore/{nid}?xsec_token={tok}&xsec_source=pc_user"
        r = requests.get(url, headers=headers(), cookies=cookies, timeout=25, allow_redirects=False)
        log(f"  {nid[:7]} status={r.status_code} len={len(r.text)}")
        if r.status_code != 200 or "/login" in r.url:
            log("    !! 详情没拿到（登录态或 xsec_token 失效）")
            continue
        note = extract_note(parse_state(r.text) or {})
        if not note:
            log("    !! 解析不到 noteDetailMap")
            continue
        (WORK / f"detail_{nid}.json").write_text(json.dumps(
            {"id": nid, "xsecToken": tok, "raw": note}, ensure_ascii=False))
        log(f"    OK imgs={len(note.get('imageList') or [])} type={note.get('type')} "
            f"title={note.get('title')!r}")
        ok += 1
        time.sleep(2)
    log(f"详情抓取完成 {ok}/{len(todo)}")


# --- 4. 图片 -----------------------------------------------------------------
def pick_url(img: dict) -> str | None:
    for k in ("urlDefault", "url"):
        u = img.get(k)
        if u and "xhscdn" in u:
            return u
    for item in img.get("infoList") or []:
        u = item.get("url")
        if u and "xhscdn" in u and item.get("imageScene") in ("WB_PRV", "WB_DFT"):
            return u
    for item in img.get("infoList") or []:
        u = item.get("url")
        if u and "xhscdn" in u:
            return u
    return None


def cmd_images(args) -> None:
    import requests

    only = set(getattr(args, "ids", None) or [])
    files = sorted(glob.glob(str(WORK / "detail_*.json")))
    if only:
        files = [f for f in files if Path(f).stem[7:] in only]
    if not files:
        raise SystemExit("没有可处理的 detail_*.json（先跑 fetch）")
    ok = err = 0
    for f in files:
        nid = Path(f).stem[len("detail_"):]
        imgs = (json.load(open(f)).get("raw") or {}).get("imageList") or []
        if not imgs:
            continue
        n_dir = IMG_XHS / nid
        n_dir.mkdir(parents=True, exist_ok=True)
        for idx, img in enumerate(imgs, 1):
            url = pick_url(img)
            if not url:
                log(f"  {nid[:7]} img{idx}: 没有可用 URL")
                err += 1
                continue
            path = n_dir / f"{idx:02d}.jpg"
            try:
                resp = requests.get(url.replace("http://", "https://"),
                                    headers={**headers(), "Accept": "image/*,*/*;q=0.8"},
                                    timeout=30)
                if resp.status_code != 200:
                    log(f"  {nid[:7]} img{idx}: HTTP {resp.status_code}")
                    err += 1
                    continue
                path.write_bytes(resp.content)
                to_jpeg(path)
                ok += 1
            except Exception as e:
                log(f"  {nid[:7]} img{idx}: {e}")
                err += 1
            time.sleep(0.4)
        log(f"  {nid[:7]} imgs={len(imgs)} done")
    log(f"图片完成 ok={ok} err={err}")


def to_jpeg(path: Path) -> None:
    """xhscdn 现在默认回 WebP，统一转成真 JPEG，与仓库既有图片保持一致。"""
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(path) as im:
        if im.format != "WEBP":
            return
        im.convert("RGB").save(path, "JPEG", quality=88, optimize=True)


# --- 5. 生成文章 -------------------------------------------------------------
def clean_desc(desc: str) -> str:
    if not desc:
        return ""
    text = re.sub(r"#[^#\s]*(?:\[话题\])?#?", "", desc)
    text = re.sub(r"#[#\s]*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def pick_tags(desc: str, title: str) -> list[str]:
    line = f"{desc} {title}".lower()
    return sorted({tag for kw, tag in TOPIC_TAGS.items() if kw.lower() in line})


def pick_series(desc: str, title: str, tags: list[str]) -> str:
    line = f"{desc} {title} {' '.join(tags)}"
    for kw, series in SERIES_MAP.items():
        if kw in line:
            return series
    return ""


def yaml_safe(text: str) -> str:
    """front-matter 里的单行安全标量：清掉会让 Hexo/YAML 报错的符号。"""
    d = text.replace("'", "''").replace("\n", " ").strip()
    return re.sub(r"[@\[\]]", "", d)


def cmd_markdown(_args) -> None:
    files = sorted(glob.glob(str(WORK / "detail_*.json")))
    if not files:
        raise SystemExit("没有可处理的 detail_*.json（先跑 fetch）")
    written = []
    for f in files:
        nid = Path(f).stem[len("detail_"):]
        raw = json.load(open(f)).get("raw") or {}
        desc = raw.get("desc") or ""
        title = clean_desc(raw.get("title") or "")
        if not title:
            title = clean_desc((raw.get("noteCard") or {}).get("displayTitle") or "")
        if not title:
            title = clean_desc(desc)[:20] or f"小红书笔记 {nid[:8]}"
        title = re.sub(r"[：:]\s*$", "", title).strip()

        ts = raw.get("time") or 0
        date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else "2024-01-01 00:00:00"
        imgs = raw.get("imageList") or []
        tags = pick_tags(desc, title) or ["小红书"]
        series = pick_series(desc, title, tags)
        description = (clean_desc(desc)[:120] or title[:60]).replace("\n", " ").strip()

        fm = ["---", f"title: {title}", f"date: {date}"]
        if imgs:
            fm += [f"cover: /img/xhs/{nid}/01.jpg", "cover_type: img"]
        if series:
            fm.append(f"series: {json.dumps(series, ensure_ascii=False)}")
        fm.append("tags: " + json.dumps(tags, ensure_ascii=False))
        fm.append('categories: ["小红书"]')
        if description:
            fm.append(f"description: '{yaml_safe(description)}'")
        fm.append("---")

        body = []
        text = clean_desc(desc)
        if text:
            body += [text, "<!-- more -->"]
        if imgs:
            body.append("")
            body.append("{% gallery %}")
            body += [f"![]({ '/img/xhs/%s/%02d.jpg' % (nid, i) })" for i in range(1, len(imgs) + 1)]
            body.append("{% endgallery %}")
        body += ["", f"{{% note info %}}本文同步自[小红书]({SITE}/explore/{nid})（柒柒）{{% endnote %}}"]

        out = POSTS / f"{nid[:7]}.md"       # 仓库约定：文件名取 id 前 7 位
        out.write_text("\n".join(fm) + "\n\n" + "\n".join(body).strip() + "\n")
        written.append(out.name)
        log(f"  {out.name} <- {nid} | {title[:24]!r} | {date} | tags={tags}"
            + (f" | series={series}" if series else ""))
    log(f"生成 {len(written)} 篇文章")


# --- 编排 -------------------------------------------------------------------
def cmd_all(args) -> None:
    cmd_cookies(args)
    cmd_list(args)
    cmd_fetch(args)
    cmd_images(args)
    cmd_markdown(args)
    log("\n下一步：pnpm run clean && pnpm run build 确认无 ERROR，再 commit + push。")


def main() -> None:
    ap = argparse.ArgumentParser(description="小红书 → Hexo 博客同步（纯 HTTP）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cookies", help="从 Chrome cookie 库解出登录态")
    sub.add_parser("list", help="列出 SSR 第一页并与博客比对")
    p = sub.add_parser("fetch", help="抓新增笔记详情")
    p.add_argument("--include-trade", action="store_true", help="连交易/出物类也抓（默认跳过）")
    p = sub.add_parser("images", help="下载图片")
    p.add_argument("--ids", nargs="*", help="只处理这些完整 note_id")
    sub.add_parser("markdown", help="生成 Hexo 文章")
    sub.add_parser("all", help="cookies→list→fetch→images→markdown")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    {"cookies": cmd_cookies, "list": cmd_list, "fetch": cmd_fetch,
     "images": cmd_images, "markdown": cmd_markdown, "all": cmd_all}[args.cmd](args)


if __name__ == "__main__":
    main()
