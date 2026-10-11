/**
 * app.js
 * ------
 * General UI enhancements: auto-dismiss flashes, smooth interactions.
 */

document.addEventListener('DOMContentLoaded', () => {

  // Auto-dismiss flash messages after 5 seconds
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });

  // Animate cards on load
  document.querySelectorAll('.group-card, .query-card, .reply-card').forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(12px)';
    el.style.transition = `opacity 0.3s ease ${i * 0.05}s, transform 0.3s ease ${i * 0.05}s`;
    requestAnimationFrame(() => {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });
  });

  // Drive link: warn if not a proper Drive URL
  const driveLinkInput = document.getElementById('drive_link');
  if (driveLinkInput) {
    driveLinkInput.addEventListener('blur', () => {
      const val = driveLinkInput.value.trim();
      if (val && !val.includes('drive.google.com') && !val.includes('docs.google.com')) {
        driveLinkInput.style.borderColor = 'var(--warning)';
        driveLinkInput.title = 'This does not look like a Google Drive link.';
      } else {
        driveLinkInput.style.borderColor = '';
      }
    });
  }

  // Textarea auto-resize
  document.querySelectorAll('textarea.input').forEach(ta => {
    ta.addEventListener('input', () => {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
  });

});
