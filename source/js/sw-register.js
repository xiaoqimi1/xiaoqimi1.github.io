/* PWA Service Worker 注册与更新
 *
 * 为什么不用 hexo-offline 自带的注入脚本：
 *   它只在 console 里打一行日志，既不主动查新版本，也不在接管后刷新页面，
 *   配合「HTML 全量预缓存」就会一直看到旧内容（2026-11-15 修）。
 *
 * 这里的策略：
 *   1. updateViaCache: 'none' —— sw.js 不走 HTTP 缓存（GitHub Pages 给 max-age=600）
 *   2. load / 可见 / 联网 / focus 时主动 reg.update()，突破 Chrome 24h 检查节流
 *   3. 新 SW 接管（controllerchange）后自动刷新一次，带三重保护：
 *      防循环（15s）、防打断输入（等 blur）、离线不刷
 */
(function () {
  if (!('serviceWorker' in navigator)) return;

  var RELOAD_FLAG = 'sw-reloaded-at';
  var UPDATE_THROTTLE = 60 * 1000; // 主动 update 的本地节流
  var lastUpdate = 0;
  var hadController = !!navigator.serviceWorker.controller;
  var reloadPending = false;

  function reloadOnce() {
    if (reloadPending) return;
    reloadPending = true;
    try {
      var last = Number(sessionStorage.getItem(RELOAD_FLAG) || 0);
      if (Date.now() - last < 15000) return; // 15 秒内只自动刷一次，防循环
      sessionStorage.setItem(RELOAD_FLAG, String(Date.now()));
    } catch (e) {
      /* 隐私模式拿不到 sessionStorage：照刷，靠 reloadPending 防重入 */
    }
    location.reload();
  }

  function maybeReload() {
    if (!navigator.onLine) return; // 离线不刷，等下次联网启动

    var ae = document.activeElement;
    if (ae && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)) {
      ae.addEventListener('blur', function () { maybeReload(); }, { once: true });
      return; // 别打断正在输入的内容
    }

    if (document.visibilityState === 'hidden') {
      reloadOnce(); // 用户看不到时立刻刷
      return;
    }
    reloadOnce();
  }

  navigator.serviceWorker
    .register('/service-worker.js', { scope: '/', updateViaCache: 'none' })
    .then(function (reg) {
      function check(force) {
        var now = Date.now();
        if (!force && now - lastUpdate < UPDATE_THROTTLE) return;
        lastUpdate = now;
        var p = reg.update();
        if (p && p.catch) p.catch(function () {});
      }

      if (hadController) check(true); // 已有旧版本 → 立刻查一次

      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible') check(false);
      });
      window.addEventListener('focus', function () { check(false); });
      window.addEventListener('online', function () { check(true); });
    })
    .catch(function (e) {
      console.warn('[pwa] Service Worker 注册失败：', e);
    });

  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (!hadController) return; // 首次安装不算「更新」，不刷新
    maybeReload();
  });
})();
