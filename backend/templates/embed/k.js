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

  function utm() {
    var out = {};
    try {
      new URLSearchParams(location.search).forEach(function (v, k) {
        if (k.indexOf("utm_") === 0 || k === "fbclid" || k === "gclid" || k === "ttclid") out[k.replace("utm_", "")] = v;
      });
    } catch (e) {}
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
      iframe.src = A + "/embed/event/" + encodeURIComponent(id) + "?embedded=1";
      iframe.title = "Ticket checkout";
      iframe.setAttribute("allow", "payment *");
      iframe.style.cssText = "width:100%;border:0;display:block;min-height:420px;background:transparent";
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
