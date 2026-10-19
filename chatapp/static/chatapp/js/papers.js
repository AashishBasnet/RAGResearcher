/**
 * Papers list: open a paper in the PDF reader dialog, and confirm before deleting.
 */
(function () {
  "use strict";
  
  /* ---------- Delete confirmation ---------- */
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
})();
