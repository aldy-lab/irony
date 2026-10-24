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
    var inStock = root.querySelector("[data-instock]");
    var producerSelect = root.querySelector("[data-producer]");
    var reset = root.querySelector("[data-reset]");
    var count = root.querySelector("[data-result-count]");
    var empty = root.querySelector("[data-no-results]");

    // The order the client put them in, so "our order" can be restored.
    cards.forEach(function (card, i) {
      card.dataset.order = i;
    });

    var state = {
      categories: [],
      q: "",
      price: "any",
      strength: "any",
      size: "any",
      sort: "default",
      inStock: false,
      producer: "any",
    };

    function inBand(value, band) {
      if (band === "any") return true;
      var parts = band.split("-");
      var min = parts[0] === "" ? -Infinity : parseFloat(parts[0]);
      var max = parts[1] === "" ? Infinity : parseFloat(parts[1]);
      return value >= min && value <= max;
    }

    function matches(card) {
      if (state.categories.length &&
          state.categories.indexOf(card.dataset.category) === -1) {
        return false;
      }
      if (state.producer !== "any" && card.dataset.producer !== state.producer) {
        return false;
      }
      if (!inBand(parseFloat(card.dataset.price), state.price)) return false;
      if (!inBand(parseFloat(card.dataset.abv), state.strength)) return false;
      if (state.size !== "any" && card.dataset.volume !== state.size) return false;
      if (state.inStock && parseInt(card.dataset.stock, 10) <= 0) return false;
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
        var slug = option.dataset.filter;
        var on = slug === "all"
          ? state.categories.length === 0
          : state.categories.indexOf(slug) !== -1;
        option.setAttribute("aria-pressed", on ? "true" : "false");
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
        state.categories.length > 0,
        state.producer !== "any",
        state.q !== "",
        state.price !== "any",
        state.strength !== "any",
        state.size !== "any",
        state.inStock,
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
        c: state.categories.join(","),
        producer: state.producer === "any" ? "" : state.producer,
        q: state.q,
        price: state.price === "any" ? "" : state.price,
        abv: state.strength === "any" ? "" : state.strength,
        ml: state.size === "any" ? "" : state.size,
        stock: state.inStock ? "1" : "",
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
      state.categories = (p.get("c") || "")
        .split(",")
        .filter(function (slug) {
          return slug && root.querySelector('[data-filter="' + CSS.escape(slug) + '"]');
        });
      state.producer = p.get("producer") || "any";
      state.q = fold(p.get("q") || "");
      state.price = p.get("price") || "any";
      state.strength = p.get("abv") || "any";
      state.size = p.get("ml") || "any";
      state.inStock = p.get("stock") === "1";
      state.sort = p.get("sort") || read(SORT_KEY, "") || "default";

      if (search) search.value = p.get("q") || "";
      if (priceSelect) priceSelect.value = state.price;
      if (strengthSelect) strengthSelect.value = state.strength;
      if (sizeSelect) sizeSelect.value = state.size;
      if (inStock) inStock.checked = state.inStock;
      if (producerSelect) producerSelect.value = state.producer;
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
        var slug = option.dataset.filter;
        if (slug === "all") {
          state.categories = [];
        } else {
          var at = state.categories.indexOf(slug);
          if (at === -1) state.categories.push(slug);
          else state.categories.splice(at, 1);
        }
        apply();
        // Only leave the panel when the choice is likely finished — picking a
        // second category is the common case, and closing after the first
        // would fight the person.
        if (!state.categories.length || state.categories.length === 1) {
          closePanelAndShowResults();
        }
      });
    });

    if (producerSelect) {
      producerSelect.addEventListener("change", function () {
        state.producer = producerSelect.value;
        apply();
      });
    }

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

    /* Press the satyr and he fills, from the hooves up, in the accent — the
       way the bottle he is carrying would. At the top a dimension line prints
       under him, and then it drains and he is ink again.

       Nothing says so. The figure keeps its default cursor and stays
       aria-hidden: it is decoration that answers, not a control, and a screen
       reader loses nothing by never being told. Naming the variables `pour`
       and `pourFull` rather than anything shorter is deliberate — `settle`
       collided with a `var settle` two hundred lines down and hoisting gave
       them one binding, which threw only once somebody actually pressed. */
    var figure = document.querySelector("[data-pour-figure]");
    var satyr = figure && figure.querySelector(".mark");
    if (satyr) {
      var POUR_MS = 1500;
      var HOLD_MS = 2600;
      var still = window.matchMedia("(prefers-reduced-motion: reduce)");
      var pouring = false;
      var startedAt = 0;
      var frame = null;

      var fill = function (pct) {
        satyr.style.setProperty("--pour", pct + "%");
      };

      var drain = function () {
        var from = parseFloat(satyr.style.getPropertyValue("--pour")) || 0;
        var began = 0;
        var back = function (now) {
          if (!began) began = now;
          var pct = from * (1 - Math.min(1, (now - began) / 420));
          fill(pct);
          if (pct > 0) frame = window.requestAnimationFrame(back);
          else pouring = false;
        };
        if (still.matches) {
          fill(0);
          pouring = false;
        } else {
          frame = window.requestAnimationFrame(back);
        }
      };

      var pourFull = function () {
        figure.setAttribute("data-poured", "true");
        window.setTimeout(function () {
          figure.removeAttribute("data-poured");
          drain();
        }, HOLD_MS);
      };

      var pour = function (now) {
        var pct = Math.min(100, ((now - startedAt) / POUR_MS) * 100);
        fill(pct);
        if (pct < 100) frame = window.requestAnimationFrame(pour);
        else pourFull();
      };

      figure.addEventListener("click", function () {
        if (pouring) return;
        pouring = true;
        if (still.matches) {
          fill(100);
          pourFull();
        } else {
          startedAt = window.performance.now();
          frame = window.requestAnimationFrame(pour);
        }
      });
    }

    if (facetsToggle && facets) {
      facetsToggle.addEventListener("click", function () {
        var open = facets.getAttribute("data-open") === "true";
        facets.setAttribute("data-open", open ? "false" : "true");
        facetsToggle.setAttribute("aria-expanded", open ? "false" : "true");
        if (!open) {
          // Opening it should put you in it, not leave you on the button.
          var first = facets.querySelector("[data-search]");
          if (first) first.focus();
        }
      });

      // Escape closes the filters. Deliberately unlike the age gate, which
      // must not be dismissable without an answer.
      facets.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        if (facets.getAttribute("data-open") !== "true") return;
        facets.setAttribute("data-open", "false");
        facetsToggle.setAttribute("aria-expanded", "false");
        facetsToggle.focus();
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
        if (key === "sort") write(SORT_KEY, el.value);
        apply();
      });
    });

    if (inStock) {
      inStock.addEventListener("change", function () {
        state.inStock = inStock.checked;
        apply();
      });
    }

    if (reset) {
      reset.addEventListener("click", function () {
        state.categories = [];
        state.producer = "any";
        state.q = "";
        state.price = "any";
        state.strength = "any";
        state.size = "any";
        state.inStock = false;
        if (inStock) inStock.checked = false;
        if (producerSelect) producerSelect.value = "any";
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

    var SORT_KEY = "ivs.sort.v1";
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
     Open now

     Against the visitor's own clock. A build from last Tuesday cannot know
     it is Sunday, so the hours ship as data and the answer is worked out here.
     --------------------------------------------------------------------- */

  var openNow = document.querySelector("[data-open-now]");
  if (openNow && IVS.hours && IVS.hours.length) {
    (function () {
      var now = new Date();
      var day = (now.getDay() + 6) % 7; // Monday first, as the data is
      var minutes = now.getHours() * 60 + now.getMinutes();

      function parse(t) {
        var bits = t.split(":");
        return parseInt(bits[0], 10) * 60 + parseInt(bits[1] || "0", 10);
      }

      var open = null;
      IVS.hours.forEach(function (span) {
        if (span.days.indexOf(day) === -1) return;
        var from = parse(span.from);
        var to = parse(span.to);
        if (minutes >= from && minutes < to) open = { to: span.to };
      });

      if (open) {
        openNow.textContent = "Open until " + open.to;
        openNow.setAttribute("data-state", "open");
      } else {
        // The next opening, looking forward through the week.
        var next = null;
        for (var ahead = 0; ahead < 8 && !next; ahead += 1) {
          var d = (day + ahead) % 7;
          IVS.hours.forEach(function (span) {
            if (next || span.days.indexOf(d) === -1) return;
            if (ahead === 0 && minutes >= parse(span.from)) return;
            next = { when: ahead === 0 ? "today" : ahead === 1 ? "tomorrow" : null, at: span.from };
          });
        }
        openNow.textContent = next
          ? "Closed · opens " + (next.when ? next.when + " " : "") + next.at
          : "Closed";
        openNow.setAttribute("data-state", "closed");
      }
      openNow.hidden = false;
    })();
  }

  /* The back-to-top button earns its place only once there is a way back. */
  var toTop = document.querySelector("[data-to-top]");
  if (toTop) {
    toTop.hidden = false;
    var updateToTop = function () {
      var deep = window.scrollY > window.innerHeight * 1.5;
      toTop.setAttribute("data-shown", deep ? "true" : "false");
    };
    window.addEventListener("scroll", updateToTop, { passive: true });
    updateToTop();
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

  /* "/" jumps to the search box, the way it does in anything people search
     in often. Ignored while already typing somewhere. */
  window.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    var tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    var box = document.querySelector("[data-search]");
    if (!box) return;
    event.preventDefault();
    var panel = document.querySelector("[data-facets]");
    var toggle = document.querySelector("[data-facets-toggle]");
    if (panel && toggle && window.matchMedia("(max-width: 899px)").matches) {
      panel.setAttribute("data-open", "true");
      toggle.setAttribute("aria-expanded", "true");
    }
    box.focus();
    box.select();
  });

  /* Share a bottle: the system sheet on a phone, the clipboard otherwise. */
  var shareButton = document.querySelector("[data-share]");
  if (shareButton) {
    var said = document.querySelector("[data-share-said]");
    shareButton.addEventListener("click", function () {
      var url = window.location.href;
      var title = shareButton.getAttribute("data-share-title") || document.title;
      if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(function () {
          /* dismissed — not an error */
        });
        return;
      }
      var done = function () {
        if (!said) return;
        said.hidden = false;
        window.setTimeout(function () {
          said.hidden = true;
        }, 2400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, function () {});
      }
    });
  }

  /* ---------------------------------------------------------------------
     Recently looked at

     A bottle shop is a place people come back to, so what you were looking at
     last time is more use than "similar products".
     --------------------------------------------------------------------- */

  var SEEN_KEY = "ivs.seen.v1";
  var seenStrip = document.querySelector("[data-recent]");
  var thisBottle = document.querySelector("[data-bottle]");

  if (thisBottle) {
    var entry = {
      slug: thisBottle.getAttribute("data-bottle"),
      name: thisBottle.getAttribute("data-bottle-name"),
      href: thisBottle.getAttribute("data-bottle-href"),
    };
    var seen = read(SEEN_KEY, []).filter(function (x) {
      return x && x.slug !== entry.slug;
    });
    seen.unshift(entry);
    write(SEEN_KEY, seen.slice(0, 6));
  }

  if (seenStrip) {
    var recent = read(SEEN_KEY, []).filter(function (x) {
      return x && x.slug && x.name && x.href;
    });
    if (recent.length > 1) {
      var list = seenStrip.querySelector("[data-recent-list]");
      recent.slice(0, 5).forEach(function (item) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = IVS.base + item.href;
        a.textContent = item.name;
        li.appendChild(a);
        list.appendChild(li);
      });
      seenStrip.hidden = false;
    }
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

/* -------------------------------------------------------------------------
   The menu's language
   Three languages, one on screen. The bar's own menu prints all three under
   every drink, which is the reason nobody reads any of them.
   ------------------------------------------------------------------------- */

(function () {
  var menu = document.querySelector("[data-menu]");
  if (!menu) return;

  var LANGS = ["en", "cs", "uk"];
  var KEY = "ivs.menu.lang";
  var picks = menu.querySelectorAll("[data-lang]");

  var stored = null;
  try {
    stored = window.localStorage.getItem(KEY);
  } catch (e) {
    /* private window, blocked storage: the menu still has to work */
  }

  /* Guessed from the browser only when nobody has chosen. Ukrainian first
     because a guest whose phone is in Ukrainian is the one least likely to
     be served by the other two. */
  var guess = "en";
  var tags = (navigator.languages || [navigator.language || ""]).join(",").toLowerCase();
  if (tags.indexOf("uk") === 0 || tags.indexOf(",uk") !== -1) guess = "uk";
  else if (tags.indexOf("cs") === 0 || tags.indexOf(",cs") !== -1) guess = "cs";

  var choose = function (code, remember) {
    if (LANGS.indexOf(code) === -1) code = "en";
    menu.setAttribute("data-lang", code);
    document.documentElement.setAttribute("lang", code);
    picks.forEach(function (button) {
      button.setAttribute(
        "aria-pressed", button.dataset.lang === code ? "true" : "false"
      );
    });
    if (!remember) return;
    try {
      window.localStorage.setItem(KEY, code);
    } catch (e) {}
  };

  choose(stored || guess, false);

  picks.forEach(function (button) {
    button.addEventListener("click", function () {
      choose(button.dataset.lang, true);
    });
  });

  /* ----------------------------------------------------------------- Tabs
     The categories drive a pager rather than anchoring down one long page.
     The movement itself is CSS scroll-snap: it stays smooth while the page
     is still fetching drawings, which a scroll animated in JS would not. */
  var pager = menu.querySelector("[data-pager]");
  var tabs = Array.prototype.slice.call(menu.querySelectorAll("[data-tab]"));
  var marker = menu.querySelector("[data-tab-marker]");
  var panels = Array.prototype.slice.call(menu.querySelectorAll("[data-panel]"));

  var markTab = function (index) {
    tabs.forEach(function (tab, i) {
      tab.setAttribute("aria-pressed", i === index ? "true" : "false");
    });
    var tab = tabs[index];
    if (!tab || !marker) return;
    /* Transform only — a marker that animated left/width would lay the tab
       strip out again on every frame. */
    marker.style.setProperty("--marker-x", tab.offsetLeft + "px");
    marker.style.setProperty("--marker-w", tab.offsetWidth);
    if (tab.scrollIntoView) {
      tab.scrollIntoView({ inline: "nearest", block: "nearest" });
    }
  };

  var current = 0;
  if (pager && tabs.length) {
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () {
        pager.scrollTo({ left: panels[i].offsetLeft - panels[0].offsetLeft });
        markTab(i);
      });
    });

    var settling = null;
    pager.addEventListener("scroll", function () {
      window.clearTimeout(settling);
      settling = window.setTimeout(function () {
        var width = pager.clientWidth || 1;
        var index = Math.round(pager.scrollLeft / width);
        index = Math.max(0, Math.min(tabs.length - 1, index));
        if (index !== current) {
          current = index;
          markTab(index);
        }
      }, 90);
    }, { passive: true });

    markTab(0);
    /* The strip is laid out before the fonts land, so the first measurement
       is of the wrong width. */
    window.addEventListener("load", function () { markTab(current); });
    window.addEventListener("resize", function () { markTab(current); });
  }

  /* --------------------------------------------------------------- Search
     It crosses every panel, so it answers in a panel of its own rather than
     emptying fourteen. The haystack is all three languages at once, so
     "bitter", "hořký" and "гіркий" each find the Negroni. */
  var search = menu.querySelector("[data-menu-search]");
  var results = menu.querySelector("[data-results]");
  var resultList = menu.querySelector("[data-results-list]");
  var found = menu.querySelector("[data-menu-count]");
  if (!search || !results) return;

  var fold = function (text) {
    return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  };

  var drinks = Array.prototype.map.call(
    menu.querySelectorAll(".pager .drink"),
    function (node) { return { node: node, hay: fold(node.textContent) }; }
  );

  var filter = function () {
    var term = fold(search.value.trim());
    if (!term) {
      menu.setAttribute("data-searching", "false");
      results.hidden = true;
      resultList.innerHTML = "";
      markTab(current);
      return;
    }
    var hits = drinks.filter(function (d) { return d.hay.indexOf(term) !== -1; });
    menu.setAttribute("data-searching", "true");
    results.hidden = false;
    resultList.innerHTML = "";
    hits.forEach(function (hit) {
      resultList.appendChild(hit.node.cloneNode(true));
    });
    found.textContent = hits.length
      ? hits.length + (hits.length === 1 ? " drink" : " drinks")
      : "Nothing by that name — ask the bar.";
  };

  var typing = null;
  search.addEventListener("input", function () {
    window.clearTimeout(typing);
    typing = window.setTimeout(filter, 120);
  });
  search.addEventListener("search", filter);
})();

/* -------------------------------------------------------------------------
   The chooser on the front page
   Two questions anybody standing at a bar can answer, and every answer it
   gives is a drink the bar actually pours. It narrows a real list rather
   than composing something nobody can order.
   ------------------------------------------------------------------------- */

(function () {
  var root = document.querySelector("[data-choose]");
  if (!root) return;

  var source = root.querySelector("[data-choose-data]");
  var list = root.querySelector("[data-choose-list]");
  var count = root.querySelector("[data-choose-count]");
  var none = root.querySelector("[data-choose-none]");
  if (!source || !list) return;

  var drinks;
  try {
    drinks = JSON.parse(source.textContent);
  } catch (e) {
    return;                       /* leave the page as the build wrote it */
  }

  var picked = { base: "", mood: "" };

  var swapping = null;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)");

  var card = function (drink, order) {
    var picture = drink.pic
      ? '<img class="pour-card__pic" src="' + drink.pic +
        '" alt="" width="320" height="330" loading="lazy" decoding="async">'
      : "";
    return '<li class="pour-card" style="--i:' + (order || 0) +
      '"><a class="pour-card__link" href="' +
      drink.href + '">' + picture +
      '<span class="pour-card__name">' + drink.name + "</span>" +
      '<span class="pour-card__price">' + drink.price +
      " <small>CZK</small></span></a></li>";
  };

  var show = function () {
    if (!picked.base && !picked.mood) {
      list.innerHTML = "";
      count.textContent = "";
      none.hidden = true;
      return;
    }
    var hits = drinks.filter(function (drink) {
      return (!picked.base || drink.base === picked.base) &&
             (!picked.mood || drink.mood === picked.mood);
    });
    /* Out, swap, in. Without the pause the old answer is replaced under the
       reader's eye mid-sentence; with it, the panel clears and fills. */
    var paint = function () {
      list.innerHTML = hits.slice(0, 6).map(function (drink, i) {
        return card(drink, i);
      }).join("");
      none.hidden = hits.length > 0;
      count.textContent = hits.length
        ? (hits.length === 1 ? "One drink" : hits.length + " drinks")
        : "";
      list.setAttribute("data-swapping", "false");
    };

    if (!list.children.length || still.matches) {
      paint();
      return;
    }
    list.setAttribute("data-swapping", "true");
    window.clearTimeout(swapping);
    swapping = window.setTimeout(paint, 160);
  };

  ["base", "mood"].forEach(function (kind) {
    root.querySelectorAll("[data-" + kind + "]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.getAttribute("data-" + kind);
        /* Pressing the answer you already gave takes it back off, which is
           how somebody widens the question again. */
        picked[kind] = picked[kind] === value ? "" : value;
        root.querySelectorAll("[data-" + kind + "]").forEach(function (other) {
          other.setAttribute(
            "aria-pressed",
            other.getAttribute("data-" + kind) === picked[kind] ? "true" : "false"
          );
        });
        show();
      });
    });
  });
})();
