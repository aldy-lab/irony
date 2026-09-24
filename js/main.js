/* =========================================================================
   Irony vs. Satyr — catalogue

   This is a catalogue, not a shop: nothing is bought here. The grid is
   rendered statically by build.py so it is crawlable and works with
   JavaScript off; everything below only narrows what is already on the page.

   Product data is written into each page by build.py as window.IVS.
   ========================================================================= */

(function () {
  "use strict";

  var IVS = window.IVS || {};
  var AGE_KEY = "ivs.age.v1";

  /* ---------------------------------------------------------------------
     Storage is guarded everywhere: in a private window, with site data
     blocked, or during a thumbnail capture these throw, and the page still
     has to render.
     --------------------------------------------------------------------- */

  function read(key, fallback) {
    try {
      var raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* A remembered answer is a convenience, not a requirement. */
    }
  }

  /* Strip diacritics, so "Becherovka" finds "Bečerovka" and the other way
     round. build.py folds the searchable text the same way. */
  function fold(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  /* ---------------------------------------------------------------------
     Catalogue filtering
     --------------------------------------------------------------------- */

  var root = document.querySelector("[data-catalogue]");
  if (root) {
    var grid = root.querySelector("[data-grid]");
    var cards = Array.prototype.slice.call(grid.children);
    var options = root.querySelectorAll("[data-filter]");
    var facets = root.querySelector("[data-facets]");
    var facetsToggle = root.querySelector("[data-facets-toggle]");
    var facetCount = root.querySelector("[data-facet-count]");
    var search = root.querySelector("[data-search]");
    var searchWrap = root.querySelector("[data-search-wrap]");
    var clear = root.querySelector("[data-search-clear]");
    var priceSelect = root.querySelector("[data-price]");
    var strengthSelect = root.querySelector("[data-strength]");
    var sizeSelect = root.querySelector("[data-size]");
    var sortSelect = root.querySelector("[data-sort]");
    var reset = root.querySelector("[data-reset]");
    var count = root.querySelector("[data-result-count]");
    var empty = root.querySelector("[data-no-results]");

    // The order the client put them in, so "our order" can be restored.
    cards.forEach(function (card, i) {
      card.dataset.order = i;
    });

    var state = {
      category: "all",
      q: "",
      price: "any",
      strength: "any",
      size: "any",
      sort: "default",
    };

    function inBand(value, band) {
      if (band === "any") return true;
      var parts = band.split("-");
      var min = parts[0] === "" ? -Infinity : parseFloat(parts[0]);
      var max = parts[1] === "" ? Infinity : parseFloat(parts[1]);
      return value >= min && value <= max;
    }

    function matches(card) {
      if (state.category !== "all" && card.dataset.category !== state.category) {
        return false;
      }
      if (!inBand(parseFloat(card.dataset.price), state.price)) return false;
      if (!inBand(parseFloat(card.dataset.abv), state.strength)) return false;
      if (state.size !== "any" && card.dataset.volume !== state.size) return false;
      if (state.q) {
        // data-search holds name, producer, category and tasting note, all
        // lowercased at build time so this stays a substring test.
        if (card.dataset.search.indexOf(state.q) === -1) return false;
      }
      return true;
    }

    function sortCards() {
      var mode = state.sort;
      var ordered = cards.slice().sort(function (a, b) {
        if (mode === "price-asc") return num(a, "price") - num(b, "price");
        if (mode === "price-desc") return num(b, "price") - num(a, "price");
        if (mode === "abv-desc") return num(b, "abv") - num(a, "abv");
        if (mode === "newest") {
          return (b.dataset.added || "").localeCompare(a.dataset.added || "");
        }
        if (mode === "name") return a.dataset.name.localeCompare(b.dataset.name);
        return num(a, "order") - num(b, "order");
      });
      ordered.forEach(function (card) {
        grid.appendChild(card);
      });
    }

    function num(el, key) {
      return parseFloat(el.dataset[key]) || 0;
    }

    var motionOK = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var first = true;
    var lastMiss = "";

    function apply() {
      var shown = 0;
      cards.forEach(function (card) {
        var ok = matches(card);
        // Only cards that were hidden a moment ago animate in; the ones that
        // were already on screen must not flicker every keystroke.
        var returning = ok && card.hidden && !first && motionOK;
        card.hidden = !ok;
        if (returning) {
          card.classList.remove("is-entering");
          void card.offsetWidth; // restart the animation
          card.classList.add("is-entering");
        }
        if (ok) shown += 1;
      });
      first = false;

      sortCards();

      options.forEach(function (option) {
        option.setAttribute(
          "aria-pressed",
          option.dataset.filter === state.category ? "true" : "false"
        );
      });

      if (count) {
        count.textContent = shown + (shown === 1 ? " bottle" : " bottles");
      }
      if (empty) empty.hidden = shown !== 0;

      // A search that finds nothing is the most useful thing the shop can
      // learn — it is a bottle somebody wanted and the shelf did not have.
      // Only reported if analytics is switched on at all; with it off,
      // window.plausible does not exist and nothing is sent anywhere.
      if (shown === 0 && state.q && state.q !== lastMiss) {
        lastMiss = state.q;
        if (typeof window.plausible === "function") {
          window.plausible("Search miss", { props: { query: state.q } });
        }
      }
      if (shown > 0) lastMiss = "";
      if (searchWrap) {
        searchWrap.setAttribute("data-filled", state.q ? "true" : "false");
      }

      // How many filters are actually narrowing the list — shown on the
      // collapsed button, so a phone visitor can see the list is filtered
      // without opening the panel.
      var active = [
        state.category !== "all",
        state.q !== "",
        state.price !== "any",
        state.strength !== "any",
        state.size !== "any",
      ].filter(Boolean).length;

      if (reset) reset.hidden = active === 0;
      if (facetCount) {
        facetCount.textContent = active;
        facetCount.hidden = active === 0;
      }

      writeUrl();
    }

    // The filtered view is shareable and survives a reload.
    function writeUrl() {
      var url = new URL(window.location.href);
      var map = {
        c: state.category === "all" ? "" : state.category,
        q: state.q,
        price: state.price === "any" ? "" : state.price,
        abv: state.strength === "any" ? "" : state.strength,
        ml: state.size === "any" ? "" : state.size,
        sort: state.sort === "default" ? "" : state.sort,
      };
      Object.keys(map).forEach(function (key) {
        if (map[key]) url.searchParams.set(key, map[key]);
        else url.searchParams.delete(key);
      });
      window.history.replaceState({}, "", url);
    }

    function readUrl() {
      var p = new URL(window.location.href).searchParams;
      var category = p.get("c");
      if (category && root.querySelector('[data-filter="' + CSS.escape(category) + '"]')) {
        state.category = category;
      }
      state.q = fold(p.get("q") || "");
      state.price = p.get("price") || "any";
      state.strength = p.get("abv") || "any";
      state.size = p.get("ml") || "any";
      state.sort = p.get("sort") || "default";

      if (search) search.value = p.get("q") || "";
      if (priceSelect) priceSelect.value = state.price;
      if (strengthSelect) strengthSelect.value = state.strength;
      if (sizeSelect) sizeSelect.value = state.size;
      if (sortSelect) sortSelect.value = state.sort;
    }

    var narrow = function () {
      return window.matchMedia("(max-width: 899px)").matches;
    };

    function closePanelAndShowResults() {
      if (!narrow() || !facets || facets.getAttribute("data-open") !== "true") return;
      facets.setAttribute("data-open", "false");
      if (facetsToggle) facetsToggle.setAttribute("aria-expanded", "false");
      // Choosing a filter and being left looking at the filter panel is the
      // one thing that made this feel unfinished on a phone.
      var head = root.querySelector(".results__head");
      if (head) head.scrollIntoView({ block: "start", behavior: "smooth" });
    }

    options.forEach(function (option) {
      option.addEventListener("click", function () {
        state.category = option.dataset.filter;
        apply();
        closePanelAndShowResults();
      });
    });

    var randomButton = root.querySelector("[data-random]");
    if (randomButton) {
      randomButton.addEventListener("click", function () {
        var open = cards.filter(function (card) {
          return !card.hidden;
        });
        if (!open.length) return;
        var pick = open[Math.floor(Math.random() * open.length)];
        var link = pick.querySelector(".card__link");
        if (link) window.location.href = link.getAttribute("href");
      });
    }

    if (facetsToggle && facets) {
      facetsToggle.addEventListener("click", function () {
        var open = facets.getAttribute("data-open") === "true";
        facets.setAttribute("data-open", open ? "false" : "true");
        facetsToggle.setAttribute("aria-expanded", open ? "false" : "true");
      });
    }

    if (search) {
      var typing = null;
      search.addEventListener("input", function () {
        window.clearTimeout(typing);
        typing = window.setTimeout(function () {
          state.q = fold(search.value.trim());
          apply();
        }, 130);
      });
    }

    if (clear) {
      clear.addEventListener("click", function () {
        search.value = "";
        state.q = "";
        search.focus();
        apply();
      });
    }

    [
      [priceSelect, "price"],
      [strengthSelect, "strength"],
      [sizeSelect, "size"],
      [sortSelect, "sort"],
    ].forEach(function (pair) {
      var el = pair[0];
      var key = pair[1];
      if (!el) return;
      el.addEventListener("change", function () {
        state[key] = el.value;
        apply();
      });
    });

    if (reset) {
      reset.addEventListener("click", function () {
        state.category = "all";
        state.q = "";
        state.price = "any";
        state.strength = "any";
        state.size = "any";
        if (search) search.value = "";
        if (priceSelect) priceSelect.value = "any";
        if (strengthSelect) strengthSelect.value = "any";
        if (sizeSelect) sizeSelect.value = "any";
        apply();
      });
    }

    grid.addEventListener("animationend", function (event) {
      if (event.animationName === "card-in") {
        event.target.classList.remove("is-entering");
      }
    });

    var SCROLL_KEY = "ivs.scroll.v1";

    if ("scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }

    window.addEventListener("pagehide", function () {
      try {
        window.sessionStorage.setItem(
          SCROLL_KEY,
          JSON.stringify({ url: window.location.href, y: window.scrollY })
        );
      } catch (e) {
        /* a lost scroll position is a papercut, not a failure */
      }
    });

    function restoreScroll() {
      var saved;
      try {
        saved = JSON.parse(window.sessionStorage.getItem(SCROLL_KEY) || "null");
      } catch (e) {
        return;
      }
      if (!saved || saved.url !== window.location.href || !saved.y) return;
      // After the grid has been filtered and laid out, or the number is
      // measured against a page of a different length.
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          window.scrollTo(0, saved.y);
        });
      });
    }

    // Let the opening stagger finish, then take it out of the way so filtering
    // is instant rather than waiting on a queue of delays.
    var settle = 600 + 11 * 45;
    window.setTimeout(function () {
      grid.setAttribute("data-settled", "true");
    }, settle);

    readUrl();
    apply();
    restoreScroll();
  }

  /* ---------------------------------------------------------------------
     Age gate. The page is hidden only once JavaScript confirms the gate is
     needed, so a crawler or a no-script visitor is never shown a blank page.
     --------------------------------------------------------------------- */

  // The answer is remembered, so offer a way to forget it. The control stays
  // hidden until there is something stored, and does nothing if storage is
  // unavailable — in which case the gate was never skipped anyway.
  var ageReset = document.querySelector("[data-age-reset]");
  if (ageReset && read(AGE_KEY, false) === true) {
    ageReset.hidden = false;
    ageReset.addEventListener("click", function () {
      try {
        window.localStorage.removeItem(AGE_KEY);
      } catch (e) {
        /* nothing stored means nothing to clear */
      }
      window.location.reload();
    });
  }

  var gate = document.querySelector("[data-age-gate]");
  if (gate) {
    if (read(AGE_KEY, false) !== true) {
      gate.hidden = false;

      // Focus starts inside the dialog and stays there. There is no Escape:
      // an age gate you can dismiss without answering is not a gate.
      var heading = gate.querySelector("h1");
      if (heading) heading.focus();

      gate.addEventListener("keydown", function (event) {
        if (event.key !== "Tab") return;
        var stops = gate.querySelectorAll("button");
        if (!stops.length) return;
        var first = stops[0];
        var last = stops[stops.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      });

      gate.querySelector("[data-age-yes]").addEventListener("click", function () {
        write(AGE_KEY, true);
        document.documentElement.classList.remove("is-gated");
        gate.hidden = true;
        var skip = document.querySelector(".skip-link");
        if (skip) skip.focus();
      });

      gate.querySelector("[data-age-no]").addEventListener("click", function () {
        gate.setAttribute("data-denied", "true");
      });
    }
  }

  /* ---------------------------------------------------------------------
     Navigation
     --------------------------------------------------------------------- */

  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", open ? "false" : "true");
      nav.setAttribute("data-open", open ? "false" : "true");
    });

    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        toggle.setAttribute("aria-expanded", "false");
        nav.setAttribute("data-open", "false");
      }
    });
  }

  /* ---------------------------------------------------------------------
     Reveal on scroll
     --------------------------------------------------------------------- */

  var reveals = document.querySelectorAll("[data-reveal]");
  if (reveals.length && "IntersectionObserver" in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.setAttribute("data-revealed", "true");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    reveals.forEach(function (el) {
      observer.observe(el);
    });
  } else {
    reveals.forEach(function (el) {
      el.setAttribute("data-revealed", "true");
    });
  }

  /* ---------------------------------------------------------------------
     After hours. Type the second half of the name.
     --------------------------------------------------------------------- */

  var typed = "";
  window.addEventListener("keydown", function (event) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    var tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (event.key.length !== 1) return;

    typed = (typed + event.key.toLowerCase()).slice(-5);
    if (typed !== "satyr") return;

    if (document.body.getAttribute("data-colourway") === "satyr") {
      document.body.removeAttribute("data-colourway");
    } else {
      document.body.setAttribute("data-colourway", "satyr");
    }
    typed = "";
  });
})();
