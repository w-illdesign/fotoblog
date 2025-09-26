// static/js/home.js
(() => {
  // ---------- utilitaires ----------
  function throttle(fn, wait) {
    let last = 0;
    return function () {
      const now = Date.now();
      if (now - last >= wait) {
        last = now;
        fn.apply(this, arguments);
      }
    };
  }

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ---------- SVG helpers (identiques au template) ----------
  function heartFilledSvg() {
    return `<svg class="heart-svg filled" xmlns="http://www.w3.org/2000/svg" fill="red" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09
                       C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>`;
  }
  function heartEmptySvg() {
    return `<svg class="heart-svg empty" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09
                       C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>`;
  }

  const creatorBadgeSvg = `
    <svg class="creator-badge" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-label="Creator badge">
      <defs>
        <linearGradient id="gCreator" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="#3AB0FF"/>
          <stop offset="1" stop-color="#1DA1F2"/>
        </linearGradient>
        <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#0b76c9" flood-opacity="0.35"/>
        </filter>
      </defs>
      <circle cx="12" cy="12" r="11.2" fill="url(#gCreator)" filter="url(#shadow)" />
      <path d="M8.6 12.2 L11 14.6 L15.6 9.8" fill="none" stroke="#fff" stroke-width="2.2"/>
    </svg>`;

  // ---------- création d'une card conforme au template Django ----------
  function createPhotoCardFromData(photo) {
    const wrapper = document.createElement("div");
    wrapper.className = "photo-card-wrapper";
    wrapper.setAttribute("data-photo-id", String(photo.id));

    const uploader = photo.uploader || {};
    const uploaderUsername = uploader.username || "";
    const uploaderProfileUrl = uploader.profile_url || `/user/${encodeURIComponent(uploaderUsername)}/`;
    const uploaderProfilePhoto = uploader.profile_photo || "/static/icons/default_profile.png";

    let dateHtml = "";
    if (photo.date_facebook) {
      dateHtml = escapeHtml(photo.date_facebook);
    } else if (photo.date_created) {
      try {
        dateHtml = escapeHtml(new Date(photo.date_created).toLocaleString());
      } catch (e) {
        dateHtml = escapeHtml(String(photo.date_created));
      }
    }

    const caption = escapeHtml(photo.caption || "");
    const likesCount = Number.isFinite(photo.likes_count) ? photo.likes_count : Number(photo.likes_count || 0);
    const isLiked = !!photo.liked;
    const relatedBlog = photo.related_blog || null;

    const relatedHtml = relatedBlog && relatedBlog.id
      ? `<a href="/blog/${encodeURIComponent(relatedBlog.id)}/" class="photo-card-link">${escapeHtml(relatedBlog.title)} <span class="link-lire">... Lire</span></a>`
      : caption;

    const html = `
      <div class="photo-card">
        <div class="photo-image-container">
          <img src="${escapeHtml(photo.url || '')}" alt="${caption}" loading="lazy">
            <a href="${escapeHtml(uploaderProfileUrl)}"  class="user-info-overlay">
            <div class="profile-photo small">
              <a href="${escapeHtml(uploaderProfileUrl)}">
                <img src="${escapeHtml(uploaderProfilePhoto)}" alt="${escapeHtml(uploaderUsername)}" loading="lazy">
              </a>
            </div>
            <div class="details small">
              <p class="uploader-line">
              ${escapeHtml(uploaderUsername)}
                ${uploader.role === "Creator" ? creatorBadgeSvg : ""}
              </p>
              <div class="date small">${dateHtml}</div>
            </div>
          </a>
        </div>

        <div class="photo-info">
          <p class="caption">${relatedHtml}</p>
        </div>

        <div class="photo-actions">
          <div class="action comments">
            <button class="comment-btn" title="Commenter" type="button">
              <span class="comments-count">2K</span>
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </button>
          </div>

          <div class="action comments">
            <button class="comment-btn" title="Partager" type="button">
              <span class="comments-count">5</span>
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </button>
          </div>

          <div class="action likes">
            <span class="likes-count">${escapeHtml(String(likesCount))}</span>
            <button class="like-btn ${isLiked ? "liked" : ""}" title="J'aime" type="button" data-photo-id="${escapeHtml(String(photo.id))}">
              ${isLiked ? heartFilledSvg() : heartEmptySvg()}
            </button>
          </div>
        </div>
      </div>
    `;

    wrapper.innerHTML = html;
    return wrapper;
  }

  // ---------- like buttons (AJAX) ----------
  function initLikeButtons(root = document) {
    const likeSound = document.getElementById("likeSound");
    const scope = root || document;
    scope.querySelectorAll(".like-btn").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";

      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        const wrapper = btn.closest(".photo-card-wrapper");
        if (!wrapper) return;
        const photoId = wrapper.getAttribute("data-photo-id");
        if (!photoId) return;
        const csrftoken = getCookie("csrftoken");

        if (likeSound) {
          try { likeSound.currentTime = 0; likeSound.play(); } catch (err) {}
        }

        try {
          const res = await fetch(`/photo/${encodeURIComponent(photoId)}/like/`, {
            method: "POST",
            headers: {
              "X-CSRFToken": csrftoken,
              "Accept": "application/json",
            },
          });
          if (!res.ok) throw new Error("Network error");
          const data = await res.json();

          btn.innerHTML = data.liked ? heartFilledSvg() : heartEmptySvg();
          const countEl = wrapper.querySelector(".likes-count");
          if (countEl && typeof data.likes_count !== "undefined") countEl.textContent = data.likes_count;
          btn.classList.toggle("liked", !!data.liked);
        } catch (err) {
          console.error("Like failed", err);
        }
      });
    });
  }

  // ---------- infinite scroll replaced by "Voir plus" ----------
  let loading = false;
  let hasNext = true;
  const feed = document.getElementById("feed-container");
  const loader = document.getElementById("feed-loader");
  const loadMoreBtn = document.getElementById("voirPlusBtn"); // bouton "Voir plus"
  const feedUrl = (window.location.pathname && window.location.pathname !== "") ? window.location.pathname : "/";
  if (!feed) console.warn("feed container not found (#feed-container). Loader and 'Voir plus' will be disabled.");

  let offset = 0;
  const initialOffsetAttr = feed && feed.dataset ? parseInt(feed.dataset.initialOffset || feed.dataset.initialOffset || "0", 10) : 0;
  offset = Number.isNaN(initialOffsetAttr) ? 0 : initialOffsetAttr;
  const limit = 20;

  function updateLoadMoreButton() {
    if (!loadMoreBtn) return;
    // si aucune suite, cacher le bouton
    if (!hasNext) {
      loadMoreBtn.style.display = "none";
      return;
    }
    // sinon l'afficher
    loadMoreBtn.style.display = "inline-block";
    loadMoreBtn.disabled = loading;
  }

  async function loadNextBatch() {
    if (loading || !hasNext || !feed) return;
    loading = true;
    updateLoadMoreButton();
    if (loader) loader.style.display = "flex";

    try {
      const url = `${feedUrl}?offset=${offset}&limit=${limit}`;
      const res = await fetch(url, { headers: { "Accept": "application/json" } });
      if (!res.ok) {
        console.warn("Fetch batch failed", res.status);
        hasNext = false;
        return;
      }
      const data = await res.json();
      const photos = Array.isArray(data.photos) ? data.photos : Array.isArray(data.items) ? data.items : [];

      for (const p of photos) {
        const card = createPhotoCardFromData({
          id: p.id,
          url: p.url,
          caption: p.caption,
          uploader: p.uploader,
          likes_count: p.likes_count,
          liked: !!p.liked,
          date_created: p.date_created,
          date_facebook: p.date_facebook,
          related_blog: p.related_blog,
        });
        feed.appendChild(card);
      }

      // bind like buttons for new cards
      initLikeButtons(feed);

      // advance offset
      offset += photos.length;

      if (typeof data.has_next !== "undefined") {
        hasNext = !!data.has_next;
      } else {
        hasNext = photos.length >= limit;
      }
    } catch (err) {
      console.error("fetch next batch failed", err);
      hasNext = false;
    } finally {
      if (loader) loader.style.display = "none";
      loading = false;
      updateLoadMoreButton();
    }
  }

  // ---------- profile modal ----------
  function initProfileModal() {
    const modal = document.getElementById("profileModal");
    if (!modal) return;
    const fileInput = document.getElementById("profilePhotoInput");
    const importBtn = document.getElementById("importBtn");
    const previewImage = document.getElementById("previewImage");
    const currentPhoto = document.getElementById("currentPhoto");

    modal.style.display = "flex";
    document.body.style.overflow = "hidden";

    importBtn && importBtn.addEventListener("click", () => fileInput && fileInput.click());
    fileInput && fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (previewImage) {
          previewImage.src = ev.target.result;
          previewImage.classList.remove("hidden");
        }
        if (currentPhoto) currentPhoto.classList.add("hidden");
      };
      reader.readAsDataURL(file);
    });

    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.style.display = "none";
        document.body.style.overflow = "";
      }
    });
  }

  // ---------- boot ----------
  document.addEventListener("DOMContentLoaded", () => {
    initLikeButtons(); // bind existing server-rendered buttons
    initProfileModal(); // modal si présent

    // Remplace le scroll infini par un bouton "Voir plus"
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", (e) => {
        e.preventDefault();
        loadNextBatch();
      });
    } else {
      console.warn("'Voir plus' button (#voirPlusBtn) not found — nothing will trigger loading more items.");
    }

    // s'assurer que le bouton est à jour (masqué si pas de suite)
    updateLoadMoreButton();

    // IMPORTANT: on ne lance pas automatiquement loadNextBatch ici.
    // Si tu veux charger automatiquement la première page quand il n'y a rien côté serveur,
    // décommente la ligne suivante :
    // if ((!feed || feed.children.length === 0) && offset === 0) loadNextBatch();
  });
})();