(function () {
  var script = document.currentScript;
  if (!script) { return; }
  var agentId = script.getAttribute("data-agent-id") || "";
  var tenantId = script.getAttribute("data-tenant-id") || "";
  if (!tenantId) {
    console.warn("[Consenso+] data-tenant-id em falta no <script>");
    return;
  }
  var origin = new URL(script.src, document.baseURI).origin;
  var api = origin + "/api";
  var iframeSrc = origin + "/api/widget/" + tenantId +
    "?api=" + encodeURIComponent(api) +
    "&tenant=" + tenantId +
    (agentId ? "&agent=" + agentId : "");

  // Inject styles
  var css = document.createElement("style");
  css.textContent = '' +
    '#cp-launcher{position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:#0069FE;color:#fff;border:0;cursor:pointer;box-shadow:0 8px 24px rgba(0,105,254,.35);z-index:2147483646;display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s}' +
    '#cp-launcher:hover{transform:scale(1.06);box-shadow:0 12px 32px rgba(0,105,254,.5)}' +
    '#cp-launcher svg{width:26px;height:26px}' +
    '#cp-frame{position:fixed;bottom:92px;right:20px;width:420px;height:620px;max-width:calc(100vw - 40px);max-height:calc(100vh - 120px);border:0;border-radius:16px;box-shadow:0 20px 60px rgba(11,19,36,.22);z-index:2147483645;background:#fff;transform:translateY(16px) scale(.98);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s}' +
    '#cp-frame.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}' +
    '#cp-badge{position:absolute;top:-4px;right:-4px;width:18px;height:18px;background:#22c55e;border:2px solid #fff;border-radius:50%;animation:cpP 1.5s infinite}' +
    '@keyframes cpP{0%,100%{opacity:1}50%{opacity:.5}}' +
    '@media(max-width:520px){#cp-frame{width:calc(100vw - 20px);right:10px;left:10px;bottom:82px}}';
  document.head.appendChild(css);

  // Iframe
  var frame = document.createElement("iframe");
  frame.id = "cp-frame";
  frame.title = "Consenso+ Chat";
  frame.src = iframeSrc;
  frame.allow = "clipboard-write";
  document.body.appendChild(frame);

  // Launcher button
  var btn = document.createElement("button");
  btn.id = "cp-launcher";
  btn.setAttribute("aria-label", "Abrir chat");
  btn.innerHTML = '' +
    '<svg viewBox="0 0 24 24" fill="none">' +
    '<path d="M4 6a3 3 0 013-3h10a3 3 0 013 3v8a3 3 0 01-3 3H9l-4 3v-3H7a3 3 0 01-3-3V6z" fill="#fff"/>' +
    '</svg>' +
    '<span id="cp-badge"></span>';
  btn.addEventListener("click", function () {
    var open = frame.classList.toggle("open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      var badge = document.getElementById("cp-badge");
      if (badge) badge.style.display = "none";
    }
  });
  document.body.appendChild(btn);
})();
