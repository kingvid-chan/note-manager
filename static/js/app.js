/* ═══════════════════════════════════════════════════════════════
   Note Manager — SPA Router + API Client + Views
   Version: 0.0.1
   ═══════════════════════════════════════════════════════════════ */

;(function () {
  "use strict";

  /* ── Constants ────────────────────────────────────────────── */
  const BASE = "/projects/note-manager";
  const API = BASE + "/api";
  const STATIC = BASE + "/static";
  const VERSION = "0.0.1";
  const JWT_KEY = "jwt_token";

  /* ── State ────────────────────────────────────────────────── */
  const state = {
    currentRoute: null,
    currentUser: null,
    tags: [],
  };

  /* ═════════════════════════════════════════════════════════════
     API Client
     ═════════════════════════════════════════════════════════════ */

  const api = {
    /**
     * Get the stored JWT token from sessionStorage.
     */
    token() {
      return sessionStorage.getItem(JWT_KEY);
    },

    /**
     * Base fetch wrapper. Attaches Authorization header automatically.
     * On 401 response, clears token and redirects to login.
     */
    async request(method, path, body) {
      const headers = {};

      const token = this.token();
      if (token) {
        headers["Authorization"] = "Bearer " + token;
      }

      if (body && !(body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
      }

      const opts = { method, headers };
      if (body) {
        opts.body =
          body instanceof FormData ? body : JSON.stringify(body);
      }

      let res;
      try {
        res = await fetch(API + path, opts);
      } catch (err) {
        throw new Error("Network error — please check your connection.");
      }

      // 401 → clear token, redirect to login
      if (res.status === 401 && this.token()) {
        sessionStorage.removeItem(JWT_KEY);
        state.currentUser = null;
        router.navigate("/login");
        throw new Error("Session expired. Please log in again.");
      }

      // 204 No Content
      if (res.status === 204) return null;

      const data = await res.json();

      if (!res.ok) {
        const msg =
          (data && data.detail) || "Request failed (" + res.status + ")";
        const err = new Error(msg);
        err.status = res.status;
        throw err;
      }

      return data;
    },

    get(path) {
      return this.request("GET", path);
    },
    post(path, body) {
      return this.request("POST", path, body);
    },
    put(path, body) {
      return this.request("PUT", path, body);
    },
    delete(path) {
      return this.request("DELETE", path);
    },
  };

  /* ═════════════════════════════════════════════════════════════
     marked.js Configuration — Global
     ═════════════════════════════════════════════════════════════ */

  /**
   * Initialize marked.js with GFM, tables, line breaks, and sanitization.
   * Called once on script load. Safe to call again after marked loads async.
   */
  function initMarked() {
    if (typeof marked === "undefined") return false;

    marked.setOptions({
      gfm: true,        // GitHub Flavored Markdown (tables, strikethrough, task lists)
      breaks: true,     // Convert \n → <br>
    });

    // Custom renderer: add language labels to code blocks
    var renderer = new marked.Renderer();
    var origCode = renderer.code.bind(renderer);
    renderer.code = function (code, language) {
      var langLabel = language
        ? '<div class="code-lang">' + esc(language) + "</div>"
        : "";
      return (
        '<div class="code-block-wrapper">' +
        langLabel +
        "<pre><code" +
        (language ? ' class="language-' + esc(language) + '"' : "") +
        ">" +
        code +
        "</code></pre></div>"
      );
    };
    marked.setOptions({ renderer: renderer });

    return true;
  }

  /**
   * Sanitize rendered HTML — strip <script>, event handlers, javascript: URLs.
   * marked v15 removed built-in sanitize; we apply a basic guard.
   */
  function sanitizeHTML(html) {
    if (!html) return "";
    // Strip <script> tags
    html = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
    // Strip on* event handlers
    html = html.replace(/\son\w+\s*=\s*"[^"]*"/gi, "");
    html = html.replace(/\son\w+\s*=\s*'[^']*'/gi, "");
    // Strip javascript: URLs
    html = html.replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"');
    html = html.replace(/href\s*=\s*'javascript:[^']*'/gi, "href='#'");
    return html;
  }

  /**
   * Render Markdown → sanitized HTML. Safe to call anywhere.
   */
  function renderMarkdown(md) {
    if (typeof marked === "undefined") {
      return "<p>Markdown parser not loaded.</p>";
    }
    var html = marked.parse(md || "");
    return sanitizeHTML(html);
  }

  // Init marked on load
  initMarked();

  /* ═════════════════════════════════════════════════════════════
     Router
     ═════════════════════════════════════════════════════════════ */

  const router = {
    routes: [],

    /**
     * Register a route pattern. Supports named params with :param syntax.
     */
    on(pattern, handler) {
      // Convert "/notes/:id" → regex ^\/notes\/([^/]+)$
      const paramNames = [];
      const regexStr = pattern
        .replace(/:([^/]+)/g, (_, name) => {
          paramNames.push(name);
          return "([^/]+)";
        })
        .replace(/\//g, "\\/");
      const regex = new RegExp("^" + regexStr + "$");
      this.routes.push({ regex, paramNames, handler, pattern });
    },

    /**
     * Navigate to a hash route.
     */
    navigate(hash) {
      if (hash.startsWith("#")) hash = hash.slice(1);
      window.location.hash = hash;
    },

    /**
     * Get current hash without the leading #.
     */
    currentHash() {
      return window.location.hash.slice(1) || "/";
    },

    /**
     * Match and dispatch the current route.
     */
    dispatch() {
      const hash = this.currentHash();
      state.currentRoute = hash;

      for (const route of this.routes) {
        const m = hash.match(route.regex);
        if (m) {
          const params = {};
          route.paramNames.forEach((name, i) => {
            params[name] = decodeURIComponent(m[i + 1]);
          });
          route.handler(params);
          return;
        }
      }

      // Fallback — redirect based on auth state
      if (api.token()) {
        this.navigate("/notes");
      } else {
        this.navigate("/login");
      }
    },

    init() {
      window.addEventListener("hashchange", () => this.dispatch());
      // Initial dispatch
      if (!window.location.hash) {
        if (api.token()) {
          this.navigate("/notes");
        } else {
          this.navigate("/login");
        }
      }
      this.dispatch();
    },
  };

  /* ═════════════════════════════════════════════════════════════
     View Helpers
     ═════════════════════════════════════════════════════════════ */

  const app = document.getElementById("app");

  /** Render HTML into #app. */
  function render(html) {
    app.innerHTML = html;
  }

  /** Escape HTML entities. */
  function esc(str) {
    if (!str) return "";
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return String(str).replace(/[&<>"']/g, (c) => map[c]);
  }

  /** Format ISO date to locale string. */
  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  }

  /** Show a toast notification. */
  function toast(message, type) {
    type = type || "info";
    let container = document.querySelector(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    const el = document.createElement("div");
    el.className = "toast toast-" + type;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(function () {
      el.remove();
      if (!container.children.length) container.remove();
    }, 3000);
  }

  /** Simple debounce. */
  function debounce(fn, ms) {
    let timer;
    return function () {
      const ctx = this, args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  /* ═════════════════════════════════════════════════════════════
     Auth Views
     ═════════════════════════════════════════════════════════════ */

  function authView() {
    // If already logged in, redirect to notes
    if (api.token()) {
      router.navigate("/notes");
      return;
    }
    // Determine initial tab from hash route
    var initTab = (window.location.hash.slice(1) === "/register") ? "register" : "login";
    let tab = initTab;
    let error = "";
    let success = "";

    function setTab(t) {
      tab = t;
      error = "";
      success = "";
      draw();
    }

    async function handleLogin(e) {
      e.preventDefault();
      error = "";
      success = "";
      const username = document.getElementById("login-username").value.trim();
      const password = document.getElementById("login-password").value;
      if (!username || !password) {
        error = "Please fill in all fields.";
        draw();
        return;
      }
      try {
        const data = await api.post("/auth/login", { username, password });
        sessionStorage.setItem(JWT_KEY, data.access_token);
        state.currentUser = data.user;
        router.navigate("/notes");
      } catch (err) {
        error = err.message;
        draw();
      }
    }

    async function handleRegister(e) {
      e.preventDefault();
      error = "";
      success = "";
      const username = document.getElementById("reg-username").value.trim();
      const email = document.getElementById("reg-email").value.trim();
      const password = document.getElementById("reg-password").value;
      const confirm = document.getElementById("reg-confirm").value;
      if (!username || !email || !password || !confirm) {
        error = "Please fill in all fields.";
        draw();
        return;
      }
      if (password.length < 6) {
        error = "Password must be at least 6 characters.";
        draw();
        return;
      }
      if (password !== confirm) {
        error = "Passwords do not match.";
        draw();
        return;
      }
      try {
        await api.post("/auth/register", { username, email, password });
        success = "Registration successful! Please log in.";
        setTab("login");
      } catch (err) {
        error = err.message;
        draw();
      }
    }

    function fillDemo() {
      document.getElementById("login-username").value = "demo";
      document.getElementById("login-password").value = "demo123";
    }

    function draw() {
      render(`
        <div class="auth-container">
          <div class="auth-card">
            <h1><span>Note</span> Manager</h1>
            <div class="auth-tabs">
              <button class="auth-tab ${tab === "login" ? "active" : ""}" id="tab-login">Login</button>
              <button class="auth-tab ${tab === "register" ? "active" : ""}" id="tab-register">Register</button>
            </div>
            ${error ? `<div class="auth-error">${esc(error)}</div>` : ""}
            ${success ? `<div class="auth-success">${esc(success)}</div>` : ""}
            ${tab === "login" ? `
              <form id="login-form">
                <div class="form-group">
                  <label class="form-label" for="login-username">Username</label>
                  <input class="form-input" id="login-username" type="text" placeholder="Enter username" autocomplete="username">
                </div>
                <div class="form-group">
                  <label class="form-label" for="login-password">Password</label>
                  <input class="form-input" id="login-password" type="password" placeholder="Enter password" autocomplete="current-password">
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%">Login</button>
                <div class="auth-footer">
                  <button type="button" class="btn btn-sm" id="demo-btn">🔑 Demo Account</button>
                </div>
              </form>
            ` : `
              <form id="register-form">
                <div class="form-group">
                  <label class="form-label" for="reg-username">Username</label>
                  <input class="form-input" id="reg-username" type="text" placeholder="3–64 characters" autocomplete="username" minlength="3" maxlength="64">
                </div>
                <div class="form-group">
                  <label class="form-label" for="reg-email">Email</label>
                  <input class="form-input" id="reg-email" type="email" placeholder="you@example.com" autocomplete="email">
                </div>
                <div class="form-group">
                  <label class="form-label" for="reg-password">Password</label>
                  <input class="form-input" id="reg-password" type="password" placeholder="At least 6 characters" autocomplete="new-password" minlength="6">
                </div>
                <div class="form-group">
                  <label class="form-label" for="reg-confirm">Confirm Password</label>
                  <input class="form-input" id="reg-confirm" type="password" placeholder="Re-enter password" autocomplete="new-password">
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%">Register</button>
              </form>
            `}
          </div>
        </div>
      `);

      // Bind events
      document.getElementById("tab-login").addEventListener("click", function () { setTab("login"); });
      document.getElementById("tab-register").addEventListener("click", function () { setTab("register"); });
      if (tab === "login") {
        document.getElementById("login-form").addEventListener("submit", handleLogin);
        document.getElementById("demo-btn").addEventListener("click", fillDemo);
      } else {
        document.getElementById("register-form").addEventListener("submit", handleRegister);
      }
    }

    draw();
  }

  /* ═════════════════════════════════════════════════════════════
     Note List View
     ═════════════════════════════════════════════════════════════ */

  function notesListView() {
    let notes = [];
    let total = 0;
    let page = 1;
    let search = "";
    let selectedTags = [];
    let loading = true;
    const perPage = 20;

    async function loadTags() {
      try {
        const data = await api.get("/tags/");
        state.tags = data.items || [];
      } catch (_) {
        state.tags = [];
      }
    }

    async function loadNotes(append) {
      loading = true;
      if (!append) draw();
      try {
        const params = new URLSearchParams();
        params.set("page", page);
        params.set("per_page", perPage);
        if (search) params.set("search", search);
        if (selectedTags.length) params.set("tag", selectedTags.join(","));
        const data = await api.get("/notes/?" + params.toString());
        if (append) {
          notes = notes.concat(data.items || []);
        } else {
          notes = data.items || [];
        }
        total = data.total || 0;
      } catch (err) {
        toast(err.message, "error");
        notes = [];
        total = 0;
      }
      loading = false;
      draw();
    }

    async function handleDeleteNote(noteId) {
      if (!confirm("Delete this note permanently?")) return;
      try {
        await api.delete("/notes/" + noteId);
        toast("Note deleted.", "success");
        await loadNotes();
      } catch (err) {
        toast(err.message, "error");
      }
    }

    function totalPages() {
      return Math.max(1, Math.ceil(total / perPage));
    }

    function draw() {
      const user = state.currentUser;
      const hasActiveFilters = search || selectedTags.length > 0;
      const tagItems = state.tags
        .map(function (t) {
          const active = selectedTags.indexOf(t.name) >= 0;
          return `<span class="tag ${active ? "active" : ""}" data-tag="${esc(t.name)}">${active ? "✓ " : ""}${esc(t.name)}</span>`;
        })
        .join("");

      render(`
        <div class="nav">
          <div class="nav-brand"><span>Note</span> Manager</div>
          <div class="nav-actions">
            <span class="nav-user">${esc(user ? user.username : "")}</span>
            <button class="btn btn-sm" id="btn-logout">Logout</button>
          </div>
        </div>
        <div style="max-width:var(--max-width);margin:0 auto;padding:var(--space-lg) var(--space-lg) 0;">
          <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-md);flex-wrap:wrap;">
            <div class="search-bar">
              <input class="form-input" id="search-input" type="text" placeholder="Search notes..." value="${esc(search)}">
            </div>
            ${hasActiveFilters ? `<button class="btn btn-sm" id="btn-clear-filters" title="Clear all filters">✕ Clear</button>` : ""}
          </div>
          ${state.tags.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:var(--space-sm);align-items:center;">
            <span style="font-size:var(--font-size-xs);color:var(--text-muted);margin-right:4px;">Tags:</span>${tagItems}</div>` : ""}
          ${!loading && notes.length > 0 ? `<div style="font-size:var(--font-size-xs);color:var(--text-muted);margin-bottom:var(--space-sm);">${total} note${total !== 1 ? "s" : ""} found</div>` : ""}
        </div>
        ${loading ? `
          <div class="loading"><div class="spinner"></div> Loading notes...</div>
        ` : notes.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <h3>${hasActiveFilters ? "No matching notes" : "No notes yet"}</h3>
            <p>${hasActiveFilters ? "Try adjusting your search or filters." : "Create your first note to get started."}</p>
            ${hasActiveFilters ? `<button class="btn" id="btn-empty-clear">Clear Filters</button>` : `<button class="btn btn-primary" id="btn-empty-create">Create Note</button>`}
          </div>
        ` : `
          <div class="card-grid">
            ${notes.map(function (n) { return `
              <div class="card" style="cursor:pointer" data-note-id="${n.id}">
                <div class="card-body">
                  <div class="card-title">${esc(n.title || "Untitled")}</div>
                  <div class="card-meta">Updated ${fmtDate(n.updated_at)}</div>
                  <div class="card-excerpt">${esc((n.content_md || "").slice(0, 100))}</div>
                  ${(n.tags || []).length ? `
                    <div class="card-tags">
                      ${n.tags.map(function (t) { return `<span class="tag">${esc(t.name)}</span>`; }).join("")}
                    </div>
                  ` : ""}
                </div>
              </div>
            `; }).join("")}
          </div>
          <div style="text-align:center;padding:var(--space-lg);">
            ${notes.length < total ? `<button class="btn" id="btn-load-more">Load More (${notes.length} / ${total})</button>` : ""}
          </div>
        `}
        <button class="fab" id="fab-new" title="New Note">+</button>
        <div id="list-modals"></div>
      `);

      // Bind events
      document.getElementById("btn-logout").addEventListener("click", function () {
        sessionStorage.removeItem(JWT_KEY);
        state.currentUser = null;
        router.navigate("/login");
      });

      document.getElementById("fab-new").addEventListener("click", function () {
        router.navigate("/notes/new");
      });

      // Search with debounce
      const searchInput = document.getElementById("search-input");
      if (searchInput) {
        searchInput.addEventListener("input", debounce(function () {
          search = this.value.trim();
          page = 1;
          loadNotes();
        }, 300));
      }

      // Clear filters button
      var clearBtn = document.getElementById("btn-clear-filters");
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          search = "";
          selectedTags = [];
          page = 1;
          loadNotes();
        });
      }

      // Tag filter clicks
      document.querySelectorAll(".tag[data-tag]").forEach(function (el) {
        el.addEventListener("click", function () {
          const tagName = this.getAttribute("data-tag");
          const idx = selectedTags.indexOf(tagName);
          if (idx >= 0) {
            selectedTags.splice(idx, 1);
          } else {
            selectedTags.push(tagName);
          }
          page = 1;
          loadNotes();
        });
      });

      // Note card clicks → navigate to editor
      document.querySelectorAll(".card[data-note-id]").forEach(function (el) {
        el.addEventListener("click", function () {
          router.navigate("/notes/" + this.getAttribute("data-note-id"));
        });
      });

      // Empty state buttons
      var emptyCreate = document.getElementById("btn-empty-create");
      var emptyClear = document.getElementById("btn-empty-clear");
      if (emptyCreate) {
        emptyCreate.addEventListener("click", function () { router.navigate("/notes/new"); });
      }
      if (emptyClear) {
        emptyClear.addEventListener("click", function () {
          search = "";
          selectedTags = [];
          page = 1;
          loadNotes();
        });
      }

      // Load More button — append next page
      var loadMoreBtn = document.getElementById("btn-load-more");
      if (loadMoreBtn) {
        loadMoreBtn.addEventListener("click", function () {
          page++;
          loadNotes(true);
        });
      }

      // Pagination
      var prevBtn = document.getElementById("btn-prev");
      var nextBtn = document.getElementById("btn-next");
      if (prevBtn) {
        prevBtn.addEventListener("click", function () {
          if (page > 1) { page--; loadNotes(); }
        });
      }
      if (nextBtn) {
        nextBtn.addEventListener("click", function () {
          if (page < totalPages()) { page++; loadNotes(); }
        });
      }
    }

    // Init
    async function init() {
      // Load current user if not loaded
      if (!state.currentUser && api.token()) {
        try {
          const user = await api.get("/auth/me");
          state.currentUser = { id: user.id, username: user.username };
        } catch (_) {
          sessionStorage.removeItem(JWT_KEY);
          router.navigate("/login");
          return;
        }
      }
      await loadTags();
      await loadNotes();
    }

    init();
  }

  /* ═════════════════════════════════════════════════════════════
     Note Editor View
     ═════════════════════════════════════════════════════════════ */

  function noteEditorView(params) {
    const noteId = params.id || null;
    const isNew = !noteId;

    let note = isNew
      ? { title: "Untitled", content_md: "", tags: [] }
      : null;
    let noteTags = [];
    let saved = false;
    let saving = false;
    let loading = !isNew;
    let draftTimer = null;

    function updatePreview() {
      const textarea = document.getElementById("editor-textarea");
      const preview = document.getElementById("editor-preview");
      if (textarea && preview) {
        preview.innerHTML = '<div class="preview-content">' + renderMarkdown(textarea.value) + "</div>";
      }
    }

    // Draft auto-save to localStorage (every 5s)
    function startDraftAutoSave() {
      const key = isNew ? "draft:new" : "draft:" + noteId;
      // Restore draft
      const draft = localStorage.getItem(key);
      const textarea = document.getElementById("editor-textarea");
      const titleInput = document.getElementById("editor-title");
      if (draft && textarea) {
        try {
          const d = JSON.parse(draft);
          if (d.content_md && textarea.value === (note ? note.content_md || "" : "")) {
            textarea.value = d.content_md;
            if (d.title && titleInput) titleInput.value = d.title;
            updatePreview();
          }
        } catch (_) {}
      }
      // Save periodically (every 5s)
      draftTimer = setInterval(function () {
        const ta = document.getElementById("editor-textarea");
        const ti = document.getElementById("editor-title");
        if (ta) {
          localStorage.setItem(key, JSON.stringify({
            content_md: ta.value,
            title: ti ? ti.value : "",
          }));
          // Show draft indicator
          var status = document.getElementById("save-status");
          if (status && status.textContent !== "✓ Saved") {
            status.textContent = "📝 Draft saved";
            status.style.color = "var(--text-muted)";
          }
        }
      }, 5000);
    }

    function clearDraft() {
      const key = isNew ? "draft:new" : "draft:" + noteId;
      localStorage.removeItem(key);
    }

    async function saveNote() {
      if (saving) return;
      saving = true;
      const titleEl = document.getElementById("editor-title");
      const textarea = document.getElementById("editor-textarea");
      const title = (titleEl.value || "").trim() || "Untitled";
      const content_md = textarea.value;
      const tagIds = noteTags.map(function (t) { return t.id; });

      try {
        let result;
        if (isNew) {
          result = await api.post("/notes", { title: title, content_md: content_md, tag_ids: tagIds });
          clearDraft();
          // Update URL to the new note
          router.navigate("/notes/" + result.id);
          // Reload full editor with the saved note
          return;
        } else {
          result = await api.put("/notes/" + noteId, { title: title, content_md: content_md, tag_ids: tagIds });
        }
        note = result;
        noteTags = result.tags || [];
        saved = true;
        saving = false;
        clearDraft();
        toast("Saved ✓", "success");
        // Update status indicator
        var status = document.getElementById("save-status");
        if (status) { status.textContent = "✓ Saved"; status.style.color = "var(--accent-secondary)"; }
        drawEditor();
      } catch (err) {
        toast(err.message, "error");
      }
      saving = false;
    }

    async function handleDelete() {
      if (!confirm("Delete this note? This cannot be undone.")) return;
      try {
        await api.delete("/notes/" + noteId);
        clearDraft();
        toast("Note deleted.", "success");
        router.navigate("/notes");
      } catch (err) {
        toast(err.message, "error");
      }
    }

    async function handleShare() {
      try {
        const share = await api.post("/notes/" + noteId + "/share", { expires_in_hours: 168 });
        const fullUrl = window.location.origin + BASE + "/#/share/" + share.token;
        // Show modal with share link
        const modalDiv = document.getElementById("editor-modals");
        modalDiv.innerHTML = `
          <div class="modal-overlay" id="share-modal-overlay">
            <div class="modal">
              <h3>📤 Share Note</h3>
              <p style="color:var(--text-secondary);margin-bottom:var(--space-md);">Anyone with this link can view the note:</p>
              <input class="form-input" id="share-url-input" value="${esc(fullUrl)}" readonly style="margin-bottom:var(--space-sm);">
              <p style="font-size:var(--font-size-xs);color:var(--text-muted);">Expires in 7 days</p>
              <div class="modal-actions">
                <button class="btn btn-primary" id="btn-copy-share">📋 Copy Link</button>
                <button class="btn" id="btn-close-share">Close</button>
              </div>
            </div>
          </div>
        `;
        document.getElementById("btn-copy-share").addEventListener("click", function () {
          const input = document.getElementById("share-url-input");
          input.select();
          document.execCommand("copy");
          toast("Link copied!", "success");
        });
        document.getElementById("btn-close-share").addEventListener("click", function () {
          document.getElementById("share-modal-overlay").remove();
        });
        document.getElementById("share-modal-overlay").addEventListener("click", function (e) {
          if (e.target === this) this.remove();
        });
      } catch (err) {
        toast(err.message, "error");
      }
    }

    function toggleTag(tag) {
      const idx = noteTags.findIndex(function (t) { return t.id === tag.id; });
      if (idx >= 0) {
        noteTags.splice(idx, 1);
      } else {
        noteTags.push(tag);
      }
      drawEditor();
    }

    async function createAndAddTag() {
      const input = document.getElementById("new-tag-input");
      const name = (input.value || "").trim();
      if (!name) return;
      if (name.length > 64) {
        toast("Tag name must be ≤ 64 characters.", "error");
        return;
      }
      try {
        const tag = await api.post("/tags/", { name: name });
        noteTags.push(tag);
        // Refresh global tag list
        const allTags = await api.get("/tags/");
        state.tags = allTags.items || [];
        input.value = "";
        drawEditor();
      } catch (err) {
        toast(err.message, "error");
      }
    }

    function drawEditor() {
      const user = state.currentUser;
      const availableTags = state.tags.filter(function (t) {
        return !noteTags.some(function (nt) { return nt.id === t.id; });
      });
      const title = note ? note.title : "Untitled";
      const content = note ? (note.content_md || "") : "";

      render(`
        <div class="nav">
          <div class="nav-brand"><a href="#/notes" style="color:inherit;text-decoration:none;"><span>Note</span> Manager</a></div>
          <div class="nav-actions">
            <span class="nav-user">${esc(user ? user.username : "")}</span>
            <button class="btn btn-sm" id="btn-logout">Logout</button>
          </div>
        </div>
        <div class="editor-toolbar">
          <div class="editor-toolbar-left">
            <a href="#/notes" class="btn btn-sm">← Notes</a>
            <span style="color:var(--border-color);margin:0 4px;">|</span>
            <button class="btn btn-sm btn-primary" id="btn-save">💾 Save</button>
            ${!isNew ? `<button class="btn btn-sm" id="btn-share">📤 Share</button>` : ""}
            ${!isNew ? `<button class="btn btn-sm btn-danger" id="btn-delete">🗑 Delete</button>` : ""}
            <span id="save-status" style="font-size:var(--font-size-xs);margin-left:var(--space-sm);"></span>
          </div>
          <div class="editor-toolbar-right">
            <span style="font-size:var(--font-size-xs);color:var(--text-muted);">Ctrl+S · Markdown</span>
          </div>
        </div>
        <div class="editor-container">
          <div class="editor-pane">
            <div class="editor-pane-header">Markdown</div>
            <div class="editor-pane-body" style="padding:0;display:flex;flex-direction:column;">
              <input class="form-input" id="editor-title" value="${esc(title)}" placeholder="Note title" style="border:none;border-bottom:1px solid var(--border-color);font-size:var(--font-size-xl);font-weight:600;padding:var(--space-md);flex-shrink:0;">
              <textarea class="editor-textarea" id="editor-textarea" placeholder="Write in Markdown..." style="display:block;padding:var(--space-md);flex:1;">${esc(content)}</textarea>
            </div>
          </div>
          <div class="editor-pane">
            <div class="editor-pane-header">Preview</div>
            <div class="editor-pane-body preview" id="editor-preview">
              <div class="preview-content">${renderMarkdown(content)}</div>
            </div>
          </div>
        </div>
        <div style="padding:var(--space-sm) var(--space-md);background:var(--bg-secondary);border-top:1px solid var(--border-color);">
          <div style="display:flex;align-items:center;gap:var(--space-sm);flex-wrap:wrap;">
            <span style="font-size:var(--font-size-xs);color:var(--text-muted);">Tags:</span>
            ${noteTags.map(function (t) { return `<span class="tag" data-tag-id="${t.id}">${esc(t.name)}<span class="tag-remove">×</span></span>`; }).join("")}
            ${availableTags.length ? `
              <span style="font-size:var(--font-size-xs);color:var(--text-muted);margin-left:var(--space-sm);">Add:</span>
              ${availableTags.map(function (t) { return `<span class="tag" data-add-tag-id="${t.id}" style="opacity:0.6;cursor:pointer;">+${esc(t.name)}</span>`; }).join("")}
            ` : ""}
            <input class="form-input" id="new-tag-input" placeholder="New tag..." style="width:100px;padding:2px 8px;font-size:var(--font-size-xs);">
            <button class="btn btn-sm" id="btn-add-tag">+</button>
          </div>
        </div>
        <div id="editor-modals"></div>
      `);

      // Bind events
      document.getElementById("btn-logout").addEventListener("click", function () {
        sessionStorage.removeItem(JWT_KEY);
        state.currentUser = null;
        router.navigate("/login");
      });

      document.getElementById("btn-save").addEventListener("click", saveNote);

      if (!isNew) {
        document.getElementById("btn-share").addEventListener("click", handleShare);
        document.getElementById("btn-delete").addEventListener("click", handleDelete);
      }

      const textarea = document.getElementById("editor-textarea");
      textarea.addEventListener("input", function () {
        updatePreview();
        // Show draft indicator
        var status = document.getElementById("save-status");
        if (status) { status.textContent = "✎ Unsaved"; status.style.color = "var(--accent-warning)"; }
      });

      // Ctrl+S / Cmd+S
      document.addEventListener("keydown", function handler(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
          e.preventDefault();
          saveNote();
        }
      });

      document.getElementById("btn-add-tag").addEventListener("click", createAndAddTag);
      document.getElementById("new-tag-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); createAndAddTag(); }
      });

      // Tag remove clicks
      document.querySelectorAll(".tag[data-tag-id] .tag-remove").forEach(function (el) {
        el.addEventListener("click", function (e) {
          e.stopPropagation();
          const tagId = parseInt(this.parentElement.getAttribute("data-tag-id"));
          noteTags = noteTags.filter(function (t) { return t.id !== tagId; });
          drawEditor();
        });
      });

      // Tag add clicks
      document.querySelectorAll(".tag[data-add-tag-id]").forEach(function (el) {
        el.addEventListener("click", function () {
          const tagId = parseInt(this.getAttribute("data-add-tag-id"));
          const tag = state.tags.find(function (t) { return t.id === tagId; });
          if (tag) toggleTag(tag);
        });
      });

      // Start draft auto-save
      startDraftAutoSave();
    }

    function drawLoading() {
      render(`
        <div class="nav">
          <div class="nav-brand"><a href="#/notes" style="color:inherit;text-decoration:none;"><span>Note</span> Manager</a></div>
        </div>
        <div class="loading"><div class="spinner"></div> Loading note...</div>
      `);
    }

    async function init() {
      // Load current user
      if (!state.currentUser && api.token()) {
        try {
          const user = await api.get("/auth/me");
          state.currentUser = { id: user.id, username: user.username };
        } catch (_) {
          sessionStorage.removeItem(JWT_KEY);
          router.navigate("/login");
          return;
        }
      }

      // Load tags
      try {
        const data = await api.get("/tags/");
        state.tags = data.items || [];
      } catch (_) {
        state.tags = [];
      }

      if (isNew) {
        note = { title: "Untitled", content_md: "", tags: [] };
        noteTags = [];
        loading = false;
        drawEditor();
      } else {
        drawLoading();
        try {
          note = await api.get("/notes/" + noteId);
          noteTags = note.tags || [];
          loading = false;
          drawEditor();
        } catch (err) {
          if (err.status === 404) {
            render(`<div class="empty-state"><div class="empty-state-icon">🔍</div><h3>Note not found</h3><p>${esc(err.message)}</p><a href="#/notes">← Back to notes</a></div>`);
          } else {
            toast(err.message, "error");
            router.navigate("/notes");
          }
        }
      }
    }

    init();
  }

  /* ═════════════════════════════════════════════════════════════
     Public Share View
     ═════════════════════════════════════════════════════════════ */

  function shareView(params) {
    const token = params.token;
    let loading = true;
    let error = null;
    let note = null;

    function draw() {
      if (loading) {
        render(`
          <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg-primary);">
            <div class="loading"><div class="spinner"></div> Loading shared note...</div>
          </div>
        `);
        return;
      }

      if (error) {
        var isExpired = error.status === 404;
        render(`
          <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg-primary);">
            <div class="share-error">
              <div class="share-error-icon">${isExpired ? "⏳" : "🔗"}</div>
              <h2>${esc(error.title || "Unable to load")}</h2>
              <p>${esc(error.message || "This share link may have expired or been revoked.")}</p>
              ${isExpired ? `
                <p style="margin-top:var(--space-md);font-size:var(--font-size-sm);">
                  The note may have been deleted, the share link may have expired, or the owner may have revoked access.
                </p>
              ` : ""}
              <div style="margin-top:var(--space-lg);">
                <a href="/projects/note-manager/" class="btn btn-primary">Go to Note Manager</a>
              </div>
            </div>
          </div>
        `);
        return;
      }

      render(`
        <div style="min-height:100vh;background:var(--bg-primary);">
          <div class="share-container">
            <div class="share-header">
              <h1 class="share-title">${esc(note.title || "Untitled")}</h1>
              <div class="share-meta">
                By <strong>${esc(note.author ? note.author.username : "unknown")}</strong>
                ${note.created_at ? " · " + fmtDate(note.created_at) : ""}
                ${note.updated_at && note.updated_at !== note.created_at ? " · Updated " + fmtDate(note.updated_at) : ""}
              </div>
            </div>
            <div class="share-content">
              <div class="preview-content">${renderMarkdown(note.content_md || "")}</div>
            </div>
            <div style="text-align:center;padding:var(--space-2xl) 0;border-top:1px solid var(--border-color);margin-top:var(--space-2xl);">
              <p style="font-size:var(--font-size-xs);color:var(--text-muted);">
                📝 Shared via <a href="/projects/note-manager/">Note Manager</a>
              </p>
            </div>
          </div>
        </div>
      `);
    }

    async function init() {
      draw();
      try {
        note = await api.get("/public/notes/" + token);
        loading = false;
        draw();
      } catch (err) {
        loading = false;
        var title = "Share not available";
        var msg = err.message;
        if (err.status === 404) {
          msg = "This share link is no longer available.";
        }
        error = { title: title, message: msg, status: err.status };
        draw();
      }
    }

    init();
  }

  /* ═════════════════════════════════════════════════════════════
     Route Registration
     ═════════════════════════════════════════════════════════════ */

  router.on("/login", function () { authView(); });
  router.on("/register", function () { authView(); });
  router.on("/notes", function () { notesListView(); });
  router.on("/notes/new", function () { noteEditorView({ id: null }); });
  router.on("/notes/:id", function (params) { noteEditorView(params); });
  router.on("/share/:token", function (params) { shareView(params); });

  /* ═════════════════════════════════════════════════════════════
     Boot
     ═════════════════════════════════════════════════════════════ */

  router.init();
})();
