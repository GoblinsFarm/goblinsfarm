/* Wiki search.
 *
 * 369 pages is small enough that the whole index is one 60KB fetch and the
 * matching is a linear scan -- no library, no server, no network call per
 * keystroke. The index is only fetched when someone first touches the field,
 * so a reader who never searches never pays for it.
 *
 * Scoring is deliberately blunt and predictable: an exact name beats a name
 * that starts with the query, which beats a word inside the name, which beats
 * a hit in the summary. Typing "drag" should put Dragon first and it does.
 */
(function () {
  "use strict";

  var box = document.querySelector(".searchbox");
  if (!box) return;

  var input = box.querySelector("input");
  var panel = box.querySelector(".results");
  var rel = box.dataset.rel || "";
  var index = null;
  var loading = null;
  var active = -1;
  var rows = [];

  function load() {
    if (loading) return loading;
    loading = fetch(box.dataset.index)
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (data) { index = data; return data; })
      .catch(function () { index = []; return []; });
    return loading;
  }

  function score(rec, q) {
    var name = rec.t.toLowerCase();
    if (name === q) return 0;
    if (name.indexOf(q) === 0) return 1;
    // A word inside the name: "dragon" should find "Inferno Dragon".
    if (name.indexOf(" " + q) > -1) return 2;
    if (name.indexOf(q) > -1) return 3;
    if ((rec.b || "").toLowerCase().indexOf(q) > -1) return 6;
    return -1;
  }

  function search(q) {
    var out = [];
    for (var i = 0; i < index.length; i++) {
      var s = score(index[i], q);
      if (s >= 0) out.push([s, index[i].t.length, index[i]]);
    }
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out.slice(0, 8).map(function (r) { return r[2]; });
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function render(hits, q) {
    if (!hits.length) {
      panel.innerHTML =
        '<p class="noresult">Nothing matches &ldquo;' + esc(q) + '&rdquo;.</p>';
      show();
      return;
    }
    panel.innerHTML = hits
      .map(function (h, i) {
        var art = h.i
          ? '<span class="plaque sm"><img src="' + rel + esc(h.i) +
            '" alt="" width="40" height="40" loading="lazy"></span>'
          : '<span class="plaque sm empty"></span>';
        return (
          '<a class="hit tone-' + esc(h.o) + '" role="option" id="hit' + i +
          '" aria-selected="false" href="' + rel + esc(h.u).replace(/^\//, "") + '">' +
          art +
          '<span class="hit-text"><b>' + esc(h.t) + "</b>" +
          '<span class="hit-sec">' + esc(h.s) + "</span></span></a>"
        );
      })
      .join("");
    rows = Array.prototype.slice.call(panel.querySelectorAll(".hit"));
    active = -1;
    show();
  }

  function show() {
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function hide() {
    panel.hidden = true;
    input.setAttribute("aria-expanded", "false");
    active = -1;
    rows = [];
  }

  function highlight(n) {
    rows.forEach(function (r, i) {
      var on = i === n;
      r.classList.toggle("on", on);
      r.setAttribute("aria-selected", on ? "true" : "false");
    });
    active = n;
    input.setAttribute("aria-activedescendant", n > -1 ? "hit" + n : "");
  }

  var timer;
  function onInput() {
    clearTimeout(timer);
    var q = input.value.trim().toLowerCase();
    if (q.length < 2) { hide(); return; }
    timer = setTimeout(function () {
      load().then(function () { render(search(q), q); });
    }, 90);
  }

  input.addEventListener("focus", load);
  input.addEventListener("input", onInput);

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { hide(); input.blur(); return; }
    if (!rows.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlight((active + 1) % rows.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight((active - 1 + rows.length) % rows.length);
    } else if (e.key === "Enter" && active > -1) {
      e.preventDefault();
      rows[active].click();
    }
  });

  document.addEventListener("click", function (e) {
    if (!box.contains(e.target)) hide();
  });

  // "/" focuses the field, the way every reference site a player already uses
  // behaves -- but not while they are typing into something else.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
})();
