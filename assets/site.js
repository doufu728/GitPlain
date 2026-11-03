/* GitPlain · 全站交互
   页面角色由 body[data-page] 决定：
     home    首页（对照交互 + 标签）
     browse  全部项目（搜索 / 分类 / 收藏 / 分页）
     weekly  周榜（本周 / 上周 / 分类 / 分页）
     detail  项目详情（仅收藏）
   数据契约与 build.py 保持一致：
     data/page-{n}.json     全量，每页 10 条，按总星数降序
     data/f/{id}-{n}.json   分类分片
     data/s/{char}.json     搜索索引（行数组）
     data/weekly.json       周榜前 100
     data/weekly-last.json  上周快照（可选，没有就隐藏「上周」）
*/
(function () {
  "use strict";

  var PAGE_SIZE = 10;
  var GT_STARS = 10000;      // 星数超过这个值才有独立详情页
  var FAV_KEY = "gitplain:favs:v1";
  var STALE_DAYS = 8;

  /* ================= 工具 ================= */
  var ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return ESC_MAP[c]; });
  }
  function fmt(n) {
    var v = Number(n);
    if (!isFinite(v)) return "0";
    return Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }
  function fetchJSON(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function safeUrl(raw) {
    try {
      var u = new URL(String(raw), window.location.href);
      if (u.protocol === "http:" || u.protocol === "https:") return u.href;
    } catch (e) {}
    return "";
  }
  function repoHref(repo, stars) {
    if (!repo || !(stars > GT_STARS)) return "";
    var parts = String(repo).split("/").filter(Boolean).map(encodeURIComponent);
    return "repo/" + parts.join("/") + "/";
  }

  /* ================= 收藏（localStorage，只在本机） ================= */
  function readFavs() {
    try {
      var arr = JSON.parse(window.localStorage.getItem(FAV_KEY) || "[]");
      return Object.prototype.toString.call(arr) === "[object Array]" ? arr : [];
    } catch (e) { return []; }
  }
  function writeFavs(arr) {
    try { window.localStorage.setItem(FAV_KEY, JSON.stringify(arr)); } catch (e) {}
  }
  function favIndex(repo) {
    var favs = readFavs();
    for (var i = 0; i < favs.length; i++) if (favs[i] && favs[i].repo === repo) return i;
    return -1;
  }
  var favCache = readFavs();

  function paintFavBtns(root) {
    var btns = (root || document).querySelectorAll("[data-fav]");
    for (var i = 0; i < btns.length; i++) {
      var on = favIndex(btns[i].getAttribute("data-fav")) !== -1;
      btns[i].setAttribute("aria-pressed", on ? "true" : "false");
      btns[i].setAttribute("aria-label", on ? "取消收藏" : "收藏");
      var label = btns[i].querySelector(".fav-label");
      if (label) label.textContent = on ? "已收藏" : "收藏";
    }
  }

  /* 收藏时给星标加一次闪烁动画 */
  function popFav(btn) {
    if (!btn || !btn.classList) return;
    btn.classList.remove("is-pop");
    void btn.offsetWidth;   /* 强制重排，保证连续点击能重播 */
    btn.classList.add("is-pop");
    btn.addEventListener("animationend", function h() {
      btn.classList.remove("is-pop");
      btn.removeEventListener("animationend", h);
    });
  }

  /* ================= 详情内容（弹层与详情页共用） ================= */
  function detailHTML(it) {
    var name = (it.repo || "").split("/").slice(1).join("/") || it.repo || "";
    var steps = (it.steps || []).map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("");
    var upd = String(it.pushed_at || it.updated_at || "").slice(0, 10) || "—";
    var week = it.stars_week || 0;
    return "" +
      '<div class="detail-head">' +
        (it.owner_avatar
          ? '<img class="detail-avatar" src="' + esc(safeUrl(it.owner_avatar)) + '" alt="" loading="lazy">'
          : '<span class="detail-avatar" aria-hidden="true"></span>') +
        '<div class="detail-titles">' +
          '<h2 class="detail-repo">' + esc(name) + "</h2>" +
          '<div class="detail-sub-line">' +
            '<span class="detail-tag">' + esc(it.category) + "</span>" +
            "<span>开发者：" + esc(it.owner) + "</span>" +
            "<span>★ " + fmt(it.stars) + "</span>" +
          "</div>" +
        "</div>" +
      "</div>" +
      '<div class="detail-summary">' +
        '<p class="detail-summary-label">GITPLAIN 说人话</p>' +
        '<p class="detail-summary-text">' + esc(it.desc_cn) + "</p>" +
        '<p class="detail-who"><b>适合谁：</b>' + esc(it.who) + "</p>" +
      "</div>" +
      '<section class="detail-section">' +
        '<h3 class="detail-sub">怎么用（3 步以内）</h3>' +
        '<ol class="detail-steps">' + steps + "</ol>" +
      "</section>" +
      '<section class="detail-section">' +
        '<div class="stat-grid">' +
          '<div class="stat"><span class="stat-num is-blue">' + (week ? "+" + fmt(week) : "—") + '</span><span class="stat-lab">本周涨星</span></div>' +
          '<div class="stat"><span class="stat-num">' + fmt(it.stars) + '</span><span class="stat-lab">总星数</span></div>' +
          '<div class="stat"><span class="stat-num">' + esc(it.lang || "—") + '</span><span class="stat-lab">主要语言</span></div>' +
          '<div class="stat"><span class="stat-num is-date">' + esc(upd) + '</span><span class="stat-lab">最近更新</span></div>' +
        "</div>" +
      "</section>" +
      '<div class="detail-actions">' +
        '<button class="btn-secondary" type="button" data-fav="' + esc(it.repo) + '" aria-pressed="false">' +
          '<span class="fav-label">收藏</span>' +
        "</button>" +
        '<a class="btn-primary" href="' + esc(safeUrl(it.url) || "#") + '" target="_blank" rel="noopener">在 GitHub 打开 ↗</a>' +
      "</div>" +
      '<p class="detail-note">中文说明由仓库简介和 README 生成，偶尔会有偏差，一切以原仓库为准。</p>';
  }

  /* ================= 弹层 ================= */
  var modalEl = null;
  var lastFocus = null;

  function ensureModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement("div");
    modalEl.className = "modal";
    modalEl.setAttribute("role", "dialog");
    modalEl.setAttribute("aria-modal", "true");
    modalEl.setAttribute("aria-label", "项目详情");
    modalEl.innerHTML = '<div class="modal-panel"><button class="modal-close" type="button" aria-label="关闭">' +
      '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">' +
      '<path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>' +
      '</button><div class="modal-body"></div></div>';
    document.body.appendChild(modalEl);
    modalEl.addEventListener("click", function (e) {
      if (e.target === modalEl || e.target.closest(".modal-close")) closeModal();
    });
    return modalEl;
  }
  function openModal(it) {
    var m = ensureModal();
    m.querySelector(".modal-body").innerHTML = detailHTML(it);
    document.body.appendChild(m);          /* 保证在最上层 */
    document.body.classList.add("is-locked");
    lastFocus = document.activeElement;
    paintFavBtns(m);
    var panel = m.querySelector(".modal-panel");
    if (panel) {
      panel.setAttribute("tabindex", "-1");
      panel.focus();
    }
  }
  function closeModal() {
    if (!modalEl || !modalEl.parentNode) return;
    modalEl.parentNode.removeChild(modalEl);
    document.body.classList.remove("is-locked");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });
  window.GP_OPEN = openModal;   /* 供调试与外部调用 */

  /* 任意地方点收藏按钮 */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest("[data-fav]") : null;
    if (!btn) return;
    e.preventDefault();
    var repo = btn.getAttribute("data-fav");
    if (!repo) return;
    var favs = readFavs();
    var i = favIndex(repo);
    if (i !== -1) {
      favs.splice(i, 1);
      writeFavs(favs);
      favCache = favs;
      paintFavBtns(document);
      if (window.GP_ON_FAV) window.GP_ON_FAV(repo, false);
    } else {
      var it = (window.GP_ITEMS && window.GP_ITEMS[repo]) || null;
      if (!it) return;
      favs.unshift(it);
      writeFavs(favs);
      favCache = favs;
      paintFavBtns(document);
      popFav(btn);   /* 只有「收藏成功」才闪烁，取消收藏不闪 */
      if (window.GP_ON_FAV) window.GP_ON_FAV(repo, true);
    }
  });

  /* ================= 行渲染（列表页） ================= */
  function rowHTML(it, rank, mode) {
    var href = repoHref(it.repo, it.stars);
    var avatar = safeUrl(it.owner_avatar);
    var name = (it.repo || "").split("/").slice(1).join("/") || it.repo || "";
    var gainColClass = mode === "week" ? "gain-col" : "gain-col gain-col--stars";
    var main, sub;
    if (mode === "week") {
      main = '<span class="gain">+' + fmt(it.stars_week || 0) + '<span class="gain-unit">/周</span></span>';
      sub = '<span class="stars">★ ' + fmt(it.stars) + "</span>";
    } else {
      main = '<span class="gain">' + fmt(it.stars) + "</span>";
      sub = '<span class="stars">' + (it.stars_week ? "+" + fmt(it.stars_week) + "/周" : "本周无涨星") + "</span>";
    }
    var rankStr = (rank < 10 ? "0" : "") + rank;
    return "" +
      '<li class="board-row' + (rank === 1 ? " board-row--top1" : "") + '"' +
        ' data-repo="' + esc(it.repo) + '" data-href="' + esc(href) + '">' +
        '<span class="bar' + (rank === 1 ? " bar--1" : rank <= 3 ? " bar--23" : "") + '" aria-hidden="true"></span>' +
        '<span class="rank ' + (rank <= 3 ? "rank--top" : "rank--rest") + '" aria-hidden="true">' + rankStr + "</span>" +
        '<span class="sr-only">第 ' + rank + " 名</span>" +
        '<div class="body">' +
          '<div class="body-head">' +
            (avatar
              ? '<img class="avatar" src="' + esc(avatar) + '" alt="" loading="lazy" decoding="async" onerror="this.style.visibility=\'hidden\'">'
              : '<span class="avatar avatar--blank" aria-hidden="true"></span>') +
            '<a class="repo-name" href="' + esc(href || it.url) + '"' + (href ? "" : ' target="_blank" rel="noopener"') + ' title="' + esc(it.repo) + '">' + esc(name) + "</a>" +
            '<span class="cat">' + esc(it.category) + "</span>" +
            '<span class="owner">开发者：' + esc(it.owner) + "</span>" +
          "</div>" +
          '<p class="desc">' + esc(it.desc_cn) + "</p>" +
          '<p class="who">' +
            '<span class="who-owner">开发者：' + esc(it.owner) + "</span>" +
            '<span class="who-dot" aria-hidden="true"></span>' +
            '<span class="who-fit">适合：' + esc(it.who) + "</span>" +
            '<span class="who-dot" aria-hidden="true"></span>' +
            '<span class="who-stars">★ ' + fmt(it.stars) + "</span>" +
          "</p>" +
        "</div>" +
        '<div class="' + gainColClass + '">' + main + sub + "</div>" +
        '<button class="fav-toggle" type="button" data-fav="' + esc(it.repo) + '" aria-pressed="false" aria-label="收藏">' +
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">' +
          '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9-4.3-4.1 5.9-.9z"/></svg>' +
        "</button>" +
        '<a class="visit" href="' + esc(safeUrl(it.url) || "#") + '" target="_blank" rel="noopener">打开' +
          '<svg class="ext" width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">' +
          '<path d="M5 3h6v6M11 3 4 10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        "</a>" +
      "</li>";
  }

  /* 行点击：有详情页就跳，没有就弹层 */
  document.addEventListener("click", function (e) {
    if (e.target.closest(".visit") || e.target.closest("[data-fav]") || e.target.closest(".repo-name")) return;
    var row = e.target.closest ? e.target.closest(".board-row") : null;
    if (!row) return;
    var href = row.getAttribute("data-href");
    if (href) { window.location.href = href; return; }
    var repo = row.getAttribute("data-repo");
    var it = window.GP_ITEMS && window.GP_ITEMS[repo];
    if (it) openModal(it);
  });

  /* ================= 分页器 ================= */
  function pagerNums(cur, tp) {
    var set;
    if (tp <= 9) {
      set = [];
      for (var i = 1; i <= tp; i++) set.push(i);
    } else {
      set = [1, tp];
      var start = Math.max(2, cur - 3), end = Math.min(tp - 1, cur + 3);
      while (end - start + 1 < 8) {
        if (start > 2) start--;
        else if (end < tp - 1) end++;
        else break;
      }
      for (var p = start; p <= end; p++) set.push(p);
    }
    set.sort(function (a, b) { return a - b; });
    var uniq = [], out = [], prev = 0;
    set.forEach(function (n) { if (uniq.indexOf(n) === -1) uniq.push(n); });
    uniq.forEach(function (n) {
      if (prev && n - prev > 1) out.push('<span class="pg-gap">…</span>');
      out.push('<button class="pg-num' + (n === cur ? " is-active" : "") + '" type="button" data-go="' + n + '"' +
        (n === cur ? ' aria-current="page"' : "") + ">" + n + "</button>");
      prev = n;
    });
    return out.join("");
  }

  function renderPager(el, cur, tp, totalItems) {
    if (!el) return;
    if (tp <= 1) { el.hidden = true; el.innerHTML = ""; return; }
    el.hidden = false;
    el.innerHTML =
      '<p class="pager-count">共 ' + fmt(totalItems) + " 个项目 · 第 " + fmt(cur) + " / " + fmt(tp) + " 页</p>" +
      '<div class="pager-ctrl">' +
        '<button class="pg-btn" type="button" data-go="' + Math.max(1, cur - 1) + '"' + (cur <= 1 ? " disabled" : "") + ">上一页</button>" +
        '<span class="pg-pages">' + pagerNums(cur, tp) + "</span>" +
        '<button class="pg-btn" type="button" data-go="' + Math.min(tp, cur + 1) + '"' + (cur >= tp ? " disabled" : "") + ">下一页</button>" +
        '<span class="pg-jump">跳到 <input class="pg-input" type="number" min="1" max="' + tp + '" inputmode="numeric" aria-label="页码"> 页</span>' +
        '<span class="pg-total">/ ' + fmt(tp) + " 页</span>" +
      "</div>";
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".pg-num, .pg-btn") : null;
    if (!btn || btn.disabled) return;
    if (window.GP_GO) window.GP_GO(parseInt(btn.getAttribute("data-go"), 10), true);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    if (!e.target.classList || !e.target.classList.contains("pg-input")) return;
    e.preventDefault();
    var n = parseInt(e.target.value, 10);
    if (n && window.GP_GO) window.GP_GO(n, true);
  });

  /* ================= 首页 ================= */
  function initHome() {
    var stage = document.getElementById("cmpStage");
    var toggle = document.getElementById("cmpToggle");
    var label = document.getElementById("cmpLabel");
    if (stage && toggle) {
      toggle.addEventListener("click", function () {
        var collapsed = stage.classList.toggle("is-collapsed");
        toggle.setAttribute("aria-expanded", String(!collapsed));
        if (label) label.textContent = collapsed ? "展开原文" : "悬停 / 点击";
      });
    }
    var input = document.getElementById("heroInput");
    var tags = document.querySelectorAll(".tag[data-q]");
    for (var i = 0; i < tags.length; i++) {
      tags[i].addEventListener("click", function () {
        if (!input) return;
        input.value = this.getAttribute("data-q") || this.textContent.trim();
        input.focus();
      });
    }
    var form = document.getElementById("heroSearch");
    if (form) {
      form.addEventListener("submit", function (e) {
        if (!input || !input.value.trim()) {
          e.preventDefault();
          if (input) input.focus();
        }
      });
    }
    /* 旧链接兼容：index.html?cat=/q=/page=/fav=1 → 转到 browse.html */
    var qs = window.location.search.replace(/^\?/, "");
    if (qs) {
      var sp = new URLSearchParams(qs);
      if (sp.get("q") || sp.get("cat") || sp.get("page") || sp.get("fav") === "1") {
        window.location.replace("browse.html?" + qs);
      }
    }
  }

  /* ================= 列表页（browse） ================= */
  function initBrowse() {
    var el = {
      list: document.getElementById("list"),
      pager: document.getElementById("pager"),
      state: document.getElementById("emptyState"),
      catSelect: document.getElementById("catSelect"),
      search: document.getElementById("q"),
      seg: document.querySelector(".ctl--mode")
    };
    if (!el.list) return;
    if (el.catSelect) initCatMenu(el.catSelect);
    var CATS = window.GP_CATS || { total: 0, updated: "", cats: [] };
    var allPages = Math.ceil(CATS.total / PAGE_SIZE) || 0;
    var catById = {}, catByName = {};
    CATS.cats.forEach(function (c) {
      catById[c.id] = c;
      catByName[c.name] = c;
    });

    var st = { mode: "all", cat: "", q: "", page: 1, tp: allPages, total: CATS.total };
    var cache = {};
    var searchRows = null;      /* 懒加载的搜索索引 */
    var searchMatches = [];
    var seq = 0;                /* 请求序号：只认最后一次，避免翻页竞态 */
    var searching = false;

    function setEmpty(title, sub, actions) {
      el.state.innerHTML =
        '<p class="state-title">' + esc(title) + "</p>" +
        (sub ? '<p class="state-sub">' + esc(sub) + "</p>" : "") +
        (actions ? '<div class="state-actions">' + actions + "</div>" : "");
      el.state.hidden = false;
      el.list.hidden = true;
    }
    function clearEmpty() {
      el.state.hidden = true;
      el.state.innerHTML = "";
      el.list.hidden = false;
    }

    function syncURL() {
      try {
        var p = [];
        if (st.mode === "fav") p.push("fav=1");
        if (st.cat) p.push("cat=" + encodeURIComponent(st.cat));
        if (st.q) p.push("q=" + encodeURIComponent(st.q));
        if (st.page > 1) p.push("page=" + st.page);
        window.history.replaceState(null, "", "browse.html" + (p.length ? "?" + p.join("&") : ""));
      } catch (e) {}
    }

    function remember(items) {
      window.GP_ITEMS = window.GP_ITEMS || {};
      items.forEach(function (it) { window.GP_ITEMS[it.repo] = it; });
    }

    function fetchPage(n) {
      if (st.cat) {
        var c = catByName[st.cat];
        if (!c) return Promise.resolve([]);
        var url = "data/f/" + c.id + "-" + n + ".json";
        if (!cache[url]) cache[url] = fetchJSON(url);
        return cache[url];
      }
      var u = "data/page-" + n + ".json";
      if (!cache[u]) cache[u] = fetchJSON(u);
      return cache[u];
    }

    /* ---- 搜索索引：按首字符分片，中文查询回退全量 ---- */
    function loadShard(key) {
      if (!window.__shard) window.__shard = {};
      if (window.__shard[key]) return Promise.resolve(window.__shard[key]);
      return fetchJSON("data/s/" + key + ".json").then(function (rows) {
        window.__shard[key] = rows;
        return rows;
      });
    }
    /* 全量索引（缓存起来，避免每次搜索都重新拉取） */
    var _fullIndex = null;
    function loadFullIndex() {
      if (_fullIndex) return Promise.resolve(_fullIndex);
      if (window.__fullIndex) { _fullIndex = window.__fullIndex; return Promise.resolve(_fullIndex); }
      return fetchJSON("data/s/index.json").then(function (meta) {
        return Promise.all(Object.keys(meta).map(loadShard));
      }).then(function (groups) {
        var all = [];
        groups.forEach(function (g) { all = all.concat(g); });
        _fullIndex = all;
        window.__fullIndex = all;
        return all;
      });
    }
    function loadSearchIndex() {
      /* 搜索统一加载全量索引：分片键按 owner 首字符切分，但用户可能按 repo 名搜，
         只按查询首字符加载单分片会漏掉大量结果（如搜 rea 找不到 facebook/react） */
      return loadFullIndex();
    }
    function rowToItem(row) {
      var owner = row[6] || "";
      return {
        repo: row[0] || "", desc_cn: row[1] || "", stars: row[2] || 0,
        stars_week: row[3] || 0, category: row[4] || "", who: row[5] || "",
        owner: owner, lang: row[7] || "", url: row[8] || "",
        owner_avatar: owner ? "https://github.com/" + owner + ".png?size=60" : ""
      };
    }

    function totalFor() {
      if (st.q) return searchMatches.length;
      if (st.mode === "fav") return favCache.length;
      if (st.cat) return (catByName[st.cat] || {}).count || 0;
      return CATS.total;
    }

    function render(items, offset) {
      el.list.innerHTML = items.map(function (it, i) {
        return rowHTML(it, offset + i + 1, "stars");
      }).join("");
      remember(items);
      paintFavBtns(el.list);
      clearEmpty();
    }

    function updateHead() {
      var meta = document.getElementById("pageMeta");
      var hint = document.getElementById("sortHint");
      var h1 = document.getElementById("pageTitle");
      var eb = document.getElementById("pageEyebrow");
      var sn = document.getElementById("subnavTitle");
      var nt = document.getElementById("subnavNote");
      var cp = document.getElementById("subnavCaption");
      var lead = document.getElementById("pageLead");
      var fav = st.mode === "fav";
      if (h1) h1.textContent = fav ? "我的收藏" : "全部项目";
      if (eb) eb.textContent = fav ? "MY FAVORITES" : "ALL PROJECTS";
      if (sn) sn.textContent = fav ? "我的收藏" : "全部项目";
      /* 子导航里的「共 65,856 个」是站点总量，挂在收藏标题后面会被读成收藏数，这里换掉 */
      if (nt) {
        nt.textContent = fav
          ? "不联网 · 不上传"
          : "共 " + fmt(CATS.total) + " 个 · 数据更新于 " + (CATS.updated || "—");
      }
      if (cp) {
        cp.textContent = fav
          ? "点星标即可收藏 · 不需要登录"
          : "1,000 星以上 · 按总星数排 · 每周更新";
      }
      if (lead) {
        lead.textContent = fav
          ? "你点过星标的项目都在这里。收藏只存在你自己的浏览器里，换设备、清缓存都会丢，不需要登录。"
          : "GitHub 上 1,000 星以上的项目都在这里，按总星数从高到低排。每个都配一句大白话，看完就知道它是不是你要的。";
      }
      if (meta) {
        if (st.q) {
          meta.textContent = "搜索「" + st.q + "」· 找到 " + fmt(st.total) + " 个相关项目";
        } else if (fav) {
          meta.textContent = "我的收藏 · " + fmt(st.total) + " 个项目（只存在本机浏览器）";
        } else if (st.cat) {
          meta.textContent = st.cat + " · " + fmt(st.total) + " 个项目 · 每页 10 个";
        } else {
          meta.textContent = "共 " + fmt(st.total) + " 个项目 · 每页 10 个";
        }
      }
      if (hint) {
        hint.textContent = st.q ? "按总星数排序 · 只搜名称与中文说明"
          : (fav ? "收藏只存在这台设备的浏览器里" : "按总星数排序");
      }
    }

    function go(n, scroll) {
      n = Math.max(1, Math.min(n || 1, st.tp || 1));
      updateHead();
      if (!st.tp) {
        if (st.mode === "fav") {
          setEmpty("还没有收藏任何项目", "看到感兴趣的项目，点右侧的星标收藏。收藏只存在你自己的浏览器里，不上传、不需要登录。",
            '<button class="btn-primary" type="button" data-act="all">去看看全部项目</button>');
        } else {
          setEmpty("这个分类还没有项目", "换个分类看看，或者直接搜你想做的事。");
        }
        renderPager(el.pager, 0, 0, 0);
        return;
      }
      var offset = (n - 1) * PAGE_SIZE;

      if (st.q) {
        var slice = searchMatches.slice(offset, offset + PAGE_SIZE);
        st.page = n;
        render(slice, offset);
        renderPager(el.pager, n, st.tp, st.total);
        syncURL();
        if (scroll) scrollTop();
        return;
      }
      if (st.mode === "fav") {
        var favs = favCache.slice(offset, offset + PAGE_SIZE);
        st.page = n;
        render(favs, offset);
        renderPager(el.pager, n, st.tp, st.total);
        syncURL();
        if (scroll) scrollTop();
        return;
      }
      var mine = ++seq;
      fetchPage(n).then(function (items) {
        if (mine !== seq) return;
        st.page = n;
        render(items, offset);
        renderPager(el.pager, n, st.tp, st.total);
        syncURL();
        if (scroll) scrollTop();
      }).catch(function () {
        if (mine !== seq) return;
        setEmpty("这一页没加载出来", "检查一下网络，或者刷新页面重试。");
      });
    }
    window.GP_GO = go;

    function scrollTop() {
      var top = document.querySelector(".pagehead");
      if (top) window.scrollTo({ top: top.offsetTop - 60, behavior: "auto" });
    }

    function applyMode(mode) {
      st.mode = mode;
      st.q = "";
      if (el.search) el.search.value = "";
      var btns = el.seg ? el.seg.querySelectorAll(".seg-btn") : [];
      for (var i = 0; i < btns.length; i++) {
        var on = btns[i].getAttribute("data-mode") === mode;
        btns[i].classList.toggle("is-active", on);
        btns[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
      if (el.catSelect) el.catSelect.disabled = mode === "fav";
      if (mode === "fav") {
        favCache = readFavs();
        st.cat = "";
        if (el.catSelect) el.catSelect.value = "";
      }
      refresh(true);
    }

    function refresh(scroll) {
      st.total = totalFor();
      st.tp = Math.ceil(st.total / PAGE_SIZE);
      go(1, scroll);
    }

    /* ---- 事件 ---- */
    if (el.catSelect) {
      el.catSelect.addEventListener("change", function () {
        st.cat = el.catSelect.value;
        st.mode = "all";
        st.q = "";
        if (el.search) el.search.value = "";
        var btns = el.seg ? el.seg.querySelectorAll(".seg-btn") : [];
        for (var i = 0; i < btns.length; i++) {
          var on = btns[i].getAttribute("data-mode") === "all";
          btns[i].classList.toggle("is-active", on);
          btns[i].setAttribute("aria-pressed", on ? "true" : "false");
        }
        refresh(true);
      });
    }
    if (el.seg) {
      el.seg.addEventListener("click", function (e) {
        var b = e.target.closest(".seg-btn");
        if (b) applyMode(b.getAttribute("data-mode"));
      });
    }
    if (el.search) {
      el.search.addEventListener("input", debounce(function () {
        var q = el.search.value.trim();
        if (!q) {
          st.q = "";
          searchMatches = [];
          refresh(false);
          return;
        }
        if (searching) return;
        searching = true;
        var token = (el.search.__t = (el.search.__t || 0) + 1);
        loadSearchIndex(q).then(function (rows) {
          searching = false;
          if (token !== el.search.__t) return;
          searchRows = rows;
          var ql = q.toLowerCase();
          searchMatches = [];
          for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            if ((r[0] || "").toLowerCase().indexOf(ql) !== -1 ||
                (r[1] || "").toLowerCase().indexOf(ql) !== -1) {
              searchMatches.push(rowToItem(r));
            }
          }
          st.q = q;
          st.mode = "all";
          st.cat = "";
          if (el.catSelect) el.catSelect.value = "";
          /* 分片是拼接来的，顺序不等于星数顺序，这里统一按总星数重排 */
          searchMatches.sort(function (a, b) { return (b.stars || 0) - (a.stars || 0); });
          st.total = searchMatches.length;
          st.tp = Math.ceil(st.total / PAGE_SIZE);
          if (!st.total) {
            setEmpty("没有找到「" + q + "」相关的项目", "换个说法试试，比如「剪视频」「表格」「语音转文字」。",
              '<button class="btn-primary" type="button" data-act="all">看看全部项目</button>');
            renderPager(el.pager, 0, 0, 0);
            updateHead();
            syncURL();
            return;
          }
          go(1, false);
        }).catch(function () {
          searching = false;
          setEmpty("搜索数据加载失败", "检查一下网络，或者刷新页面重试。");
        });
      }, 280));
    }
    document.addEventListener("click", function (e) {
      var act = e.target.closest ? e.target.closest("[data-act]") : null;
      if (!act) return;
      if (act.getAttribute("data-act") === "all") {
        if (el.search) el.search.value = "";
        if (el.catSelect) el.catSelect.value = "";
        applyMode("all");
      }
    });
    window.GP_ON_FAV = function (repo, on) {
      favCache = readFavs();
      if (st.mode !== "fav") return;
      st.total = favCache.length;
      st.tp = Math.ceil(st.total / PAGE_SIZE);
      go(Math.min(st.page || 1, st.tp || 1), false);
    };

    /* ---- 初始化：地址栏 → 状态 ---- */
    var sp = new URLSearchParams(window.location.search);
    var q0 = sp.get("q") || "";
    var cat0 = sp.get("cat") || "";
    var page0 = parseInt(sp.get("page"), 10) || 1;
    var favMode = sp.get("fav") === "1";

    window.GP_ITEMS = window.GP_ITEMS || {};
    (window.GP_FIRST || []).forEach(function (it) { window.GP_ITEMS[it.repo] = it; });
    paintFavBtns(document);

    /* 从发现页带 q/cat 跳转过来时，显示「返回发现页」 */
    if (q0 || cat0) {
      var bd = document.getElementById("backDiscover");
      if (bd) bd.hidden = false;
    }

    if (favMode) {
      applyMode("fav");
    } else if (q0) {
      if (el.search) {
        el.search.value = q0;
        el.search.dispatchEvent(new Event("input"));
      }
    } else if (cat0) {
      st.cat = cat0;
      if (el.catSelect) el.catSelect.value = cat0;
      st.total = totalFor();
      st.tp = Math.ceil(st.total / PAGE_SIZE);
      go(page0, false);
    } else {
      st.total = CATS.total;
      st.tp = allPages;
      renderPager(el.pager, 1, allPages, CATS.total);
      if (page0 > 1) go(page0, false);
    }
  }

  /* ================= 周榜 ================= */
  function initWeekly() {
    var el = {
      list: document.getElementById("list"),
      pager: document.getElementById("pager"),
      state: document.getElementById("emptyState"),
      catSelect: document.getElementById("catSelect"),
      seg: document.querySelector(".ctl--period"),
      label: document.getElementById("weekLabel"),
      meta: document.getElementById("pageMeta"),
      notice: document.getElementById("staleNotice"),
      noticeText: document.getElementById("staleText")
    };
    if (!el.list) return;

    var st = { period: "this", cat: "", page: 1, data: {}, tp: 0, total: 0 };
    var CATS = window.GP_CATS || { updated: "" };

    function setEmpty(title, sub) {
      el.state.innerHTML = '<p class="state-title">' + esc(title) + "</p>" +
        (sub ? '<p class="state-sub">' + esc(sub) + "</p>" : "");
      el.state.hidden = false;
      el.list.hidden = true;
    }
    function clearEmpty() {
      el.state.hidden = true;
      el.state.innerHTML = "";
      el.list.hidden = false;
    }

    function weekMeta(dateStr) {
      var m = /(\d{4})-(\d{2})-(\d{2})/.exec(String(dateStr || ""));
      if (!m) return null;
      var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
      if (isNaN(d.getTime())) return null;
      var t = new Date(d.getTime());
      var dow = (t.getUTCDay() + 6) % 7;
      t.setUTCDate(t.getUTCDate() - dow + 3);
      var firstThu = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
      var fdow = (firstThu.getUTCDay() + 6) % 7;
      firstThu.setUTCDate(firstThu.getUTCDate() - fdow + 3);
      var week = 1 + Math.round((t - firstThu) / (7 * 86400000));
      var start = new Date(d.getTime() - 6 * 86400000);
      function mmdd(x) {
        var mm = x.getUTCMonth() + 1, dd = x.getUTCDate();
        return (mm < 10 ? "0" : "") + mm + "." + (dd < 10 ? "0" : "") + dd;
      }
      return { week: week, range: mmdd(start) + "-" + mmdd(d), iso: d.toISOString().slice(0, 10) };
    }

    function list() {
      var raw = st.data[st.period] || [];
      if (!st.cat) return raw;
      return raw.filter(function (it) { return String(it.category || "").trim() === st.cat; });
    }

    function go(n, scroll) {
      var rows = list();
      st.total = rows.length;
      st.tp = Math.ceil(rows.length / PAGE_SIZE);
      n = Math.max(1, Math.min(n || 1, st.tp || 1));
      if (!st.tp) {
        setEmpty("这一周没有符合条件的项目", "换个分类看看。");
        renderPager(el.pager, 0, 0, 0);
        return;
      }
      var offset = (n - 1) * PAGE_SIZE;
      var slice = rows.slice(offset, offset + PAGE_SIZE);
      st.page = n;
      el.list.innerHTML = slice.map(function (it, i) { return rowHTML(it, offset + i + 1, "week"); }).join("");
      window.GP_ITEMS = window.GP_ITEMS || {};
      slice.forEach(function (it) { window.GP_ITEMS[it.repo] = it; });
      paintFavBtns(el.list);
      clearEmpty();
      renderPager(el.pager, n, st.tp, st.total);
      if (el.meta) el.meta.textContent = "共 " + fmt(st.total) + " 个项目 · 每页 10 个";
      if (scroll) {
        var top = document.querySelector(".pagehead");
        if (top) window.scrollTo({ top: top.offsetTop - 60, behavior: "auto" });
      }
    }
    window.GP_GO = go;

    function paintSeg() {
      var btns = el.seg ? el.seg.querySelectorAll(".seg-btn") : [];
      for (var i = 0; i < btns.length; i++) {
        var on = btns[i].getAttribute("data-period") === st.period;
        btns[i].classList.toggle("is-active", on);
        btns[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
    }

    if (el.seg) {
      el.seg.addEventListener("click", function (e) {
        var b = e.target.closest(".seg-btn");
        if (!b) return;
        var p = b.getAttribute("data-period");
        if (p === st.period) return;
        st.period = p;
        paintSeg();
        if (!st.data[p]) {
          setEmpty("正在加载上周数据…", "");
          fetchJSON("data/weekly-last.json").then(function (rows) {
            st.data[p] = rows;
            go(1, false);
          }).catch(function () {
            setEmpty("上周榜单暂未归档", "从下一次更新起，系统会自动保存每周快照。先看本周榜单吧。");
            renderPager(el.pager, 0, 0, 0);
          });
          return;
        }
        go(1, false);
      });
    }
    if (el.catSelect) {
      el.catSelect.addEventListener("change", function () {
        st.cat = el.catSelect.value;
        go(1, false);
      });
    }

    Promise.all([
      fetchJSON("data/weekly.json").catch(function () { return null; }),
      fetchJSON("data/weekly-last.json").catch(function () { return null; }),
      fetchJSON("data/cats.json").catch(function () { return null; })
    ]).then(function (res) {
      var cur = res[0], prev = res[1], metaRes = res[2];
      if (metaRes && metaRes.updated) CATS = metaRes;
      st.data.this = Array.isArray(cur) ? cur : [];
      st.data.last = Array.isArray(prev) ? prev : [];
      if (!st.data.this.length) {
        setEmpty("周榜数据还没生成", "数据正在抓取，稍后再来。");
        renderPager(el.pager, 0, 0, 0);
        return;
      }
      /* 没有上周数据就藏起「上周」开关，不做一个点了会空的按钮 */
      if (!st.data.last.length && el.seg) el.seg.hidden = true;

      var meta = weekMeta(CATS.updated);
      if (meta) {
        if (el.label) el.label.textContent = "第 " + meta.week + " 周 · " + meta.range;
        var eb = document.getElementById("eyebrow");
        if (eb) eb.textContent = "WEEKLY RANKING · 第 " + meta.week + " 周";
        if (el.notice && el.noticeText) {
          var today = new Date();
          var days = Math.floor((Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) -
            Date.parse(meta.iso + "T00:00:00Z")) / 86400000);
          if (days > STALE_DAYS) {
            el.notice.hidden = false;
            el.noticeText.textContent = "这份榜单更新于 " + meta.iso + "，已经 " + days + " 天没更新了，数字可能不是你看到这篇文章时的最新值。";
          }
        }
      }
      /* 分类下拉：只保留本周里真实出现过的分类 */
      var seen = {}, order = [];
      st.data.this.forEach(function (it) {
        var c = String(it.category || "").trim();
        if (c && !seen[c]) { seen[c] = 1; order.push(c); }
      });
      if (el.catSelect) {
        order.sort(function (a, b) { return a.localeCompare(b, "zh"); });
        order.forEach(function (c) {
          var o = document.createElement("option");
          o.value = c;
          o.textContent = c;
          el.catSelect.appendChild(o);
        });
        initCatMenu(el.catSelect);
      }
      paintSeg();
      go(1, false);
    }).catch(function () {
      setEmpty("周榜加载失败", "检查一下网络，或者刷新页面重试。");
    });
  }

  /* ================= 详情页 ================= */
  function initDetail() {
    if (window.GP_ITEM) {
      window.GP_ITEMS = window.GP_ITEMS || {};
      window.GP_ITEMS[window.GP_ITEM.repo] = window.GP_ITEM;
    }
    paintFavBtns(document);
  }

  /* ================= 分类下拉（自绘外观，数据仍走原生 select） ================= */
  function initCatMenu(select) {
    if (!select) return;
    var wrap = select.parentNode;
    var btn = wrap.querySelector(".catmenu-btn");
    var list = wrap.querySelector(".catmenu-list");
    if (!btn || !list) return;

    function open() {
      btn.setAttribute("aria-expanded", "true");
      list.hidden = false;
    }
    function close() {
      btn.setAttribute("aria-expanded", "false");
      list.hidden = true;
    }
    function syncBtn() {
      var cur = select.options[select.selectedIndex];
      var label = btn.querySelector(".catmenu-label");
      if (label) label.textContent = cur ? cur.textContent : "全部分类";
    }
    function renderList() {
      var cur = select.value;
      var html = "";
      for (var i = 0; i < select.options.length; i++) {
        var o = select.options[i];
        var sel = o.value === cur;
        var isAll = o.value === "";
        html += '<li role="option" aria-selected="' + (sel ? "true" : "false") + '" data-val="' + esc(o.value) + '">' +
          '<button type="button" class="catmenu-opt' + (isAll ? " catmenu-opt--all" : "") + '" tabindex="-1">' +
            '<span class="catmenu-check" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 7.5 5.5 10.5 11.5 3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' +
            '<span class="catmenu-txt">' + esc(o.textContent) + "</span>" +
            (o.dataset && o.dataset.count ? '<span class="catmenu-n">' + esc(o.dataset.count) + "</span>" : "") +
          "</button></li>";
      }
      list.innerHTML = html;
      syncBtn();
    }
    function pick(val) {
      select.value = val;
      /* 触发原 change 逻辑（initBrowse / initWeekly 里各自监听） */
      var ev;
      try { ev = new Event("change", { bubbles: true }); }
      catch (e) { ev = document.createEvent("Event"); ev.initEvent("change", true, false); }
      select.dispatchEvent(ev);
      close();
      syncBtn();
    }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (btn.getAttribute("aria-expanded") === "true") { close(); return; }
      renderList();
      open();
    });
    list.addEventListener("click", function (e) {
      var li = e.target.closest("[data-val]");
      if (!li) return;
      pick(li.getAttribute("data-val"));
    });
    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) close();
    });
    document.addEventListener("keydown", function (e) {
      if (btn.getAttribute("aria-expanded") !== "true") return;
      var items = list.querySelectorAll("[data-val]");
      if (!items.length) return;
      var cur = -1;
      for (var i = 0; i < items.length; i++) {
        if (items[i].getAttribute("aria-selected") === "true") { cur = i; break; }
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        var next = e.key === "ArrowDown" ? (cur + 1) % items.length : (cur - 1 + items.length) % items.length;
        items[next].querySelector(".catmenu-opt").focus();
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (cur >= 0) pick(items[cur].getAttribute("data-val"));
      } else if (e.key === "Escape") {
        close();
        btn.focus();
      }
    });

    /* 原生 select 值被程序改（applyMode / 搜索清空 / 周榜异步补选项）时，同步按钮文字 */
    select.addEventListener("change", syncBtn);
    var origAdd = select.appendChild.bind(select);
    select.appendChild = function (node) {
      var r = origAdd(node);
      syncBtn();
      return r;
    };
    /* 拦截 value 赋值：程序化 set 也同步按钮文字 */
    var proto = Object.getPrototypeOf(select);
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) {
      var origSet = desc.set;
      Object.defineProperty(select, "value", {
        get: function () { return desc.get.call(this); },
        set: function (v) { origSet.call(this, v); syncBtn(); },
        configurable: true
      });
    }
    syncBtn();
    return { refresh: renderList, sync: syncBtn };
  }

  /* ================= 启动 ================= */
  function boot() {
    var page = document.body.getAttribute("data-page");
    if (page === "home") initHome();
    else if (page === "browse") initBrowse();
    else if (page === "weekly") initWeekly();
    else if (page === "detail") initDetail();
    else paintFavBtns(document);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
