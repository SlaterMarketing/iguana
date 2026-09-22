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
      window.addEventListener("message", function (e) {
        var d = e.data;
        if (d && d.type === "kintana-embed-height" && typeof d.height === "number" && e.source === iframe.contentWindow) {
          iframe.style.height = Math.max(160, d.height | 0) + "px";
          iframe.style.minHeight = "0";
        }
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
