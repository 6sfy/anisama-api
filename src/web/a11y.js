(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const lang = () => (localStorage.getItem('anisama-lang') === 'fr' ? 'fr' : 'en');

  const TXT = {
    en: { menuOpen: 'Open menu', menuClose: 'Close menu', copy: 'Copy code', copied: 'Copied', lang: 'Change language',
          search: 'Search the docs', cmd: 'Terminal command', out: 'Terminal output', skip: 'Skip to content', nav: 'Documentation' },
    fr: { menuOpen: 'Ouvrir le menu', menuClose: 'Fermer le menu', copy: 'Copier le code', copied: 'Copié', lang: 'Changer de langue',
          search: 'Rechercher dans la doc', cmd: 'Commande du terminal', out: 'Sortie du terminal', skip: 'Aller au contenu', nav: 'Documentation' }
  };
  const t = k => TXT[lang()][k];

  const P = {
    globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3" style="transform:translateX(1px)"/>',
    list: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>'
  };
  const ICON_ORDER = ['globe', 'target', 'zap', 'play', 'list', 'info'];
  const svg = name => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + P[name] + '</svg>';

  function labels() {
    const menu = $('#menuBtn');
    if (menu) {
      const open = $('#sidebar')?.classList.contains('open');
      menu.setAttribute('aria-label', open ? t('menuClose') : t('menuOpen'));
      menu.setAttribute('aria-expanded', open ? 'true' : 'false');
      menu.setAttribute('aria-controls', 'sidebar');
    }
    $('#langBtn')?.setAttribute('aria-label', t('lang') + ' (' + lang().toUpperCase() + ')');
    $('#sInput')?.setAttribute('aria-label', t('search'));
    $('#termIn')?.setAttribute('aria-label', t('cmd'));
    $('#termOut')?.setAttribute('aria-label', t('out'));
    $('#nav')?.setAttribute('aria-label', t('nav'));
    const skip = $('.skip-link');
    if (skip) skip.textContent = t('skip');
    $$('.copy-btn').forEach(b => { b.setAttribute('aria-label', t('copy')); b.setAttribute('type', 'button'); });
  }

  const linkFor = id => $$('.nav-group-item').find(a => (a.getAttribute('onclick') || '').includes("'" + id + "'"));

  function setCurrent(link) {
    $$('.nav-group-item').forEach(a => a.removeAttribute('aria-current'));
    link?.setAttribute('aria-current', 'page');
  }

  function activate(id, link) {
    $$('.page').forEach(p => p.classList.remove('active'));
    const page = $('#p-' + id);
    if (page) page.classList.add('active');
    $$('.nav-group-item').forEach(a => a.classList.remove('active'));
    if (link) link.classList.add('active');
    $('#sidebar')?.classList.remove('open');
    $('#overlay')?.classList.remove('active');
    if (id === 'terminal') $('#termIn')?.focus();
    window.scrollTo(0, 0);
  }

  function go(id, { focus = true, push = true } = {}) {
    const link = linkFor(id);
    activate(id, link);
    setCurrent(link);
    if (focus && id !== 'terminal') {
      const h = $('#p-' + id + ' h1');
      if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
    }

    if (push && window.location.hash !== '#/' + id) {
      window.history.pushState(null, '', '#/' + id);
    }
  }

  function fromHash() {
    const id = window.location.hash.replace(/^#\/?/, '');
    if (id && $('#p-' + id) && !$('#p-' + id).classList.contains('active')) go(id, { focus: false, push: false });
  }

  function init() {

    const main = $('main');
    if (main) { main.id = 'main'; main.setAttribute('tabindex', '-1'); }
    const skip = document.createElement('a');
    skip.className = 'skip-link'; skip.href = '#main';
    skip.addEventListener('click', e => { e.preventDefault(); main?.focus(); });
    document.body.prepend(skip);

    const live = document.createElement('div');
    live.className = 'sr-only'; live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite');
    document.body.append(live);
    document.addEventListener('click', e => {
      if (e.target.closest('.copy-btn')) { live.textContent = ''; setTimeout(() => (live.textContent = t('copied')), 50); }
    });

    $$('.nav-group-item').forEach(a => {
      const m = (a.getAttribute('onclick') || '').match(/showPage\('([^']+)'/);
      if (m) a.setAttribute('href', '#/' + m[1]);
    });
    setCurrent($('.nav-group-item.active'));

    $$('.nav-group-header').forEach(h => {
      h.setAttribute('role', 'button'); h.setAttribute('tabindex', '0'); h.setAttribute('aria-expanded', 'true');
      h.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); h.click(); } });
    });

    $$('.sidebar-search svg,.theme-btn svg,.lang-btn svg,.nav-group-header svg,.copy-btn svg')
      .forEach(s => { s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false'); });

    $$('.grid .card .icon').forEach((el, i) => { if (ICON_ORDER[i]) el.innerHTML = svg(ICON_ORDER[i]); el.setAttribute('aria-hidden', 'true'); });

    const out = $('#termOut');
    if (out) { out.setAttribute('role', 'log'); out.setAttribute('aria-live', 'polite'); out.setAttribute('tabindex', '0'); }
    $('#sInput')?.setAttribute('type', 'search');
    $('#overlay')?.setAttribute('aria-hidden', 'true');

    labels();
    fromHash();
  }

  window.showPage = function (id) { go(id); return false; };

  ['applyLang', 'toggleLang', 'injectCopyButtons'].forEach(n => {
    const orig = window[n];
    if (typeof orig === 'function') window[n] = function () { const r = orig.apply(this, arguments); labels(); return r; };
  });
  ['toggleSidebar', 'closeSidebar'].forEach(n => {
    const orig = window[n];
    if (typeof orig === 'function') window[n] = function () { const r = orig.apply(this, arguments); labels(); return r; };
  });
  const _group = window.toggleGroup;
  if (typeof _group === 'function') {
    window.toggleGroup = function (el) {
      _group(el);
      el.setAttribute('aria-expanded', String(!el.closest('.nav-group')?.classList.contains('collapsed')));
    };
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && $('#sidebar')?.classList.contains('open')) { window.closeSidebar?.(); $('#menuBtn')?.focus(); }
  });
  window.addEventListener('popstate', fromHash);
  window.addEventListener('hashchange', fromHash);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
