/**
 * Chat: send the question, stream the answer, render the sources,
 * and handle copy / retry / edit on messages.
 *
 * The server streams one JSON object per line (NDJSON):
 *   {"type":"saved","user_message_id":12}  {"type":"query","text":"..."}
 *   {"type":"sources","sources":[...]}     {"type":"token","text":"..."}
 *   {"type":"error","message":"..."}       {"type":"done"}
 */
(function () {
  "use strict";

  var form = document.getElementById("chat-form");
  var thread = document.getElementById("chat-thread");
  if (!form || !thread) return;

  var input = document.getElementById("chat-input");
  var sendButton = form.querySelector(".chat-composer__send");
  var emptyState = document.getElementById("chat-empty");
  var userTemplate = document.getElementById("tpl-user-message");
  var botTemplate = document.getElementById("tpl-bot-message");
  var SVG_NS = "http://www.w3.org/2000/svg";
  var busy = false;

  /* ---------- Small DOM helpers (no innerHTML anywhere) ---------- */
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function icon(id, className) {
    var svg = document.createElementNS(SVG_NS, "svg");
    var use = document.createElementNS(SVG_NS, "use");
    svg.setAttribute("class", className);
    use.setAttribute("href", "#" + id);
    svg.appendChild(use);
    return svg;
  }

  function timeNow() {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function isNearBottom() {
    return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120;
  }

  function scrollToBottom() {
    thread.scrollTop = thread.scrollHeight;
  }

  /* ---------- LaTeX cleanup (models sometimes ignore "no LaTeX") ---------- */
  var MATH_SYMBOLS = {
    chi: "\u03C7", alpha: "\u03B1", beta: "\u03B2", gamma: "\u03B3", delta: "\u03B4",
    Delta: "\u0394", epsilon: "\u03B5", rho: "\u03C1", sigma: "\u03C3", mu: "\u03BC",
    tau: "\u03C4", lambda: "\u03BB", pi: "\u03C0", theta: "\u03B8", omega: "\u03C9",
    Omega: "\u03A9", phi: "\u03C6", odot: "\u2299", sim: "~", approx: "\u2248",
    times: "\u00D7", cdot: "\u00B7", le: "\u2264", leq: "\u2264", ge: "\u2265",
    geq: "\u2265", pm: "\u00B1", propto: "\u221D", to: "\u2192", rightarrow: "\u2192",
    infty: "\u221E", left: "", right: ""
  };

  function cleanMath(text) {
    return text
      .replace(/\\[()\[\]]/g, "")
      .replace(/\\(?:mathrm|rm|text|mathit|mathbf)\{([^{}]*)\}/g, "$1")
      .replace(/\\([A-Za-z]+)/g, function (match, name) {
        return Object.prototype.hasOwnProperty.call(MATH_SYMBOLS, name) ? MATH_SYMBOLS[name] : name;
      })
      .replace(/\\[,;:! ]/g, " ")
      .replace(/_\{([^{}]*)\}/g, "_$1")
      .replace(/\^\{([^{}]*)\}/g, "^$1")
      .replace(/[{}$]/g, "");
  }

  /* ---------- Minimal, safe markdown: **bold**, `code`, lists, headings ---------- */
  function appendInline(parent, text) {
    text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach(function (part) {
      if (!part) return;
      if (part.length > 4 && part.slice(0, 2) === "**" && part.slice(-2) === "**") {
        parent.appendChild(el("strong", "", part.slice(2, -2)));
      } else if (part.length > 2 && part.charAt(0) === "`" && part.slice(-1) === "`") {
        parent.appendChild(el("code", "", part.slice(1, -1)));
      } else {
        parent.appendChild(document.createTextNode(part));
      }
    });
  }

  function renderMarkdown(container, text) {
    text = cleanMath(text);
    container.textContent = "";
    var list = null;
    var listType = null;
    var paragraph = null;

    text.replace(/\r\n/g, "\n").split("\n").forEach(function (line) {
      var ordered = line.match(/^\s*(\d+)[.)]\s+(.*)$/);
      var bullet = line.match(/^\s*[-*\u2022]\s+(.*)$/);
      var heading = line.match(/^\s*#{1,6}\s+(.*)$/);

      if (ordered || bullet) {
        var type = ordered ? "ol" : "ul";
        if (!list || listType !== type) {
          list = document.createElement(type);
          if (ordered) list.setAttribute("start", ordered[1]);
          listType = type;
          container.appendChild(list);
        }
        paragraph = null;
        var item = document.createElement("li");
        appendInline(item, ordered ? ordered[2] : bullet[1]);
        list.appendChild(item);
      } else if (!line.trim()) {
        paragraph = null;               // a blank line ends a paragraph, not a list
      } else if (heading) {
        list = null;
        paragraph = null;
        var p = document.createElement("p");
        p.appendChild(el("strong", "", heading[1]));
        container.appendChild(p);
      } else {
        list = null;
        if (!paragraph) {
          paragraph = document.createElement("p");
          container.appendChild(paragraph);
        } else {
          paragraph.appendChild(document.createElement("br"));
        }
        appendInline(paragraph, line.trim());
      }
    });
  }

  /* ---------- Messages ---------- */
  function addUserMessage(text) {
    var node = userTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector("[data-text]").textContent = text;
    node.querySelector("[data-time]").textContent = timeNow();
    thread.appendChild(node);
    return node;
  }

  function addBotMessage() {
    var node = botTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector("[data-time]").textContent = timeNow();
    thread.appendChild(node);
    return {
      node: node,
      userNode: null,
      status: node.querySelector("[data-status]"),
      text: node.querySelector("[data-text]"),
      sources: node.querySelector("[data-sources]"),
      answer: ""
    };
  }

  function renderSources(box, sources) {
    if (!sources || !sources.length) return;
    var list = box.querySelector(".sources__list");
    list.textContent = "";

    sources.forEach(function (source, index) {
      var item = document.createElement("li");
      var link = el("a", "source");
      link.href = source.url || "#";
      link.target = "_blank";
      link.rel = "noopener";

      var text = el("span", "source__text");
      text.appendChild(el("span", "source__title", source.title));
      if (source.page) text.appendChild(el("span", "source__meta", "Page " + source.page));

      link.appendChild(el("span", "source__index", index + 1 + "."));
      link.appendChild(text);
      link.appendChild(icon("i-external", "icon icon-sm source__open"));
      item.appendChild(link);
      list.appendChild(item);
    });
    box.hidden = false;
  }

  function showError(bot, message) {
    bot.status.textContent = message;
    bot.status.classList.add("is-error");
    bot.status.hidden = false;
  }

  /* ---------- Copy ---------- */
  function writeClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
      area.remove();
      if (ok) resolve(); else reject(new Error("Copy failed"));
    });
  }

  function flashCopied(button) {
    var use = button.querySelector("use");
    use.setAttribute("href", "#i-check");
    button.classList.add("is-copied");
    button.title = "Copied";
    window.setTimeout(function () {
      use.setAttribute("href", "#i-copy");
      button.classList.remove("is-copied");
      button.title = "Copy";
    }, 1500);
  }

  function copyMessage(article, button) {
    var text = article.classList.contains("message--user")
      ? article.querySelector("[data-text]").textContent
      : article.dataset.raw || "";
    if (!text.trim()) return;
    writeClipboard(text).then(
      function () { flashCopied(button); },
      function () { button.title = "Copy failed"; }
    );
  }

  /* ---------- Retry and edit ---------- */
  function findUserArticle(article) {
    if (article.classList.contains("message--user")) return article;
    var previous = article.previousElementSibling;
    return previous && previous.classList.contains("message--user") ? previous : null;
  }

  // Removes a message and everything after it (the server does the same in the database).
  function truncateFrom(node) {
    var current = node;
    while (current) {
      var next = current.nextElementSibling;
      current.remove();
      current = next;
    }
  }

  function retryMessage(article) {
    if (busy) return;
    var userArticle = findUserArticle(article);
    if (!userArticle) return;
    var question = userArticle.querySelector("[data-text]").textContent;
    send(question, { messageId: userArticle.dataset.messageId, replaceFrom: userArticle });
  }

  function startEdit(article) {
    if (busy || article.classList.contains("is-editing")) return;
    var bubble = article.querySelector("[data-text]");
    var original = bubble.textContent;

    var wrap = el("div", "edit-wrap");
    var area = el("textarea", "edit-box");
    area.value = original;
    area.rows = 1;
    area.maxLength = 1000;
    area.setAttribute("aria-label", "Edit your question");

    var controls = el("div", "edit-controls");
    var cancel = el("button", "btn btn--ghost btn--sm", "Cancel");
    var save = el("button", "btn btn--primary btn--sm", "Send");
    cancel.type = "button";
    save.type = "button";
    controls.appendChild(cancel);
    controls.appendChild(save);
    wrap.appendChild(area);
    wrap.appendChild(controls);

    function fit() {
      area.style.height = "auto";
      area.style.height = Math.min(area.scrollHeight, 240) + "px";
    }

    function finish() {
      wrap.remove();
      bubble.hidden = false;
      article.classList.remove("is-editing");
    }

    function submit() {
      var text = area.value.trim();
      if (!text) {
        area.focus();
        return;
      }
      finish();
      send(text, { messageId: article.dataset.messageId, replaceFrom: article });
    }

    area.addEventListener("input", fit);
    area.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        submit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        finish();
      }
    });
    cancel.addEventListener("click", finish);
    save.addEventListener("click", submit);

    bubble.hidden = true;
    article.classList.add("is-editing");
    bubble.insertAdjacentElement("afterend", wrap);
    fit();
    area.focus();
    area.setSelectionRange(area.value.length, area.value.length);
  }

  thread.addEventListener("click", function (event) {
    var button = event.target.closest("[data-action]");
    if (!button) return;
    var article = button.closest(".message");
    if (!article) return;

    var action = button.getAttribute("data-action");
    if (action === "copy") copyMessage(article, button);
    else if (action === "retry") retryMessage(article);
    else if (action === "edit") startEdit(article);
  });

  /* ---------- Streaming ---------- */
  function handleEvent(bot, event) {
    if (event.type === "saved") {
      if (bot.userNode) bot.userNode.dataset.messageId = event.user_message_id;
    } else if (event.type === "sources") {
      var stick = isNearBottom();
      renderSources(bot.sources, event.sources);
      if (stick) scrollToBottom();
    } else if (event.type === "token") {
      var follow = isNearBottom();
      bot.answer += event.text;
      bot.status.hidden = true;
      bot.text.hidden = false;
      renderMarkdown(bot.text, bot.answer);
      if (follow) scrollToBottom();
    } else if (event.type === "error") {
      throw new Error(event.message || "Something went wrong.");
    }
  }

  function handleLine(bot, line) {
    if (!line.trim()) return;
    handleEvent(bot, JSON.parse(line));
  }

  async function streamAnswer(formData, bot) {
    var response = await fetch(form.action, {
      method: "POST",
      body: formData,
      credentials: "same-origin"
    });

    var type = response.headers.get("Content-Type") || "";
    if (response.redirected || type.indexOf("application/x-ndjson") === -1) {
      if (type.indexOf("application/json") !== -1) {
        var data = await response.json();
        throw new Error(data.error || "The request failed.");
      }
      throw new Error("Your session may have expired. Refresh the page and sign in again.");
    }

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";

    while (true) {
      var chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      var lines = buffer.split("\n");
      buffer = lines.pop();
      for (var i = 0; i < lines.length; i++) handleLine(bot, lines[i]);
    }
    handleLine(bot, buffer);
  }

  function setBusy(state) {
    busy = state;
    input.disabled = state;
    sendButton.disabled = state;
    form.classList.toggle("is-busy", state);
    thread.classList.toggle("is-busy", state);
  }

  /*
   * Ask a question. With options.replaceFrom (a user message element) the conversation
   * is cut back to that message first, which is how retry and edit work.
   */
  async function send(question, options) {
    options = options || {};

    var formData = new FormData(form);   // carries the CSRF token
    formData.set("question", question);
    if (options.messageId) formData.set("message_id", options.messageId);
    else formData.delete("message_id");

    setBusy(true);
    if (emptyState) emptyState.hidden = true;
    if (options.replaceFrom) truncateFrom(options.replaceFrom);

    var userNode = addUserMessage(question);
    var bot = addBotMessage();
    bot.userNode = userNode;
    bot.node.classList.add("is-streaming");
    scrollToBottom();

    try {
      await streamAnswer(formData, bot);
      if (!bot.answer) showError(bot, "No answer was returned.");
    } catch (error) {
      showError(bot, error.message || "Network error. Please try again.");
    } finally {
      bot.node.classList.remove("is-streaming");
      bot.node.dataset.raw = cleanMath(bot.answer);
      setBusy(false);
      input.focus();
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var question = input.value.trim();
    if (busy || !question) return;
    input.value = "";
    send(question);
  });

  /* ---------- Initial page load: format saved answers, jump to the latest ---------- */
  thread.querySelectorAll("[data-markdown]").forEach(function (node) {
    var raw = node.textContent;
    if (!raw.trim()) return;
    var article = node.closest(".message");
    if (article) article.dataset.raw = cleanMath(raw);
    renderMarkdown(node, raw);
  });
  scrollToBottom();
})();
