// hexo-offline / workbox-build 配置
// 详见 https://github.com/JLHwung/hexo-offline
module.exports = {
  globPatterns: ['**/*.{js,mjs,html,css,png,jpg,jpeg,gif,webp,svg,eot,ttf,woff,woff2,xml,json}'],
  maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
  skipWaiting: true,
  clientsClaim: true,
  runtimeCaching: [
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