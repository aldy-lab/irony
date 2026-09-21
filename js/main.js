/* =========================================================================
   Irony vs. Satyr

   Product and configuration data are written into each page by build.py as
   window.IVS. Nothing here invents a URL: if a value is blank in
   data/site.json the element that would have used it is removed from the DOM
   instead of falling back to a dead link.
   ========================================================================= */

(function () {
  "use strict";

  var IVS = window.IVS || {};
  var PRODUCTS = IVS.products || {};
  var SHOP = IVS.commerce || {};
  var CART_KEY = "ivs.cart.v1";
  var AGE_KEY = "ivs.age.v1";

  /* ---------------------------------------------------------------------
     Storage. Every read and write is guarded: in a private window, with site
     data blocked, or during a thumbnail capture these throw, and the page
     still has to render.
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
      return true;
    } catch (e) {
      return false;
    }
  }

  /* ---------------------------------------------------------------------
     Money
     --------------------------------------------------------------------- */

  // Must match money() in build.py: a thin space, the Czech convention, so a
  // price rendered here reads identically to one rendered into the HTML.
  function money(amount) {
    return String(Math.round(amount)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  /* ---------------------------------------------------------------------
     Cart. Shape is { slug: qty }. Unknown slugs are dropped on read so a
     renamed or removed product cannot wedge somebody's cart forever.
     --------------------------------------------------------------------- */

  var cart = {
    all: function () {
      var stored = read(CART_KEY, {});
      var clean = {};
      Object.keys(stored).forEach(function (slug) {
        var qty = parseInt(stored[slug], 10);
        if (PRODUCTS[slug] && qty > 0) clean[slug] = Math.min(qty, 99);
      });
      return clean;
    },

    lines: function () {
      var items = cart.all();
      return Object.keys(items).map(function (slug) {
        var p = PRODUCTS[slug];
        return {
          slug: slug,
          qty: items[slug],
          product: p,
          total: p.price * items[slug],
        };
      });
    },

    count: function () {
      var items = cart.all();
      return Object.keys(items).reduce(function (n, slug) {
        return n + items[slug];
      }, 0);
    },

    subtotal: function () {
      return cart.lines().reduce(function (sum, line) {
        return sum + line.total;
      }, 0);
    },

    delivery: function () {
      var sub = cart.subtotal();
      if (!sub) return 0;
      var free = SHOP.free_delivery_over;
      if (free && sub >= free) return 0;
      return SHOP.delivery_flat || 0;
    },

    set: function (slug, qty) {
      var items = cart.all();
      qty = Math.max(0, Math.min(parseInt(qty, 10) || 0, 99));
      if (qty === 0) delete items[slug];
      else items[slug] = qty;
      write(CART_KEY, items);
      sync();
      return qty;
    },

    add: function (slug, qty) {
      var items = cart.all();
      return cart.set(slug, (items[slug] || 0) + (qty || 1));
    },

    clear: function () {
      write(CART_KEY, {});
      sync();
    },
  };

  /* ---------------------------------------------------------------------
     Header badge
     --------------------------------------------------------------------- */

  function syncBadge() {
    var n = cart.count();
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      el.textContent = n;
      // An empty cart shows nothing rather than a zero.
      el.hidden = n === 0;
    });
  }

  function sync() {
    syncBadge();
    renderCart();
  }

  /* ---------------------------------------------------------------------
     Toast
     --------------------------------------------------------------------- */

  var toastTimer = null;

  function toast(message, linkText, linkHref) {
    var el = document.querySelector("[data-toast]");
    if (!el) return;
    el.innerHTML = "";
    var span = document.createElement("span");
    span.textContent = message;
    el.appendChild(span);
    if (linkText && linkHref) {
      var a = document.createElement("a");
      a.href = linkHref;
      a.textContent = linkText;
      el.appendChild(a);
    }
    el.setAttribute("data-visible", "true");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      el.removeAttribute("data-visible");
    }, 3600);
  }

  /* ---------------------------------------------------------------------
     Add to cart
     --------------------------------------------------------------------- */

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-add]");
    if (!button) return;
    event.preventDefault();

    var slug = button.getAttribute("data-add");
    var product = PRODUCTS[slug];
    if (!product) return;

    var qtyInput = document.querySelector("[data-qty-input]");
    var qty = button.hasAttribute("data-use-qty") && qtyInput
      ? parseInt(qtyInput.value, 10) || 1
      : 1;

    cart.add(slug, qty);

    var label = button.getAttribute("data-label") || button.textContent;
    button.setAttribute("data-state", "added");
    button.textContent = "Added";
    window.setTimeout(function () {
      button.removeAttribute("data-state");
      button.textContent = label;
    }, 1400);

    toast(product.name + " added", "View cart", IVS.base + "cart.html");
  });

  /* ---------------------------------------------------------------------
     Quantity stepper on the product page
     --------------------------------------------------------------------- */

  document.addEventListener("click", function (event) {
    var step = event.target.closest("[data-step]");
    if (!step) return;
    var input = document.querySelector("[data-qty-input]");
    if (!input) return;
    var next = (parseInt(input.value, 10) || 1) + parseInt(step.getAttribute("data-step"), 10);
    input.value = Math.max(1, Math.min(next, 99));
  });

  /* ---------------------------------------------------------------------
     Cart page
     --------------------------------------------------------------------- */

  function renderCart() {
    var root = document.querySelector("[data-cart-page]");
    if (!root) return;

    var lines = cart.lines();
    var listWrap = root.querySelector("[data-cart-filled]");
    var emptyWrap = root.querySelector("[data-cart-empty]");

    if (!lines.length) {
      if (listWrap) listWrap.hidden = true;
      if (emptyWrap) emptyWrap.hidden = false;
      return;
    }

    if (listWrap) listWrap.hidden = false;
    if (emptyWrap) emptyWrap.hidden = true;

    var list = root.querySelector("[data-line-items]");
    list.innerHTML = "";

    lines.forEach(function (line) {
      var li = document.createElement("li");
      li.className = "line-item";

      var main = document.createElement("div");
      var name = document.createElement("div");
      name.className = "line-item__name";
      var link = document.createElement("a");
      link.href = IVS.base + "shop/" + line.slug + ".html";
      link.textContent = line.product.name;
      name.appendChild(link);
      var meta = document.createElement("div");
      meta.className = "line-item__meta";
      meta.textContent =
        line.product.volume + " ml · " + line.product.abv + "% · " + money(line.product.price) + " each";
      main.appendChild(name);
      main.appendChild(meta);

      var controls = document.createElement("div");
      controls.className = "line-item__controls";

      var qty = document.createElement("div");
      qty.className = "qty";
      qty.innerHTML =
        '<button type="button" aria-label="One fewer">-</button>' +
        '<input type="number" inputmode="numeric" min="1" max="99" aria-label="Quantity">' +
        '<button type="button" aria-label="One more">+</button>';
      var input = qty.querySelector("input");
      input.value = line.qty;

      qty.querySelectorAll("button")[0].addEventListener("click", function () {
        cart.set(line.slug, line.qty - 1);
      });
      qty.querySelectorAll("button")[1].addEventListener("click", function () {
        cart.set(line.slug, line.qty + 1);
      });
      input.addEventListener("change", function () {
        cart.set(line.slug, input.value);
      });

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "link-quiet";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () {
        cart.set(line.slug, 0);
      });

      controls.appendChild(qty);
      controls.appendChild(remove);

      var total = document.createElement("div");
      total.className = "price";
      total.textContent = money(line.total) + " ";
      var cur = document.createElement("small");
      cur.textContent = IVS.currency;
      total.appendChild(cur);

      li.appendChild(main);
      li.appendChild(controls);
      li.appendChild(total);
      list.appendChild(li);
    });

    var sub = cart.subtotal();
    var ship = cart.delivery();
    setText(root, "[data-subtotal]", money(sub) + " " + IVS.currency);
    setText(
      root,
      "[data-delivery]",
      ship === 0 ? "Included" : money(ship) + " " + IVS.currency
    );
    setText(root, "[data-total]", money(sub + ship) + " " + IVS.currency);

    var away = root.querySelector("[data-free-delivery]");
    if (away) {
      var threshold = SHOP.free_delivery_over;
      if (threshold && sub < threshold) {
        away.hidden = false;
        away.textContent =
          money(threshold - sub) + " " + IVS.currency + " more and delivery is on us.";
      } else {
        away.hidden = true;
      }
    }
  }

  function setText(root, selector, value) {
    var el = root.querySelector(selector);
    if (el) el.textContent = value;
  }

  /* ---------------------------------------------------------------------
     Checkout. The cart is sent as an order request to the configured form
     endpoint. With no endpoint configured the form is not rendered at all
     and the page says how to order instead, so no button ever promises a
     payment that cannot happen.
     --------------------------------------------------------------------- */

  var checkoutForm = document.querySelector("[data-checkout-form]");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", function (event) {
      event.preventDefault();

      var lines = cart.lines();
      if (!lines.length) return;

      var status = checkoutForm.querySelector("[data-checkout-status]");
      var submit = checkoutForm.querySelector("[type=submit]");
      var data = new FormData(checkoutForm);

      data.append(
        "order",
        lines
          .map(function (l) {
            return l.qty + " x " + l.product.name + " (" + l.product.volume + " ml) — " +
              money(l.total) + " " + IVS.currency;
          })
          .join("\n")
      );
      data.append("subtotal", money(cart.subtotal()) + " " + IVS.currency);
      data.append("delivery", money(cart.delivery()) + " " + IVS.currency);
      data.append("total", money(cart.subtotal() + cart.delivery()) + " " + IVS.currency);

      submit.setAttribute("aria-disabled", "true");
      if (status) status.textContent = "Sending your order…";

      window
        .fetch(checkoutForm.action, {
          method: "POST",
          body: data,
          headers: { Accept: "application/json" },
        })
        .then(function (response) {
          if (!response.ok) throw new Error("Request failed: " + response.status);
          cart.clear();
          checkoutForm.hidden = true;
          var done = document.querySelector("[data-checkout-done]");
          if (done) done.hidden = false;
        })
        .catch(function () {
          submit.removeAttribute("aria-disabled");
          if (status) {
            status.textContent =
              "That did not send. Please try again, or contact us directly and we will take the order by hand.";
          }
        });
    });
  }

  /* ---------------------------------------------------------------------
     Shop filtering. The grid is rendered statically by build.py so it is
     crawlable and works without JavaScript; this only hides and shows.
     --------------------------------------------------------------------- */

  var shop = document.querySelector("[data-shop]");
  if (shop) {
    var chips = shop.querySelectorAll("[data-filter]");
    var cards = shop.querySelectorAll("[data-category]");
    var countEl = shop.querySelector("[data-result-count]");
    var emptyEl = shop.querySelector("[data-no-results]");

    var apply = function (value) {
      var shown = 0;
      cards.forEach(function (card) {
        var match = value === "all" || card.getAttribute("data-category") === value;
        card.hidden = !match;
        if (match) shown += 1;
      });
      chips.forEach(function (chip) {
        chip.setAttribute(
          "aria-pressed",
          chip.getAttribute("data-filter") === value ? "true" : "false"
        );
      });
      if (countEl) {
        countEl.textContent = shown + (shown === 1 ? " bottle" : " bottles");
      }
      if (emptyEl) emptyEl.hidden = shown !== 0;

      var url = new URL(window.location.href);
      if (value === "all") url.searchParams.delete("c");
      else url.searchParams.set("c", value);
      window.history.replaceState({}, "", url);
    };

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        apply(chip.getAttribute("data-filter"));
      });
    });

    var sort = shop.querySelector("[data-sort]");
    if (sort) {
      sort.addEventListener("change", function () {
        var grid = shop.querySelector("[data-grid]");
        var items = Array.prototype.slice.call(grid.children);
        var mode = sort.value;
        items.sort(function (a, b) {
          if (mode === "price-asc") return num(a, "price") - num(b, "price");
          if (mode === "price-desc") return num(b, "price") - num(a, "price");
          if (mode === "name") {
            return a.getAttribute("data-name").localeCompare(b.getAttribute("data-name"));
          }
          return num(a, "order") - num(b, "order");
        });
        items.forEach(function (item) {
          grid.appendChild(item);
        });
      });
    }

    var initial = new URL(window.location.href).searchParams.get("c");
    apply(initial && document.querySelector('[data-filter="' + CSS.escape(initial) + '"]') ? initial : "all");
  }

  function num(el, attr) {
    return parseFloat(el.getAttribute("data-" + attr)) || 0;
  }

  /* ---------------------------------------------------------------------
     Age gate. The page is hidden only once JavaScript confirms the gate is
     needed, so a crawler or a no-script visitor is never shown a blank page.
     --------------------------------------------------------------------- */

  var gate = document.querySelector("[data-age-gate]");
  if (gate) {
    var confirmed = read(AGE_KEY, false) === true;
    if (!confirmed) {
      document.body.setAttribute("data-gated", "true");
      gate.hidden = false;

      gate.querySelector("[data-age-yes]").addEventListener("click", function () {
        write(AGE_KEY, true);
        document.body.removeAttribute("data-gated");
        gate.hidden = true;
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
     The other colourway. Type the second half of the name.
     --------------------------------------------------------------------- */

  var typed = "";
  window.addEventListener("keydown", function (event) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    var tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (event.key.length !== 1) return;

    typed = (typed + event.key.toLowerCase()).slice(-5);
    if (typed !== "satyr") return;

    var on = document.body.getAttribute("data-colourway") === "satyr";
    if (on) document.body.removeAttribute("data-colourway");
    else document.body.setAttribute("data-colourway", "satyr");
    typed = "";
  });

  /* --------------------------------------------------------------------- */

  sync();
})();
