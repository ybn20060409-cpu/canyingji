/**
 * 残影集 — Search & Client-Side Scripts
 * Vanilla JS, no frameworks.
 */
(function () {
  'use strict';

/* ── State ─────────────────────────────────────────── */
  let searchIndex = { articles: [], poems: [] };
  let allWorks = [];
  let debounceTimer = null;

/* ── DOM References ─────────────────────────────────── */
  const searchInput = document.getElementById('search-input');
  const searchResults = document.getElementById('search-results');
  const seriesBtns = document.querySelectorAll('.series-btn');
  const workCards = document.querySelectorAll('.work-card');
  const progressBar = document.getElementById('reading-progress');

/* ── Theme ─────────────────────────────────────────── */
  function initTheme() {
    // Sync theme-toggle button state
    var btn = document.querySelector('.theme-toggle');
    if (!btn) return;
    if (localStorage.getItem('theme') === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      btn.innerHTML = '☀️';
    }
    // Listen for TOC scroll highlight
    initTocHighlight();
  }

  function initTocHighlight() {
    var tocItems = document.querySelectorAll('.toc-item a');
    if (!tocItems.length) return;
    var headings = [];
    tocItems.forEach(function(a) {
      var href = a.getAttribute('href');
      if (href && href.startsWith('#')) {
        var el = document.getElementById(href.slice(1));
        if (el) headings.push({ anchor: a, target: el });
      }
    });
    if (!headings.length) return;
    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          var scrollPos = window.scrollY + 100;
          var current = null;
          headings.forEach(function(h) {
            if (h.target.offsetTop <= scrollPos) current = h;
          });
          tocItems.forEach(function(a) { a.parentElement.classList.remove('active'); });
          if (current) current.anchor.parentElement.classList.add('active');
          ticking = false;
        });
        ticking = true;
      }
    });
  }

/* ── Init ──────────────────────────────────────────── */
  function init() {
    initTheme();
    loadSearchIndex();
    bindSearch();
    bindSeriesFilter();
    bindMobileMenu();
    bindSmoothScroll();
    bindCopyLink();
    initReadingProgress();
    checkUrlHash();
  }

/* ── Load Search Index ─────────────────────────────── */
  async function loadSearchIndex() {
    try {
      const resp = await fetch('/search-index.json');
      if (!resp.ok) throw new Error('Failed to load search index');
      searchIndex = await resp.json();
      // Flatten into a unified array for filtering
      allWorks = [
        ...(searchIndex.articles || []).map(w => ({ ...w, type: 'article' })),
        ...(searchIndex.poems || []).map(w => ({ ...w, type: 'poem' })),
      ];
    } catch (err) {
      console.warn('[残影集] Could not load search index:', err.message);
    }
  }

/* ── Search ────────────────────────────────────────── */
  function bindSearch() {
    if (!searchInput) return;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(performSearch, 300);
    });
    searchInput.addEventListener('focus', () => {
      if (searchInput.value.trim().length > 0) performSearch();
    });
    // Close results on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-box')) {
        if (searchResults) searchResults.classList.remove('open');
      }
    });
  }

  function performSearch() {
    if (!searchResults) return;
    const query = searchInput.value.trim().toLowerCase();
    if (query.length === 0) {
      searchResults.classList.remove('open');
      searchResults.innerHTML = '';
      return;
    }
    // Filter from fetched index
    let results = [];
    if (allWorks.length > 0) {
      results = allWorks.filter(w => {
        const inTitle = (w.title || '').toLowerCase().includes(query);
        const inText = (w.text || w.excerpt || '').toLowerCase().includes(query);
        const inTags = (w.tags || []).some(t => t.toLowerCase().includes(query));
        const inSeries = (w.series || '').toLowerCase().includes(query);
        return inTitle || inText || inTags || inSeries;
      });
    }
    // Also filter visible cards as fallback
    if (results.length === 0 && workCards.length > 0) {
      const cardMatches = [];
      workCards.forEach(card => {
        const title = card.querySelector('.card-title')?.textContent || '';
        const excerpt = card.querySelector('.card-excerpt')?.textContent || '';
        const series = card.querySelector('.card-series')?.textContent || '';
        const tags = Array.from(card.querySelectorAll('.tag')).map(t => t.textContent);
        const allText = (title + ' ' + excerpt + ' ' + series + ' ' + tags.join(' ')).toLowerCase();
        if (allText.includes(query)) {
          cardMatches.push(card.cloneNode(true));
        }
      });
      if (cardMatches.length > 0) {
        renderSearchResultsFromCards(cardMatches);
        return;
      }
    }
    renderSearchResults(results, query);
  }


  function renderSearchResults(results, query) {
    if (results.length === 0) {
      searchResults.innerHTML = '<div class="search-no-results">' +
        '没有找到匹配 “' + escapeHtml(query) +
        '” 的作品<br>' +
        '<span style="font-size:0.8em;opacity:0.7">试试其他关键词</span></div>';
      searchResults.classList.add('open');
      return;
    }
    var html = results.map(function(w) {
      var typeLabel = w.type === 'poem' ? '诗歌' : '文章';
      var href = '/' + w.type + '/' + w.slug + '.html';
      var date = w.date || '';
      var excerpt = w.excerpt || '';
      var tags = (w.tags || []).map(function(t) {
        return '<span class="tag">' + escapeHtml(t) + '</span>';
      }).join('');
      return '<a href="' + href + '" class="search-result-item">' +
        '<span class="result-type">' + typeLabel + '</span>' +
        '<span class="result-title">' + highlightMatch(w.title, query) + '</span>' +
        '<span class="result-date">' + date + '</span>' +
        '<span class="result-excerpt">' + escapeHtml(excerpt) + '</span>' +
        '<div class="result-tags">' + tags + '</div>' +
        '</a>';
    }).join('');
    searchResults.innerHTML = html;
    searchResults.classList.add('open');
  }

  function renderSearchResultsFromCards(cardClones) {
    searchResults.innerHTML = '';
    cardClones.forEach(function(clone) {
      clone.classList.add('search-result-card');
      searchResults.appendChild(clone);
    });
    searchResults.classList.add('open');
  }

  function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    var escaped = escapeHtml(text);
    var q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escaped.replace(new RegExp('(' + q + ')', 'gi'), '<mark>$1</mark>');
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

/* ── Series Filter ─────────────────────────────────── */
  function bindSeriesFilter() {
    if (!seriesBtns.length) return;
    seriesBtns.forEach(function(btn) {
      btn.addEventListener('click', function() {
        seriesBtns.forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var series = btn.getAttribute('data-series');
        filterWorks(series);
        // Update URL hash
        if (series === 'all') {
          history.replaceState(null, '', window.location.pathname);
        } else {
          history.replaceState(null, '', '#series=' + encodeURIComponent(series));
        }
      });
    });
  }

  function filterWorks(series) {
    if (!workCards.length) return;
    workCards.forEach(function(card) {
      if (series === 'all' || card.getAttribute('data-series') === series) {
        card.style.display = '';
      } else {
        card.style.display = 'none';
      }
    });
  }

/* ── Mobile Menu ───────────────────────────────────── */
  function bindMobileMenu() {
    // Create mobile menu button if it doesn't exist
    var header = document.querySelector('.header-inner');
    var nav = document.querySelector('.site-nav');
    if (!header || !nav) return;
    if (document.querySelector('.mobile-menu-btn')) return;

    var btn = document.createElement('button');
    btn.className = 'mobile-menu-btn';
    btn.setAttribute('aria-label', '菜单');
    btn.innerHTML = '<span></span><span></span><span></span>';
    header.insertBefore(btn, nav);

    btn.addEventListener('click', function() {
      btn.classList.toggle('open');
      nav.classList.toggle('open');
    });

    // Close menu on nav link click
    nav.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        btn.classList.remove('open');
        nav.classList.remove('open');
      });
    });
  }

/* ── Smooth Scroll ─────────────────────────────────── */
  function bindSmoothScroll() {
    document.addEventListener('click', function(e) {
      var link = e.target.closest('a[href^="#"]');
      if (!link) return;
      var targetId = link.getAttribute('href').slice(1);
      if (!targetId) return;
      var target = document.getElementById(targetId);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

/* ── Copy Link ─────────────────────────────────────── */
  function bindCopyLink() {
    var shareBtn = document.querySelector('.share-btn');
    if (!shareBtn) return;
    shareBtn.addEventListener('click', function() {
      var url = window.location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function() {
          showToast('链接已复制');
        });
      } else {
        // Fallback
        var input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('链接已复制');
      }
    });
  }

  function showToast(msg) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2000);
  }

/* ── Reading Progress ──────────────────────────────── */
  function initReadingProgress() {
    if (!progressBar) return;
    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(function() {
          updateProgress();
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  function updateProgress() {
    var scrollTop = window.scrollY || document.documentElement.scrollTop;
    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) {
      progressBar.style.width = '0%';
      return;
    }
    var pct = Math.min((scrollTop / docHeight) * 100, 100);
    progressBar.style.width = pct + '%';
  }

/* ── URL Hash Support ──────────────────────────────── */
  function checkUrlHash() {
    var hash = window.location.hash;
    if (!hash) return;

    // #search=xxx
    var searchMatch = hash.match(/^#search=(.+)/);
    if (searchMatch && searchInput) {
      var query = decodeURIComponent(searchMatch[1]);
      searchInput.value = query;
      // Wait for index to load, then search
      var retries = 0;
      var doSearch = function() {
        if (allWorks.length > 0 || retries > 10) {
          performSearch();
        } else {
          retries++;
          setTimeout(doSearch, 300);
        }
      };
      setTimeout(doSearch, 300);
    }

    // #series=xxx
    var seriesMatch = hash.match(/^#series=(.+)/);
    if (seriesMatch && seriesBtns.length) {
      var seriesName = decodeURIComponent(seriesMatch[1]);
      seriesBtns.forEach(function(btn) {
        if (btn.getAttribute('data-series') === seriesName) {
          btn.click();
        }
      });
    }
  }

/* ── Start ─────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
