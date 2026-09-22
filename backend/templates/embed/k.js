/* Iguana Comedy site script: ticket checkout widgets + pageview tracking. Drop-in for Kintana's /_t/k.js. */
(function () {
  if (window.__iguanaK) return;
  window.__iguanaK = 1;
  var S = document.currentScript;
  var A = (S && S.getAttribute("data-api-base")) || "{{ backend_url }}";
  var T = (S && S.getAttribute("data-token")) || "";
  A = A.replace(/\/$/, "");

  function vid() {
    try {
      var v = localStorage.getItem("kintana_page_vid");
      if (!v) {
        v = Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem("kintana_page_vid", v);
      }
      return v;
    } catch (e) {
      return "";
    }
  }
  var V = vid();

  function post(path, body) {
    try {
      var data = JSON.stringify(body);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(A + path, new Blob([data], { type: "text/plain" }));
      } else {
        fetch(A + path, { method: "POST", body: data, keepalive: true, mode: "cors", credentials: "omit" });
      }
    } catch (e) {}
  }

  function cookie(name) {
    try {
      var hit = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
      return hit ? decodeURIComponent(hit[2]) : "";
    } catch (e) {
      return "";
    }
  }

  function utm() {
    var out = {};
    try {
      var params = new URLSearchParams(location.search);
      params.forEach(function (v, k) {
        if (k.indexOf("utm_") === 0 || k === "fbclid" || k === "gclid" || k === "ttclid") out[k.replace("utm_", "")] = v;
      });
      // Meta matches a server-side sale on these. The checkout iframe is on another origin and cannot read them,
      // so they are collected here and posted with the order; see backend/sales/ad_reporting.py.
      out.fbp = cookie("_fbp");
      // The pixel normally writes _fbc from fbclid, but it is the first thing an ad blocker stops. Rebuilding it
      // in Meta's own format keeps the click attributable when the pixel never ran.
      out.fbc = cookie("_fbc") || (params.get("fbclid") ? "fb.1." + Date.now() + "." + params.get("fbclid") : "");
      // The page the fan actually saw, rather than the iframe URL, so Meta reports results per landing page.
      out.pageUrl = location.href.slice(0, 200);
    } catch (e) {}
    for (var key in out) {
      if (out[key] === "") delete out[key];
    }
    return out;
  }

  function fanToken() {
    try {
      return (localStorage.getItem("kintana_access_token") || localStorage.getItem("kintana_fan_access_token") || "").trim();
    } catch (e) {
      return "";
    }
  }

  function track(name, props) {
    post("/api/ingest/event", { token: T, visitorKey: V, name: String(name || ""), props: props || null });
  }

  function bootWidgets() {
    window.addEventListener("message", function (e) {
      var d = e.data;
      if (!d || e.origin !== A) return;
      if (d.type === "kintana-embed-checkout-success" && typeof d.url === "string") {
        track("Purchase", { url: d.url });
        window.location.assign(d.url);
      }
      if (d.type === "kintana-fan-auth-request" && e.source) {
        e.source.postMessage({ type: "kintana-fan-auth", token: fanToken(), attribution: utm() }, A);
      }
    });

  // The sticky copy of the checkout button. It never decides anything: it shows whatever the checkout says it
  // is showing, and a press is forwarded back so the real form and the real validation run. It hides itself
  // while the real button is already on screen, so the two are never both visible saying the same thing.
  function stickyCta(iframe) {
    var bar = document.createElement("div");
    bar.setAttribute("data-kintana-cta-bar", "");
    bar.style.cssText = "position:fixed;left:0;right:0;bottom:0;z-index:2147483000;padding:10px 12px calc(10px + env(safe-area-inset-bottom));background:rgba(255,255,255,.94);backdrop-filter:blur(8px);border-top:1px solid rgba(0,0,0,.1);display:none";
    var button = document.createElement("button");
    button.type = "button";
    button.style.cssText = "display:flex;flex-direction:column;gap:2px;align-items:center;justify-content:center;width:100%;min-height:56px;border:0;border-radius:999px;background:#3f7d3e;color:#fff;font:600 1.05rem/1.2 inherit;cursor:pointer;padding:10px 20px";
    var main = document.createElement("span");
    var sub = document.createElement("span");
    sub.style.cssText = "font-size:.85rem;font-weight:500;opacity:.9";
    button.appendChild(main);
    button.appendChild(sub);
    bar.appendChild(button);
    document.body.appendChild(bar);

    var state = { visible: false, disabled: true };
    button.addEventListener("click", function () {
      if (state.disabled) return;
      iframe.contentWindow.postMessage({ type: "kintana-embed-submit" }, A);
    });

    function realButtonOnScreen() {
      // The iframe is as tall as its content, so the real button sits at its bottom edge.
      var box = iframe.getBoundingClientRect();
      return box.bottom <= (window.innerHeight || 0) + 8;
    }

    function paint() {
      var showIt = state.visible && !realButtonOnScreen();
      bar.style.display = showIt ? "block" : "none";
      button.disabled = !!state.disabled;
      button.style.opacity = state.disabled ? ".6" : "1";
    }
    window.addEventListener("scroll", paint, { passive: true });
    window.addEventListener("resize", paint);

    return {
      update: function (d) {
        state = d;
        main.textContent = d.main || "";
        sub.textContent = d.sub || "";
        sub.style.display = d.sub ? "" : "none";
        paint();
      },
    };
  }

    document.querySelectorAll("[data-kintana-widget]").forEach(function (el) {
      var raw = el.getAttribute("data-kintana-widget") || "";
      var id = raw.indexOf("event:") === 0 ? raw.slice(6) : "";
      if (!id || el.querySelector("iframe")) return;
      var iframe = document.createElement("iframe");
      // The page language rides along so the checkout, order page and email match the site the fan is on.
      var lang = el.getAttribute("data-kintana-locale") || document.documentElement.lang || "en";
      // A host page that prints the demand line itself turns the iframe's copy off, so it is not said twice.
      var demand = el.getAttribute("data-kintana-demand") === "off" ? "&demand=0" : "";
      iframe.src = A + "/embed/event/" + encodeURIComponent(id) + "?embedded=1&lang=" + encodeURIComponent(lang) + demand;
      iframe.title = el.getAttribute("aria-label") || "Ticket checkout";
      iframe.setAttribute("allow", "payment *");
      iframe.style.cssText = "width:100%;border:0;display:block;min-height:200px;background:transparent";
      el.innerHTML = "";
      el.appendChild(iframe);
      // A host page can ask for a copy of the checkout button that stays on screen, for the very common case
      // where the form is taller than the phone the ad was clicked on.
      var bar = el.getAttribute("data-kintana-sticky-cta") === "on" ? stickyCta(iframe) : null;
      window.addEventListener("message", function (e) {
        var d = e.data;
        if (!d || e.source !== iframe.contentWindow) return;
        if (d.type === "kintana-embed-height" && typeof d.height === "number") {
          iframe.style.height = Math.max(160, d.height | 0) + "px";
          iframe.style.minHeight = "0";
        }
        if (d.type === "kintana-embed-cta" && bar) bar.update(d);
      });
      iframe.addEventListener("load", function () {
        iframe.contentWindow.postMessage({ type: "kintana-fan-auth", token: fanToken(), attribution: utm() }, A);
      });
    });
  }

  function pageview() {
    var detail = { url: location.href, referrer: document.referrer || "", utm: utm() };
    try {
      window.dispatchEvent(new CustomEvent("kintana:pageview", { detail: detail }));
    } catch (e) {}
    post("/api/ingest/pageview", { token: T, visitorKey: V, url: detail.url, referrer: detail.referrer, utm: detail.utm });
  }

  window.Kintana = window.Kintana || { track: track, page: track, identify: function () {}, consent: function () {} };

  function boot() {
    bootWidgets();
    pageview();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
