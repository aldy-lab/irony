/* The owner's editor.
 *
 * No client library: a sign-in is one POST and a save is one PATCH, and
 * pulling in fifty kilobytes from somebody else's CDN to make two fetches
 * would also be the only third-party request the site makes.
 *
 * What protects this is not the page. The key below is publishable and is
 * meant to be read; every write is refused by the database unless the caller
 * is signed in and listed in irony.editors. An anonymous write answers 401,
 * and a check asserts that it still does.
 */

(function () {
  var root = document.querySelector("[data-admin]");
  if (!root) return;

  var store = (window.IVS && window.IVS.store) || {};
  if (!store.url) return;

  var KEY = "ivs.admin.session";
  var signIn = root.querySelector("[data-sign-in]");
  var work = root.querySelector("[data-work]");
  var rowsEl = root.querySelector("[data-rows]");
  var said = root.querySelector("[data-said]");
  var saved = root.querySelector("[data-saved]");
  var out = root.querySelector("[data-sign-out]");
  var search = root.querySelector("[data-admin-search]");

  var token = null;
  var drinks = [];
  var categories = [];

  try {
    token = window.sessionStorage.getItem(KEY);
  } catch (e) {
    /* a private window still has to be able to sign in */
  }

  var api = function (path, options) {
    options = options || {};
    var headers = {
      apikey: store.key,
      "Content-Type": "application/json",
      "Accept-Profile": store.schema,
      "Content-Profile": store.schema
    };
    if (token) headers.Authorization = "Bearer " + token;
    Object.keys(options.headers || {}).forEach(function (k) {
      headers[k] = options.headers[k];
    });
    return fetch(store.url + "/rest/v1/" + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    });
  };

  var tell = function (node, words, bad) {
    node.textContent = words;
    node.setAttribute("data-bad", bad ? "true" : "false");
    if (!bad && words) {
      window.setTimeout(function () {
        if (node.textContent === words) node.textContent = "";
      }, 2600);
    }
  };

  /* ------------------------------------------------------------- signing in */

  signIn.addEventListener("submit", function (event) {
    event.preventDefault();
    var form = new FormData(signIn);
    tell(said, "Signing in…");
    fetch(store.url + "/auth/v1/token?grant_type=password", {
      method: "POST",
      headers: { apikey: store.key, "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"), password: form.get("password")
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (body) {
        if (!body.access_token) {
          tell(said, body.error_description || body.msg ||
            "That did not work. Check the address and the password.", true);
          return;
        }
        token = body.access_token;
        try {
          window.sessionStorage.setItem(KEY, token);
        } catch (e) {}
        tell(said, "");
        open();
      })
      .catch(function () {
        tell(said, "Could not reach the menu store.", true);
      });
  });

  out.addEventListener("click", function () {
    token = null;
    try {
      window.sessionStorage.removeItem(KEY);
    } catch (e) {}
    work.hidden = true;
    out.hidden = true;
    signIn.hidden = false;
  });

  /* ---------------------------------------------------------------- the list */

  var row = function (drink) {
    var box = document.createElement("div");
    box.className = "edit";
    box.setAttribute("data-slug", drink.slug);
    box.setAttribute("data-hay",
      (drink.name + " " + drink.category).toLowerCase());
    box.innerHTML =
      '<div class="edit__top">' +
        '<input class="edit__name" value="" data-field="name" ' +
          'aria-label="Name">' +
        '<input class="edit__price" type="number" step="1" min="0" ' +
          'value="" data-field="price" aria-label="Price in CZK" inputmode="numeric">' +
        '<select class="edit__cat" data-field="category" aria-label="Shelf"></select>' +
      "</div>" +
      '<div class="edit__flags">' +
        '<label><input type="checkbox" data-field="listed"> On the menu</label>' +
        '<label><input type="checkbox" data-field="popular"> One we push</label>' +
      "</div>" +
      '<details class="edit__words"><summary>Words</summary>' +
        '<textarea data-field="text_en" rows="2" aria-label="English"></textarea>' +
        '<textarea data-field="text_cs" rows="2" aria-label="Czech"></textarea>' +
        '<textarea data-field="text_uk" rows="2" aria-label="Ukrainian"></textarea>' +
      "</details>";

    /* Values are set as properties, never interpolated into the markup: a
       drink called <b>Negroni</b> would otherwise be markup. */
    box.querySelector('[data-field="name"]').value = drink.name || "";
    box.querySelector('[data-field="price"]').value =
      drink.price === null || drink.price === undefined
        ? "" : Math.round(Number(drink.price));
    box.querySelector('[data-field="listed"]').checked = drink.listed !== false;
    box.querySelector('[data-field="popular"]').checked = !!drink.popular;
    ["text_en", "text_cs", "text_uk"].forEach(function (field) {
      box.querySelector('[data-field="' + field + '"]').value =
        drink[field] || "";
    });

    var select = box.querySelector('[data-field="category"]');
    categories.forEach(function (cat) {
      var option = document.createElement("option");
      option.value = cat.slug;
      option.textContent = cat.name;
      if (cat.slug === drink.category) option.selected = true;
      select.appendChild(option);
    });

    /* One field at a time. Sending the whole row on every edit is how a
       field somebody never touched gets written back as empty. */
    box.querySelectorAll("[data-field]").forEach(function (input) {
      input.addEventListener("change", function () {
        var field = input.getAttribute("data-field");
        var value;
        if (input.type === "checkbox") value = input.checked;
        else if (field === "price") value = input.value === "" ? null : Number(input.value);
        else value = input.value === "" ? null : input.value;

        var patch = {};
        patch[field] = value;
        api("drinks?slug=eq." + encodeURIComponent(drink.slug), {
          method: "PATCH",
          body: patch,
          headers: { Prefer: "return=minimal" }
        }).then(function (r) {
          if (r.ok) {
            tell(saved, "Saved");
            box.setAttribute("data-dirty", "false");
          } else {
            tell(saved, "Not saved (" + r.status + ")", true);
            box.setAttribute("data-dirty", "true");
          }
        }).catch(function () {
          tell(saved, "Not saved — no connection", true);
          box.setAttribute("data-dirty", "true");
        });
      });
    });
    return box;
  };

  var paint = function () {
    rowsEl.innerHTML = "";
    drinks.forEach(function (drink) { rowsEl.appendChild(row(drink)); });
  };

  var open = function () {
    signIn.hidden = true;
    work.hidden = false;
    out.hidden = false;
    Promise.all([
      api("categories?select=slug,name,position&order=position").then(function (r) { return r.json(); }),
      api("drinks?select=*&order=category,position").then(function (r) { return r.json(); })
    ]).then(function (both) {
      categories = both[0] || [];
      drinks = both[1] || [];
      paint();
      tell(saved, drinks.length + " drinks");
    });
  };

  if (search) {
    search.addEventListener("input", function () {
      var term = search.value.trim().toLowerCase();
      rowsEl.querySelectorAll(".edit").forEach(function (box) {
        box.hidden = !!term &&
          box.getAttribute("data-hay").indexOf(term) === -1;
      });
    });
  }

  /* ------------------------------------------------- starting again */

  var reseed = root.querySelector("[data-reseed]");
  var reseeded = root.querySelector("[data-reseeded]");
  if (reseed) {
    reseed.addEventListener("click", function () {
      tell(reseeded, "Reading the published list…");
      fetch("../data/menu.json")
        .then(function (r) { return r.json(); })
        .then(function (menu) {
          var rows = menu.products.map(function (p, i) {
            var t = p.text || {};
            return {
              slug: p.slug, name: p.name, category: p.category,
              price: p.price === undefined ? null : p.price,
              popular: !!p.popular, listed: true,
              text_en: t.en || null, text_cs: t.cs || null, text_uk: t.uk || null,
              position: i
            };
          });
          return api("drinks?on_conflict=slug", {
            method: "POST",
            body: rows,
            headers: { Prefer: "resolution=merge-duplicates,return=minimal" }
          });
        })
        .then(function (r) {
          if (!r.ok) return r.text().then(function (t) { throw new Error(t); });
          tell(reseeded, "Written. Reloading.");
          open();
        })
        .catch(function (e) {
          tell(reseeded, "Could not write: " + String(e).slice(0, 120), true);
        });
    });
  }

  if (token) open();
})();
