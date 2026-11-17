/*!
 * SRU Buddy chat widget (v3.0.0)
 *
 * Add SRU Buddy to any web page (for example the SR University admission page) with ONE line,
 * just before </body>:
 *
 *   <script src="https://university-ai-companion.vercel.app/widget.js" defer></script>
 *
 * Optional settings on the same tag:
 *   data-position="left"            bubble on the left (default: right)
 *   data-color="#1d4ed8"            bubble colour
 *   data-label="Ask SRU Buddy"      text next to the bubble on wide screens ("" hides it)
 *   data-greeting="Hi! ..."         the small greeting shown once per visit ("" turns it off)
 *   data-open="true"                open the chat straight away
 *
 * From the page's own JavaScript: window.SRUBuddy.open(), .close(), .toggle().
 *
 * The chat itself is the same SRU Buddy app (same answers, same fee calculator, same knowledge),
 * opened in compact "widget" mode, so every improvement to the website reaches the widget too.
 * Nothing is loaded until the student shows interest (hover / focus / tap), so the host page
 * stays fast.
 */
(function () {
  "use strict";
  if (window.SRUBuddy && window.SRUBuddy.__loaded) return;

  var script =
    document.currentScript ||
    (function () {
      var all = document.getElementsByTagName("script");
      for (var i = all.length - 1; i >= 0; i--) {
        if (/widget\.js(\?|$)/.test(all[i].src)) return all[i];
      }
      return null;
    })();
  var base = script ? new URL(script.src, location.href).origin : location.origin;
  var opt = function (name, fallback) {
    var v = script && script.getAttribute("data-" + name);
    return v === null || v === undefined ? fallback : v;
  };
  var side = opt("position", "right") === "left" ? "left" : "right";
  var color = opt("color", "#dc2626");
  var label = opt("label", "Ask SRU Buddy");
  var greeting = opt("greeting", "Hi! Questions about admissions 2027-28? Ask me.");
  var startOpen = opt("open", "false") === "true";
  var appUrl = base + "/?mode=widget";

  var host = document.createElement("div");
  host.id = "sru-buddy-widget";
  host.style.cssText = "position:fixed;z-index:2147483000;bottom:0;" + side + ":0;width:0;height:0;";
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var css =
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}" +
    ".launcher{position:fixed;bottom:20px;" + side + ":20px;display:flex;align-items:center;gap:10px;" +
    "flex-direction:" + (side === "left" ? "row" : "row-reverse") + ";border:0;background:none;padding:0;cursor:pointer}" +
    ".launcher .dot{width:62px;height:62px;border-radius:50%;background:" + color + ";display:flex;align-items:center;" +
    "justify-content:center;box-shadow:0 8px 24px rgba(220,38,38,.4);transition:transform .15s ease;" +
    "animation:sruPulse 2.5s infinite}" +
    "@keyframes sruPulse{0%{box-shadow:0 0 0 0 rgba(220,38,38,.7),0 8px 24px rgba(0,0,0,.3)}70%{box-shadow:0 0 0 16px rgba(220,38,38,0),0 8px 24px rgba(0,0,0,.3)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0),0 8px 24px rgba(0,0,0,.3)}}" +
    ".launcher:hover .dot{transform:scale(1.06)}" +
    ".launcher .dot img{width:40px;height:40px;border-radius:50%;background:#fff;object-fit:contain;padding:2px}" +
    ".launcher .tag{background:#fff;color:#0f172a;font-size:14px;font-weight:600;padding:9px 14px;border-radius:999px;" +
    "box-shadow:0 4px 16px rgba(15,23,42,.16);white-space:nowrap}" +
    ".launcher:focus-visible{outline:none}.launcher:focus-visible .dot{outline:3px solid #f59e0b;outline-offset:3px}" +
    ".greet{position:fixed;bottom:92px;" + side + ":20px;max-width:260px;background:#fff;color:#0f172a;font-size:14px;" +
    "line-height:1.4;padding:12px 34px 12px 14px;border-radius:14px;box-shadow:0 8px 28px rgba(15,23,42,.2);cursor:pointer}" +
    ".greet button{position:absolute;top:6px;right:6px;border:0;background:none;font-size:16px;line-height:1;color:#64748b;" +
    "cursor:pointer;padding:4px}" +
    ".panel{position:fixed;bottom:92px;" + side + ":20px;width:400px;height:min(680px,calc(100vh - 116px));" +
    "background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 18px 48px rgba(15,23,42,.32);display:none}" +
    ".panel.open{display:block}.panel iframe{width:100%;height:100%;border:0;display:block}" +
    "@media (max-width:640px){.panel{left:0;right:0;bottom:0;top:0;width:100%;height:100%;border-radius:0}" +
    ".launcher .tag{display:none}.open-mobile .launcher,.open-mobile .greet{display:none}}" +
    "@media (prefers-reduced-motion:reduce){.launcher .dot{transition:none}}";

  var style = document.createElement("style");
  style.textContent = css;
  root.appendChild(style);

  var wrap = document.createElement("div");
  root.appendChild(wrap);

  var launcher = document.createElement("button");
  launcher.className = "launcher";
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open SRU Buddy, the SR University admissions assistant");
  launcher.setAttribute("aria-expanded", "false");
  launcher.setAttribute("aria-controls", "sru-buddy-panel");
  launcher.innerHTML =
    '<span class="dot"><img alt="" src="' + base + '/sru-crest.png"></span>' +
    (label ? '<span class="tag"></span>' : "");
  if (label) launcher.querySelector(".tag").textContent = label;
  wrap.appendChild(launcher);

  var panel = document.createElement("div");
  panel.className = "panel";
  panel.id = "sru-buddy-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "SRU Buddy chat");
  wrap.appendChild(panel);

  var frame = null;
  function load() {
    if (frame) return;
    frame = document.createElement("iframe");
    frame.title = "SRU Buddy, SR University admissions assistant";
    frame.src = appUrl;
    frame.allow = "microphone; clipboard-write";
    frame.setAttribute("loading", "eager");
    panel.appendChild(frame);
  }

  var greet = null;
  function hideGreeting() {
    if (greet && greet.parentNode) greet.parentNode.removeChild(greet);
    greet = null;
    try {
      sessionStorage.setItem("sru_buddy_greeted", "1");
    } catch (e) {
      /* storage blocked: fine */
    }
  }

  var isOpen = false;
  function open() {
    load();
    hideGreeting();
    isOpen = true;
    panel.classList.add("open");
    wrap.classList.add("open-mobile");
    launcher.setAttribute("aria-expanded", "true");
    launcher.setAttribute("aria-label", "Close SRU Buddy");
    setTimeout(function () {
      try {
        frame.focus();
      } catch (e) {
        /* ignore */
      }
    }, 50);
  }
  function close() {
    isOpen = false;
    panel.classList.remove("open");
    wrap.classList.remove("open-mobile");
    launcher.setAttribute("aria-expanded", "false");
    launcher.setAttribute("aria-label", "Open SRU Buddy, the SR University admissions assistant");
    launcher.focus();
  }
  function toggle() {
    if (isOpen) close();
    else open();
  }

  launcher.addEventListener("click", toggle);
  // Start loading as soon as the student shows interest: the chat is ready when they click.
  ["pointerenter", "focus", "touchstart"].forEach(function (ev) {
    launcher.addEventListener(ev, load, { passive: true, once: true });
  });
  document.addEventListener("keydown", function (e) {
    if (isOpen && e.key === "Escape") close();
  });
  window.addEventListener("message", function (e) {
    if (e.origin !== base || !e.data || e.data.type !== "sru-buddy:close") return;
    close();
  });

  function mount() {
    document.body.appendChild(host);
    var greeted = false;
    try {
      greeted = sessionStorage.getItem("sru_buddy_greeted") === "1";
    } catch (e) {
      greeted = false;
    }
    if (startOpen) {
      open();
    } else if (greeting && !greeted) {
      setTimeout(function () {
        if (isOpen) return;
        greet = document.createElement("div");
        greet.className = "greet";
        greet.setAttribute("role", "status");
        greet.innerHTML = '<span></span><button type="button" aria-label="Dismiss">×</button>';
        greet.querySelector("span").textContent = greeting;
        greet.querySelector("button").addEventListener("click", function (e) {
          e.stopPropagation();
          hideGreeting();
        });
        greet.addEventListener("click", open);
        wrap.appendChild(greet);
      }, 4000);
    }
  }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);

  window.SRUBuddy = { open: open, close: close, toggle: toggle, __loaded: true };
})();
