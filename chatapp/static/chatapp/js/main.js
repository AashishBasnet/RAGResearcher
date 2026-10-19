/**
 * Main UI behaviour: mobile sidebar and toast messages.
 * The chat conversation is intentionally static for now.
 */
(function () {
  "use strict";

  var body = document.body;

  /* ---------- Mobile sidebar ---------- */
  var menuButton = document.querySelector("[data-sidebar-toggle]");
  var backdrop = document.querySelector("[data-sidebar-backdrop]");

  function setSidebar(open) {
    body.classList.toggle("sidebar-open", open);
    if (menuButton) {
      menuButton.setAttribute("aria-expanded", String(open));
    }
  }

  if (menuButton) {
    menuButton.addEventListener("click", function () {
      setSidebar(!body.classList.contains("sidebar-open"));
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", function () {
      setSidebar(false);
    });
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") setSidebar(false);
  });

  /* ---------- Toast ---------- */
  var toast = document.querySelector("[data-toast]");
  var toastTimer;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 3000);
  }

  /* ---------- Flash messages from Django ---------- */
  var flash = document.querySelector("[data-flash]");
  if (flash && flash.textContent.trim()) {
    showToast(flash.textContent.trim());
  }
})();
