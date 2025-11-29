// static/script.js
document.addEventListener("DOMContentLoaded", () => {
  /* ------------------ Image Preview (Your Existing Code) ------------------ */
  const input = document.getElementById('fileInput');
  const preview = document.getElementById('preview');
  const uploadBtn = document.getElementById('uploadBtn');

  if (input) {
    input.addEventListener('change', () => {
      const file = input.files[0];
      if (!file) {
        preview.innerHTML = '<span style="color:#777">Image preview will appear here</span>';
        return;
      }

      const allowed = ['image/jpeg', 'image/png', 'image/jpg', 'image/bmp'];
      if (!allowed.includes(file.type)) {
        input.value = '';
        preview.innerHTML = '<span style="color:#777">Invalid file type</span>';
        return;
      }

      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      img.onload = () => URL.revokeObjectURL(img.src);
      preview.innerHTML = '';
      preview.appendChild(img);
    });
  }

  const form = document.getElementById('uploadForm');
  if (form) {
    form.addEventListener('submit', () => {
      uploadBtn.disabled = true;
      uploadBtn.textContent = 'Uploading…';
    });
  }

  /* ------------------ Recent Uploads — Click to open Gallery ------------------ */
  const historyList = document.getElementById('historyList');
  const allGalleryWrap = document.getElementById('allGalleryWrap');
  const allGallery = document.getElementById('allGallery');

  if (!historyList || !allGalleryWrap || !allGallery) return;

  // Remove old highlights
  function clearHighlight() {
    document.querySelectorAll(".gallery-thumb").forEach(t => {
      t.style.border = "none";
      t.style.transform = "none";
    });
  }

  // Highlight a given image
  function highlightImage(imgUrl) {
    clearHighlight();
    const thumbs = document.querySelectorAll(".gallery-thumb img");
    thumbs.forEach(img => {
      if (img.src.includes(imgUrl)) {
        img.parentElement.style.border = "2px solid #2b7a2b";
        img.parentElement.style.transform = "scale(1.05)";
      }
    });
  }

  // Handle click on history boxes
  historyList.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      let isVisible = allGalleryWrap.style.display === 'block';
      allGalleryWrap.style.display = isVisible ? 'none' : 'block';

      // When it's opening, highlight the clicked one
      if (!isVisible) {
        const imgUrl = item.getAttribute("data-img");
        highlightImage(imgUrl);

        // Smooth scroll
        setTimeout(() => {
          allGalleryWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    });
  });

  // Clicking "View" link does same
  historyList.querySelectorAll('.view-all-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      allGalleryWrap.style.display = "block";
    });
  });
});
