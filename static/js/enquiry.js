// After sending (or failing) the enquiry form, bring the result message into view.
(function () {
  var status = document.getElementById('enquiry-status');
  if (status) status.scrollIntoView({ block: 'center' });
})();
