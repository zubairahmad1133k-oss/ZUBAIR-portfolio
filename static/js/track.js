// Records clicks on WhatsApp / email buttons. The link itself always works,
// even if this request fails. A click is NOT an enquiry; it only counts a click.
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  document.addEventListener('click', function (event) {
    var link = event.target.closest('[data-track]');
    if (!link) return;
    try {
      fetch('/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': meta.content },
        body: JSON.stringify({ type: 'contact_click', channel: link.dataset.track, path: location.pathname }),
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* never block the link */ }
  });
})();
