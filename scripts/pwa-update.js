/* 把 hexo-offline 注入的内联 SW 注册脚本换成 /js/sw-register.js
 *
 * hexo-offline 在 before_exit（默认优先级 10）里往 index.html 末尾塞一段内联脚本，
 * 它只在 console 打印日志、不会主动检查更新、接管后也不刷新页面。
 * 这里用优先级 99 在同一阶段之后运行，替换掉那段脚本，并补到所有 HTML 页面，
 * 让从任意页面（深链 / 分享链接）进入的访问也能触发更新检查。
 *
 * 注意：hexo-offline 没有关闭注入的开关，所以只能构建后处理。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const REG_TAG = '<script src="/js/sw-register.js" defer></script>';

// hexo-offline 注入的那段：<script>"use strict";if("serviceWorker"in navigator){navigator.serviceWorker.register("service-worker.js")...
const INJECTED_RE =
  /<script>(?:(?!<\/script>)[\s\S])*?navigator\.serviceWorker\.register\("service-worker\.js"\)(?:(?!<\/script>)[\s\S])*?<\/script>/;

function walkHtml(dir, out) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkHtml(full, out);
    } else if (entry.name.endsWith('.html')) {
      out.push(full);
    }
  }
  return out;
}

hexo.extend.filter.register(
  'before_exit',
  function () {
    const publicDir = hexo.public_dir;
    if (!fs.existsSync(publicDir)) return;

    const files = walkHtml(publicDir, []);
    let touched = 0;

    for (const file of files) {
      const html = fs.readFileSync(file, 'utf8');
      let next = html;

      if (INJECTED_RE.test(next)) {
        next = next.replace(INJECTED_RE, REG_TAG);
      }
      if (!next.includes('/js/sw-register.js')) {
        next = next.replace(/<\/body>\s*<\/html>\s*$/, `${REG_TAG}</body></html>`);
      }
      if (next !== html) {
        fs.writeFileSync(file, next);
        touched += 1;
      }
    }

    if (touched) {
      hexo.log.info(`PWA：已把 sw-register.js 接入 ${touched} 个页面`);
    }
  },
  99
);
