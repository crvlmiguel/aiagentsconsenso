(function () {
  try {
    var script = document.currentScript;
    if (!script) {
      // Fallback: find our script by src
      var scripts = document.getElementsByTagName("script");
      for (var i = scripts.length - 1; i >= 0; i--) {
        if (scripts[i].src && /\/widget\.js(\?|$)/.test(scripts[i].src)) { script = scripts[i]; break; }
      }
    }
    if (!script) { console.warn("[Consenso+] não foi possível localizar o <script>"); return; }
    if (window.__cpWidgetLoaded) return; // prevent double-injection
    window.__cpWidgetLoaded = true;

    var agentId = script.getAttribute("data-agent-id") || "";
    var tenantId = script.getAttribute("data-tenant-id") || "";
    if (!tenantId) {
      console.error("[Consenso+] data-tenant-id em falta no <script src='.../api/widget.js'>");
      return;
    }

    // Resolve origin from script src (works cross-domain)
    var origin;
    try { origin = new URL(script.src, document.baseURI).origin; }
    catch (e) { origin = location.origin; }
    var api = origin + "/api";
    var iframeSrc = origin + "/api/widget/" + encodeURIComponent(tenantId) +
      "?api=" + encodeURIComponent(api) +
      "&tenant=" + encodeURIComponent(tenantId) +
      (agentId ? "&agent=" + encodeURIComponent(agentId) : "");

    // Inject CSS (very high z-index, always visible)
    var css = document.createElement("style");
    css.id = "cp-widget-style";
    css.textContent = '' +
      '#cp-launcher{position:fixed!important;bottom:20px!important;right:20px!important;width:60px!important;height:60px!important;border-radius:50%!important;background:#0069FE!important;color:#fff!important;border:0!important;cursor:pointer!important;box-shadow:0 8px 24px rgba(0,105,254,.35)!important;z-index:2147483646!important;display:flex!important;align-items:center!important;justify-content:center!important;transition:transform .2s,box-shadow .2s!important;padding:0!important;margin:0!important;font-family:inherit!important}' +
      '#cp-launcher:hover{transform:scale(1.06)!important;box-shadow:0 12px 32px rgba(0,105,254,.5)!important}' +
      '#cp-launcher svg{width:26px;height:26px;display:block}' +
      '#cp-frame{position:fixed!important;bottom:92px!important;right:20px!important;width:420px!important;height:620px!important;max-width:calc(100vw - 40px)!important;max-height:calc(100vh - 120px)!important;border:0!important;border-radius:16px!important;box-shadow:0 20px 60px rgba(11,19,36,.22)!important;z-index:2147483645!important;background:#fff!important;transform:translateY(16px) scale(.98);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;display:none}' +
      '#cp-frame.cp-open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto;display:block}' +
      '#cp-badge{position:absolute;top:-4px;right:-4px;width:18px;height:18px;background:#22c55e;border:2px solid #fff;border-radius:50%;animation:cpP 1.5s infinite}' +
      '#cp-err{position:fixed!important;bottom:92px!important;right:20px!important;width:300px!important;padding:14px 16px!important;background:#fff!important;border:1px solid #FCA5A5!important;border-radius:12px!important;box-shadow:0 20px 60px rgba(11,19,36,.22)!important;z-index:2147483645!important;font-family:system-ui,sans-serif!important;font-size:13px!important;color:#991B1B!important;display:none}' +
      '#cp-err.cp-open{display:block}' +
      '@keyframes cpP{0%,100%{opacity:1}50%{opacity:.5}}' +
      '@media(max-width:520px){' +
        '#cp-launcher{bottom:16px!important;right:16px!important;width:56px!important;height:56px!important}' +
        '#cp-frame{width:100vw!important;height:100%!important;max-width:100vw!important;max-height:100%!important;bottom:0!important;right:0!important;left:0!important;top:0!important;border-radius:0!important}' +
        '#cp-frame.cp-open~#cp-launcher,body:has(#cp-frame.cp-open) #cp-launcher{display:none!important}' +
      '}';
    document.head.appendChild(css);

    function mountIcon() {
      if (document.getElementById("cp-launcher")) return;

      // Launcher button — ALWAYS injected first, regardless of iframe status
      var btn = document.createElement("button");
      btn.id = "cp-launcher";
      btn.type = "button";
      btn.setAttribute("aria-label", "Abrir chat");
      btn.innerHTML = '' +
        '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
        '<path d="M4 6a3 3 0 013-3h10a3 3 0 013 3v8a3 3 0 01-3 3H9l-4 3v-3H7a3 3 0 01-3-3V6z" fill="#fff"/>' +
        '</svg>' +
        '<span id="cp-badge"></span>';

      // Iframe (hidden until first click — lazy)
      var frame = null;
      var errBox = null;

      function openIframe() {
        if (frame) {
          frame.classList.toggle("cp-open");
          return;
        }
        frame = document.createElement("iframe");
        frame.id = "cp-frame";
        frame.title = "Consenso+ Chat";
        frame.src = iframeSrc;
        frame.allow = "clipboard-write";
        frame.onerror = showError;
        document.body.appendChild(frame);
        // open with small delay for CSS transition
        requestAnimationFrame(function () { frame.classList.add("cp-open"); });
        // Fallback if iframe fails to load within 8s
        var loaded = false;
        frame.onload = function () { loaded = true; };
        setTimeout(function () {
          if (!loaded) { showError(); }
        }, 8000);
      }

      function showError() {
        if (errBox) { errBox.classList.add("cp-open"); return; }
        errBox = document.createElement("div");
        errBox.id = "cp-err";
        errBox.innerHTML = '<div style="font-weight:700;margin-bottom:4px;color:#0B1324">Erro de ligação</div>' +
          '<div style="color:#5B6B82;font-size:12px">Não foi possível carregar o chat agora. Tente mais tarde.</div>';
        document.body.appendChild(errBox);
        errBox.classList.add("cp-open");
      }

      btn.addEventListener("click", function () {
        if (!frame) {
          openIframe();
          var badge = document.getElementById("cp-badge");
          if (badge) badge.style.display = "none";
        } else {
          frame.classList.toggle("cp-open");
        }
      });
      document.body.appendChild(btn);

      // Expose minimal API for host pages
      window.ConsensoPlus = {
        open: function () { if (!frame) openIframe(); else frame.classList.add("cp-open"); },
        close: function () { if (frame) frame.classList.remove("cp-open"); },
        tenantId: tenantId, agentId: agentId,
      };

      // Listen for close events from the iframe (mobile fullscreen "×" button)
      window.addEventListener("message", function (ev) {
        if (ev && ev.data && ev.data.type === "cp-close" && frame) {
          frame.classList.remove("cp-open");
        }
      });
    }

    // Ensure DOM is ready before mounting
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountIcon);
    } else {
      mountIcon();
    }
  } catch (err) {
    console.error("[Consenso+] falha crítica:", err);
  }
})();
