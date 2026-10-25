/**
 * Projects page: new/rename dialogs, the card menu, delete confirmation, toast messages.
 */
(function () {
  "use strict";

  /* ---------- Toast (messages from Django) ---------- */
  var toast = document.querySelector("[data-toast]");
  var flash = document.querySelector("[data-flash]");
  if (toast && flash && flash.textContent.trim()) {
    toast.textContent = flash.textContent.trim();
    toast.classList.add("is-visible");
    window.setTimeout(function () { toast.classList.remove("is-visible"); }, 3500);
  }

  /* ---------- Dialogs ---------- */
  var createDialog = document.querySelector('[data-dialog="create"]');
  var renameDialog = document.querySelector('[data-dialog="rename"]');

  function openDialog(dialog) {
    if (!dialog || typeof dialog.showModal !== "function") return;
    dialog.showModal();
    var field = dialog.querySelector("input[name='name']");
    if (field) {
      field.focus();
      field.select();
    }
  }

  document.querySelectorAll("[data-dialog]").forEach(function (dialog) {
    dialog.querySelectorAll("[data-dialog-close]").forEach(function (button) {
      button.addEventListener("click", function () { dialog.close(); });
    });
    // Clicking the backdrop (the dialog element itself) closes it.
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
  });

  document.querySelectorAll("[data-project-new]").forEach(function (button) {
    button.addEventListener("click", function () {
      var field = createDialog && createDialog.querySelector("input[name='name']");
      if (field) field.value = "";
      openDialog(createDialog);
    });
  });

  /* ---------- Card menus ---------- */
  function closeMenus(except) {
    document.querySelectorAll("[data-menu]").forEach(function (holder) {
      if (holder === except) return;
      var menu = holder.querySelector(".menu");
      var button = holder.querySelector("[data-menu-button]");
      if (menu) menu.hidden = true;
      if (button) button.setAttribute("aria-expanded", "false");
    });
  }

  document.querySelectorAll("[data-menu-button]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var holder = button.closest("[data-menu]");
      var menu = holder.querySelector(".menu");
      var willOpen = menu.hidden;
      closeMenus(holder);
      menu.hidden = !willOpen;
      button.setAttribute("aria-expanded", String(willOpen));
    });
  });

  document.addEventListener("click", function () { closeMenus(); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenus();
  });

  /* ---------- Rename ---------- */
  var renameForm = document.querySelector("[data-rename-form]");

  document.querySelectorAll("[data-project-rename]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!renameForm) return;
      renameForm.action = button.getAttribute("data-action");
      renameForm.querySelector("input[name='name']").value = button.getAttribute("data-name");
      closeMenus();
      openDialog(renameDialog);
    });
  });

  /* ---------- Delete confirmation ---------- */
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) event.preventDefault();
    });
  });
})();
