/* SFX Studio — interactions. Plain JS + GSAP/ScrollTrigger (optional: the
   site works fully without them). Motion character: weighty, mechanical. */
(function () {
  'use strict';

  var doc = document.documentElement;
  var reduceMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  var desktopMQ = window.matchMedia('(min-width: 1000px)');
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function plural(n, one, few, many) {
    var a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b === 1) return one;
    if (b >= 2 && b <= 4) return few;
    return many;
  }

  function loadVideo(video) {
    if (!video || video.dataset.loaded) return;
    var src = video.querySelector('source[data-src]');
    if (src) { src.src = src.dataset.src; video.load(); }
    video.dataset.loaded = '1';
  }
  function safePlay(video) {
    if (!video) return;
    var p = video.play();
    if (p && p.catch) p.catch(function () { /* autoplay blocked: poster stays */ });
  }

  /* ---------- Header ---------- */
  var header = $('[data-header]');
  if (header && header.hasAttribute('data-transparent')) {
    var onScroll = function () { header.classList.toggle('is-solid', window.scrollY > 40); };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- Mobile menu ---------- */
  var menuBtn = $('[data-menu-btn]'), menu = $('[data-menu]');
  if (menuBtn && menu) {
    var setMenu = function (open) {
      menuBtn.setAttribute('aria-expanded', String(open));
      menu.classList.toggle('is-open', open);
      document.body.classList.toggle('menu-open', open);
      if (header) header.classList.toggle('is-solid', open || window.scrollY > 40 || !header.hasAttribute('data-transparent'));
      if (open) { var first = menu.querySelector('a'); if (first) first.focus(); }
    };
    menuBtn.addEventListener('click', function () { setMenu(menuBtn.getAttribute('aria-expanded') !== 'true'); });
    menu.addEventListener('click', function (e) { if (e.target.closest('a')) setMenu(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('is-open')) { setMenu(false); menuBtn.focus(); }
    });
    desktopMQ.addEventListener && desktopMQ.addEventListener('change', function (e) { if (e.matches) setMenu(false); });
  }

  /* ---------- Hero: montage synced with the element words ---------- */
  var hero = $('[data-hero]');
  if (hero) {
    var hv = $('[data-hero-video]', hero);
    var map = [];
    try { map = JSON.parse($('[data-hero-map]', hero).textContent) || []; } catch (e) { map = []; }
    var words = $$('[data-elements] li', hero);
    var ticks = $$('.reel-ticks i', hero);
    var credit = $('[data-hero-credit]', hero);
    var pauseBtn = $('[data-hero-pause]', hero);
    var userPaused = false, current = -1;
    var sources = hv ? $$('source', hv) : [];
    var source = sources[0];

    var setActive = function (i) {
      if (i === current || !map[i]) return;
      current = i;
      words.forEach(function (li) { li.classList.toggle('is-active', li.dataset.key === map[i].key); });
      if (credit) credit.textContent = 'В кадре: «' + map[i].credit + '»';
    };
    var segmentAt = function (t) {
      var idx = 0;
      for (var k = 0; k < map.length; k++) if (t >= map[k].start) idx = k;
      return idx;
    };
    var raf = null;
    var tick = function () {
      if (!hv || hv.paused) { raf = null; return; }
      var t = hv.currentTime, i = segmentAt(t);
      setActive(i);
      var dur = hv.duration || 0;
      ticks.forEach(function (el, k) {
        var s = map[k] ? map[k].start : 0;
        var e = map[k + 1] ? map[k + 1].start : dur;
        var p = k < i ? 1 : k > i ? 0 : Math.min(1, Math.max(0, (t - s) / Math.max(.01, e - s)));
        el.firstChild.style.transform = 'scaleX(' + p.toFixed(3) + ')';
      });
      raf = requestAnimationFrame(tick);
    };
    var setPaused = function (paused) {
      hero.classList.toggle('is-paused', paused);
      if (pauseBtn) {
        pauseBtn.setAttribute('aria-pressed', String(paused));
        pauseBtn.querySelector('span').textContent = paused ? 'Смотреть' : 'Пауза';
      }
    };

    if (hv && source) {
      var wantMotion = !reduceMQ.matches && !saveData;
      var wide = window.innerWidth >= 900;
      sources.forEach(function (sEl) { sEl.src = wide ? sEl.dataset.srcWide : sEl.dataset.srcNarrow; });
      if (wantMotion) {
        hv.load();
        hv.addEventListener('playing', function () { setPaused(false); if (!raf) raf = requestAnimationFrame(tick); });
        hv.addEventListener('pause', function () { setPaused(true); });
        safePlay(hv);
      } else {
        userPaused = true;
        setPaused(true);
      }
      if (pauseBtn) pauseBtn.addEventListener('click', function () {
        if (hv.paused) {
          userPaused = false;
          if (!hv.currentSrc) hv.load();
          safePlay(hv);
        } else { userPaused = true; hv.pause(); }
      });
      // Pause while off-screen (saves battery), resume if the user did not pause
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (!en.isIntersecting && !hv.paused) { hv.pause(); hero.dataset.autoPaused = '1'; }
            else if (en.isIntersecting && hero.dataset.autoPaused && !userPaused) { delete hero.dataset.autoPaused; safePlay(hv); }
          });
        }, { threshold: 0.05 }).observe(hero);
      }
    }
    // Hovering a word previews nothing (keeps one focus), but keyboard focus is visible via CSS.
  }

  /* ---------- Chapters: sticky stage on desktop, inline loops on mobile ---------- */
  var chapters = $$('[data-chapter]');
  var stage = $('[data-stage]');
  var stageItems = stage ? $$('[data-stage-item]', stage) : [];
  var stageNum = $('[data-stage-num]'), stageName = $('[data-stage-name]');
  var activeKey = null;
  function activateStage(key) {
    if (!stage || key === activeKey) return;
    var prev = activeKey;
    activeKey = key;
    stageItems.forEach(function (fig) {
      var on = fig.dataset.stageItem === key;
      var was = fig.dataset.stageItem === prev;
      fig.classList.toggle('is-active', on);
      fig.classList.toggle('was-active', was && !on);
      var v = fig.querySelector('video');
      if (on) {
        if (!reduceMQ.matches && !saveData) { loadVideo(v); safePlay(v); }
      } else if (v && !v.paused) {
        // keep the outgoing shot alive until the wipe completes
        setTimeout(function () { if (!fig.classList.contains('is-active')) v.pause(); }, 950);
      }
    });
    var ch = chapters.filter(function (c) { return c.dataset.chapter === key; })[0];
    if (ch && stageNum) {
      stageNum.textContent = ch.querySelector('.cue b').textContent;
      stageName.textContent = ch.querySelector('.chapter__name').textContent.trim();
    }
  }
  function inlineLoops() {
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var v = en.target;
        if (desktopMQ.matches) return;
        if (en.isIntersecting && !reduceMQ.matches && !saveData) { loadVideo(v); safePlay(v); }
        else if (!v.paused) v.pause();
      });
    }, { threshold: 0.35 });
    $$('[data-lazy-video]').forEach(function (v) { io.observe(v); });
  }
  inlineLoops();

  /* ---------- Generic players ---------- */
  $$('[data-player]').forEach(function (p) {
    var btn = p.querySelector('.player__btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var type = p.dataset.type, src = p.dataset.src, el;
      if (type === 'mp4') {
        el = document.createElement('video');
        el.controls = true; el.autoplay = true; el.playsInline = true; el.src = src;
      } else {
        el = document.createElement('iframe');
        el.src = src;
        el.title = p.dataset.title || 'Видео';
        el.allow = 'autoplay; encrypted-media; fullscreen; picture-in-picture';
        el.allowFullscreen = true;
        el.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      }
      btn.remove();
      p.appendChild(el);
      el.focus && el.focus();
    });
  });

  var dlg = $('[data-dialog]');
  if (dlg && typeof dlg.showModal === 'function') {
    var dlgBody = $('[data-dialog-body]', dlg), dlgTitle = $('[data-dialog-title]', dlg), opener = null;
    var closeDlg = function () { dlg.close(); };
    dlg.addEventListener('close', function () {
      dlgBody.innerHTML = '';
      if (hero && hero.dataset.dialogPaused) { delete hero.dataset.dialogPaused; var v = $('[data-hero-video]'); if (v) safePlay(v); }
      if (opener) opener.focus();
    });
    $('[data-dialog-close]', dlg).addEventListener('click', closeDlg);
    dlg.addEventListener('click', function (e) { if (e.target === dlg) closeDlg(); });
    $$('[data-open-video]').forEach(function (b) {
      b.addEventListener('click', function () {
        opener = b;
        var v = document.createElement('video');
        v.controls = true; v.autoplay = true; v.playsInline = true; v.src = b.dataset.openVideo;
        dlgBody.innerHTML = ''; dlgBody.appendChild(v);
        dlgTitle.textContent = b.dataset.videoTitle || 'Видео';
        var hvid = $('[data-hero-video]');
        if (hvid && !hvid.paused) { hvid.pause(); hero.dataset.dialogPaused = '1'; }
        dlg.showModal();
      });
    });
  } else {
    // No <dialog> support: open the file directly
    $$('[data-open-video]').forEach(function (b) {
      b.addEventListener('click', function () { location.href = b.dataset.openVideo; });
    });
  }

  /* ---------- Archive filtering / paging ---------- */
  function paging(list, size) {
    var items = $$(':scope > *', list);
    var wrap = list.parentNode.querySelector('[data-more-wrap]');
    var shown = size;
    var apply = function () {
      var visible = items.filter(function (el) { return !el.dataset.filteredOut; });
      visible.forEach(function (el, i) { el.hidden = i >= shown; });
      items.forEach(function (el) { if (el.dataset.filteredOut) el.hidden = true; });
      if (wrap) wrap.hidden = visible.length <= shown;
      return visible.length;
    };
    if (wrap) wrap.querySelector('[data-more]').addEventListener('click', function () {
      var firstHidden = items.filter(function (el) { return el.hidden && !el.dataset.filteredOut; })[0];
      shown += size; apply();
      if (firstHidden) { var a = firstHidden.matches('a') ? firstHidden : firstHidden.querySelector('a'); if (a) a.focus({ preventScroll: true }); }
    });
    return { apply: apply, reset: function () { shown = size; return apply(); } };
  }

  var filters = $('[data-filters]');
  var archive = $('[data-archive]');
  if (filters && archive) {
    var cards = $$(':scope > .acard', archive);
    var pager = paging(archive, 24);
    var btns = $$('[data-filter]', filters);
    var search = $('[data-search]', filters);
    var count = $('[data-count]', filters);
    var empty = $('[data-empty]');
    var tagRow = $('[data-tag-row]', filters), tagLabel = $('[data-tag-label]', filters);
    var tagNames = {};
    try { JSON.parse($('[data-tag-names]').textContent).forEach(function (t) { tagNames[t[0]] = t[1]; }); } catch (e) {}
    var params = new URLSearchParams(location.search);
    var state = { cat: params.get('cat') || '', tag: params.get('tag') || '', q: params.get('q') || '' };
    if (search) search.value = state.q;

    var run = function (push) {
      var q = state.q.trim().toLowerCase();
      var n = 0;
      cards.forEach(function (c) {
        var ok = (!state.cat || (' ' + c.dataset.cats + ' ').indexOf(' ' + state.cat + ' ') > -1) &&
                 (!state.tag || (' ' + c.dataset.tags + ' ').indexOf(' ' + state.tag + ' ') > -1) &&
                 (!q || c.dataset.search.indexOf(q) > -1);
        if (ok) { delete c.dataset.filteredOut; n++; } else c.dataset.filteredOut = '1';
      });
      pager.reset();
      btns.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.filter === state.cat)); });
      if (count) count.textContent = n + ' ' + plural(n, 'работа', 'работы', 'работ');
      if (empty) empty.hidden = n > 0;
      if (tagRow) {
        tagRow.hidden = !state.tag;
        if (state.tag) tagLabel.textContent = 'Метка: ' + (tagNames[state.tag] || state.tag);
      }
      if (push) {
        var p = new URLSearchParams();
        if (state.cat) p.set('cat', state.cat);
        if (state.tag) p.set('tag', state.tag);
        if (state.q) p.set('q', state.q);
        history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
      }
    };
    btns.forEach(function (b) {
      b.addEventListener('click', function () { state.cat = b.dataset.filter; run(true); });
    });
    var tmr;
    if (search) search.addEventListener('input', function () {
      clearTimeout(tmr);
      tmr = setTimeout(function () { state.q = search.value; run(true); }, 160);
    });
    var clear = $('[data-tag-clear]', filters);
    if (clear) clear.addEventListener('click', function (e) { e.preventDefault(); state.tag = ''; run(true); });
    run(false);
    // Make the active filter visible in the scroller
    var act = btns.filter(function (b) { return b.dataset.filter === state.cat; })[0];
    if (act && act.scrollIntoView && state.cat) act.scrollIntoView({ block: 'nearest', inline: 'center' });
  } else {
    $$('[data-paged]').forEach(function (list) { paging(list, parseInt(list.dataset.pageSize || '12', 10)).apply(); });
  }

  /* ---------- Mail form (no backend: prepares an e-mail) ---------- */
  $$('[data-mail-form]').forEach(function (form) {
    var status = $('[data-form-status]', form);
    var submit = form.querySelector('[type="submit"]');
    var check = function (input, msg) {
      var err = document.getElementById(input.id + '-err');
      var bad = !input.value.trim();
      input.setAttribute('aria-invalid', String(bad));
      if (err) err.textContent = bad ? msg : '';
      return !bad;
    };
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var f = form.elements;
      var ok = [check(f.name, 'Как к вам обращаться?'), check(f.contact, 'Оставьте телефон или e-mail для ответа'),
                check(f.task, 'Опишите задачу хотя бы в двух словах')];
      if (ok.indexOf(false) > -1) {
        var firstBad = form.querySelector('[aria-invalid="true"]');
        if (firstBad) firstBad.focus();
        return;
      }
      var body = 'Имя: ' + f.name.value.trim() + '\nКонтакт: ' + f.contact.value.trim() +
        (f.when.value.trim() ? '\nДаты и место: ' + f.when.value.trim() : '') + '\n\nЗадача:\n' + f.task.value.trim() +
        '\n\n— отправлено с сайта SFX Studio';
      var href = 'mailto:' + form.action.replace(/^mailto:/, '') + '?subject=' +
        encodeURIComponent('Запрос на спецэффекты — ' + f.name.value.trim()) + '&body=' + encodeURIComponent(body);
      submit.disabled = true;
      setTimeout(function () { submit.disabled = false; }, 3000);
      window.location.href = href;
      if (status) {
        status.hidden = false;
        status.textContent = 'Письмо подготовлено в вашей почтовой программе — проверьте и нажмите «Отправить». Если ничего не открылось, напишите на ' +
          form.action.replace(/^mailto:/, '') + ' или позвоните.';
      }
    });
    $$('input, textarea', form).forEach(function (el) {
      el.addEventListener('input', function () {
        if (el.getAttribute('aria-invalid') === 'true' && el.value.trim()) {
          el.setAttribute('aria-invalid', 'false');
          var err = document.getElementById(el.id + '-err'); if (err) err.textContent = '';
        }
      });
    });
  });

  /* ---------- Background loops that must respect reduced motion ---------- */
  $$('[data-autoplay-motion]').forEach(function (v) {
    if (reduceMQ.matches || saveData) { v.removeAttribute('autoplay'); v.pause(); }
  });

  /* ---------- Reveal + scroll choreography ---------- */
  var revealEls = $$('[data-reveal],[data-reveal-mask]');
  if (!reduceMQ.matches && 'IntersectionObserver' in window && revealEls.length) {
    doc.classList.add('reveal-ready');
    var rio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var t = en.target;
        if (t._maskKids) t._maskKids.forEach(function (k) { k.classList.add('is-in'); });
        if (t.hasAttribute('data-reveal')) t.classList.add('is-in');
        rio.unobserve(t);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    // A fully clipped element is invisible to IntersectionObserver, so masked
    // headings are observed through their parent.
    revealEls.forEach(function (el) {
      if (el.hasAttribute('data-reveal-mask')) {
        var parent = el.parentNode;
        (parent._maskKids = parent._maskKids || []).push(el);
        rio.observe(parent);
      } else rio.observe(el);
    });
  }

  function withGsap() {
    var gsap = window.gsap, ST = window.ScrollTrigger;
    if (!gsap || !ST) return false;
    gsap.registerPlugin(ST);
    var mm = gsap.matchMedia();
    mm.add({ desktop: '(min-width: 1000px)', motion: '(prefers-reduced-motion: no-preference)' }, function (ctx) {
      var c = ctx.conditions;
      // Hero entrance: words rise from their own line, one by one
      if (hero && c.motion) {
        gsap.from($$('[data-elements] a', hero), { yPercent: 105, duration: 1.1, ease: 'expo.out', stagger: 0.07, delay: 0.1 });
        gsap.from($$('.hero__copy > *, .hero__top, .hero__bar', hero), { autoAlpha: 0, y: 16, duration: .9, ease: 'power3.out', stagger: .06, delay: .45 });
        // Depth: the shot drifts slower than the page as it leaves
        gsap.to($('.hero__media', hero), { yPercent: 14, ease: 'none', scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true } });
      }
      // Atmospheric backgrounds drift a little slower than the page (background layer only)
      if (c.motion) {
        $$('.atmo').forEach(function (sec) {
          var bg = sec.querySelector('.atmo__bg');
          if (bg) gsap.fromTo(bg, { yPercent: -5 }, { yPercent: 5, ease: 'none', scrollTrigger: { trigger: sec, start: 'top bottom', end: 'bottom top', scrub: true } });
        });
      }
      // Chapters drive the sticky stage
      if (c.desktop && stage) {
        chapters.forEach(function (ch) {
          ST.create({ trigger: ch, start: 'top 55%', end: 'bottom 55%', onToggle: function (self) { if (self.isActive) activateStage(ch.dataset.chapter); } });
        });
        activateStage(chapters[0] && chapters[0].dataset.chapter);
      }
      return function () { activeKey = null; };
    });
    return true;
  }
  // Without GSAP the stage still works via IntersectionObserver
  function stageFallback() {
    if (!stage || !('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting && desktopMQ.matches) activateStage(en.target.dataset.chapter); });
    }, { rootMargin: '-45% 0px -45% 0px' });
    chapters.forEach(function (c) { io.observe(c); });
  }
  if (!withGsap()) stageFallback();
})();
