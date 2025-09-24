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
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function heartFilledSvg() {
    return `<svg class="heart-svg filled" xmlns="http://www.w3.org/2000/svg" width="34" height="34" fill="red" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09
                       C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>`;
  }
  function heartEmptySvg() {
    return `<svg class="heart-svg empty" xmlns="http://www.w3.org/2000/svg" width="34" height="34" fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09
                       C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>`;
  }

  // ---------- création d'une card depuis la data JSON ----------
  function createPhotoCardFromData(photo) {
    // photo = { id, url, caption, uploader: { username, profile_photo, role }, likes_count, liked }
    const wrapper = document.createElement('div');
    wrapper.className = 'photo-card-wrapper';
    wrapper.dataset.photoId = photo.id;

    const uploader = photo.uploader || {};
    const uploaderName = escapeHtml(uploader.username || '');
    const uploaderPhoto = uploader.profile_photo || '/static/icons/default_profile.png';
    const caption = escapeHtml(photo.caption || '');

    const html = `
      <div class="photo-card">
        <div class="photo-image-container">
          <img src="${photo.url || ''}" alt="${caption}">
          <div class="user-info-overlay">
            <div class="profile-photo small">
              <img src="${uploaderPhoto}" alt="${uploaderName}">
            </div>
            <div class="details small">
              <p class="uploader-line">
                ${uploaderName}
                ${uploader.role === 'Creator' ? '<span class="creator-badge" aria-hidden="true">✔</span>' : ''}
              </p>
              <div class="date small">${photo.date_created ? escapeHtml(new Date(photo.date_created).toLocaleString()) : ''}</div>
            </div>
          </div>
        </div>
        <div class="photo-info">
          <p class="caption">${caption}</p>
        </div>
        <div class="photo-actions">
          <div class="action likes">
            <span class="likes-count">${photo.likes_count ?? 0}</span>
            <button class="like-btn ${photo.liked ? 'liked' : ''}" title="J'aime" type="button">
              ${photo.liked ? heartFilledSvg() : heartEmptySvg()}
            </button>
          </div>
        </div>
      </div>
    `;
    wrapper.innerHTML = html;
    return wrapper;
  }

  // ---------- like buttons ----------
  function initLikeButtons(root = document) {
  const likeSound = document.getElementById('likeSound');
  root.querySelectorAll('.like-btn').forEach(btn => {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const wrapper = btn.closest('.photo-card-wrapper');
      if (!wrapper) return;
      const photoId = wrapper.dataset.photoId;
      const csrftoken = getCookie('csrftoken');

      if (likeSound) {
        try { likeSound.currentTime = 0; likeSound.play(); } catch (err) {}
      }

      try {
        const res = await fetch(`/photo/${photoId}/like/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrftoken,
            'Accept': 'application/json',
          },
        });
        if (!res.ok) throw new Error('Network error');
        const data = await res.json();
        btn.innerHTML = data.liked ? heartFilledSvg() : heartEmptySvg();
        const countEl = wrapper.querySelector('.likes-count');
        if (countEl) countEl.textContent = data.likes_count;
        btn.classList.toggle('liked', !!data.liked);
      } catch (err) {
        console.error('Like failed', err);
      }
    });
  });
}

  // ---------- infinite scroll ----------
  let loading = false;
  let hasNext = true;
  const feed = document.getElementById('feed-container');
  const loader = document.getElementById('feed-loader');
  const feedUrl = (window.location.pathname && window.location.pathname !== '') ? window.location.pathname : '/';

  if (!feed) {
    console.warn('feed container not found (#feed-container). Infinite loader disabled.');
  }

  let offset = 0;
  const initialOffsetAttr = feed && feed.dataset ? parseInt(feed.dataset.initialOffset || '0', 10) : 0;
  offset = Number.isNaN(initialOffsetAttr) ? 0 : initialOffsetAttr;
  const limit = 20;

  async function loadNextBatch() {
    if (loading || !hasNext || !feed) return;
    loading = true;
    if (loader) loader.style.display = 'flex';

    try {
      const url = `${feedUrl}?offset=${offset}&limit=${limit}`;
      const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) {
        // if 404 or other, stop trying further
        console.warn('Fetch batch failed', res.status);
        hasNext = false;
        return;
      }
      const data = await res.json();

      const photos = Array.isArray(data.photos) ? data.photos : (Array.isArray(data.items) ? data.items : []);
      for (const p of photos) {
        const card = createPhotoCardFromData({
          id: p.id,
          url: p.url,
          caption: p.caption,
          uploader: p.uploader,
          likes_count: p.likes_count,
          liked: !!p.liked,
          date_created: p.date_created
        });
        feed.appendChild(card);
      }

      // bind like buttons for new cards
      initLikeButtons(feed);

      // advance offset
      offset += photos.length;

      // prefer explicit has_next from server
      if (typeof data.has_next !== 'undefined') {
        hasNext = !!data.has_next;
      } else {
        hasNext = photos.length >= limit;
      }
    } catch (err) {
      console.error('fetch next batch failed', err);
      // on erreur réseau on peut réessayer plus tard; pour éviter boucles infinies on stoppe
      hasNext = false;
    } finally {
      if (loader) loader.style.display = 'none';
      loading = false;
    }
  }

  // déclenche le chargement quand on est proche du bas
  function onScroll() {
    if (!feed) return;
    const distanceFromBottom = document.documentElement.scrollHeight - (window.innerHeight + window.scrollY);
    // ajuster seuil px selon tes écrans ; ~800px = 5 cartes d'avance sur desktop
    if (distanceFromBottom < 800) {
      loadNextBatch();
    }
  }

  // ---------- profile modal ----------
  function initProfileModal() {
    const modal = document.getElementById('profileModal');
    if (!modal) return;
    const fileInput = document.getElementById('profilePhotoInput');
    const importBtn = document.getElementById('importBtn');
    const previewImage = document.getElementById('previewImage');
    const currentPhoto = document.getElementById('currentPhoto');

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    importBtn && importBtn.addEventListener('click', () => fileInput && fileInput.click());
    fileInput && fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (previewImage) {
          previewImage.src = ev.target.result;
          previewImage.classList.remove('hidden');
        }
        if (currentPhoto) currentPhoto.classList.add('hidden');
      };
      reader.readAsDataURL(file);
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
      }
    });
  }

  // ---------- boot ----------
  document.addEventListener('DOMContentLoaded', () => {
    initLikeButtons();            // bind existant
    initProfileModal();          // modal si présent
    window.addEventListener('scroll', throttle(onScroll, 150));

    // si la page a été rendue serveur (photos déjà présents), offset vaut déjà leur nombre;
    // sinon on déclenche un fetch initial
    const hasServerPhotos = feed && feed.children && feed.children.length > 0;
    if (!hasServerPhotos && offset === 0) {
      loadNextBatch();
    }
  });
})();