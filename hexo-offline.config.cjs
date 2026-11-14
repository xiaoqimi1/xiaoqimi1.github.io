// hexo-offline / workbox-build 配置
// 详见 https://github.com/JLHwung/hexo-offline
//
// 缓存策略（2026-11-15 重构）：
//   - 预缓存只放「壳」：CSS / JS / 字体 / SVG。HTML 和图片一律不进预缓存，
//     否则导航永远命中 Cache Storage，发新文章后下拉刷新也看不到（旧方案 346 个文件 34MB）。
//   - 导航走 NetworkFirst：在线先取网络（3s 超时再回缓存），离线仍能打开看过的页面。
//   - 图片走 CacheFirst：发版不需要整体重下，按需缓存 300 张 / 30 天。
//   - mp4 不缓存（一条视频可能 95MB，不能占离线空间，也不该进 git 之外的缓存）。
//   - cleanupOutdatedCaches：新版本激活时清掉旧版本遗留的缓存。
module.exports = {
  globPatterns: ['**/*.{js,mjs,css,woff2,woff,ttf,eot,svg}'],
  maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
  skipWaiting: true,
  clientsClaim: true,
  cleanupOutdatedCaches: true,
  runtimeCaching: [
    {
      // 页面导航（HTML）：先网络后缓存
      urlPattern: ({ request }) => request.mode === 'navigate',
      handler: 'NetworkFirst',
      options: {
        cacheName: 'pages',
        networkTimeoutSeconds: 3,
        expiration: { maxEntries: 40, maxAgeSeconds: 7 * 24 * 60 * 60 }
      }
    },
    {
      // 站内图片（不含视频）：命中即用，30 天过期
      urlPattern: ({ url }) =>
        url.origin === self.location.origin &&
        url.pathname.startsWith('/img/') &&
        !url.pathname.endsWith('.mp4'),
      handler: 'CacheFirst',
      options: {
        cacheName: 'images',
        cacheableResponse: { statuses: [0, 200] },
        expiration: { maxEntries: 300, maxAgeSeconds: 30 * 24 * 60 * 60 }
      }
    },
    {
      urlPattern: /^https:\/\/cdn\.jsdelivr\.net\/.*/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'jsdelivr-cdn',
        expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }
      }
    },
    {
      urlPattern: /^https:\/\/unpkg\.com\/.*/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'unpkg-cdn',
        expiration: { maxEntries: 30, maxAgeSeconds: 30 * 24 * 60 * 60 }
      }
    },
    {
      urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/,
      handler: 'StaleWhileRevalidate',
      options: { cacheName: 'google-fonts-css' }
    },
    {
      urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'google-fonts',
        expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }
      }
    }
  ]
};
