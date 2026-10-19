/**
 * Upload Paper dialog: open/close, drag and drop, and quick client-side checks.
 * The server (forms.py) validates again, so this is only for faster feedback.
 */
(function () {
  "use strict";

  var dialog = document.querySelector("[data-upload-dialog]");
  if (!dialog || typeof dialog.showModal !== "function") return;

  var form = dialog.querySelector("form");
  var input = dialog.querySelector('input[type="file"]');
  var zone = dialog.querySelector("[data-dropzone]");
  var fileName = dialog.querySelector("[data-file-name]");
  var titleInput = dialog.querySelector('input[name="title"]');
  var clientError = dialog.querySelector("[data-client-error]");
  var submitButton = dialog.querySelector("[data-upload-submit]");
  var maxBytes = (parseInt(dialog.getAttribute("data-max-mb"), 10) || 25) * 1024 * 1024;
  var defaultMeta = fileName.textContent;

  /* ---------- Open / close ---------- */
  document.querySelectorAll("[data-upload-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      dialog.showModal();
    });
  });

  dialog.querySelectorAll("[data-upload-close]").forEach(function (button) {
    button.addEventListener("click", function () {
      dialog.close();
    });
  });

  // Clicking the backdrop (the dialog element itself) closes it.
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener("close", resetState);

  if (dialog.hasAttribute("data-open-on-load")) {
    dialog.showModal();
  }

  /* ---------- File handling ---------- */
  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function stem(name) {
    return name.replace(/\.[^.]+$/, "");
  }

  function setError(message) {
    clientError.textContent = message || "";
    clientError.hidden = !message;
  }

  function validate(file) {
    if (!file) return "Choose a PDF file.";
    var isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    if (!isPdf) return "Only PDF files are supported.";
    if (file.size > maxBytes) return "The file is larger than " + maxBytes / (1024 * 1024) + " MB.";
    return "";
  }

  function clearFile() {
    input.value = "";
    fileName.textContent = defaultMeta;
    zone.classList.remove("has-file");
    if (titleInput) titleInput.placeholder = "Defaults to the file name";
  }

  function handleFile(file) {
    var message = validate(file);
    setError(message);
    if (message) {
      clearFile();
      return;
    }
    fileName.textContent = file.name + " \u00B7 " + formatSize(file.size);
    zone.classList.add("has-file");
    if (titleInput) titleInput.placeholder = stem(file.name);
  }

  input.addEventListener("change", function () {
    handleFile(input.files && input.files[0]);
  });

  /* ---------- Drag and drop ---------- */
  ["dragenter", "dragover"].forEach(function (type) {
    zone.addEventListener(type, function (event) {
      event.preventDefault();
      zone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach(function (type) {
    zone.addEventListener(type, function () {
      zone.classList.remove("is-dragover");
    });
  });

  zone.addEventListener("drop", function (event) {
    event.preventDefault();
    var file = event.dataTransfer && event.dataTransfer.files[0];
    if (!file) return;
    try {
      var transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
    } catch (e) {
      /* Older browsers: the user can still use the file picker. */
    }
    handleFile(file);
  });

  /* ---------- Submit ---------- */
  form.addEventListener("submit", function (event) {
    var file = input.files && input.files[0];
    var message = validate(file);
    if (message) {
      event.preventDefault();
      setError(message);
      return;
    }
    submitButton.disabled = true;
    submitButton.textContent = "Uploading\u2026";
  });

  function resetState() {
    form.reset();
    clearFile();
    setError("");
    submitButton.disabled = false;
    submitButton.textContent = "Upload paper";
  }
})();
