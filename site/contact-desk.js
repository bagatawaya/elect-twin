(() => {
  const form = document.getElementById('contact-form');
  if (!form) return;
  const status = document.getElementById('contact-result');
  const fallback = document.getElementById('contact-payload');
  const email = document.getElementById('contact-email');
  function payload() {
    const fields = new FormData(form);
    return `OpenTwin + OpenZoo inquiry\n\nName / Outlet or Channel: ${fields.get('name')}\nEmail or Social Handle: ${fields.get('contact')}\nInquiry Type: ${fields.get('type')}\n\n${fields.get('message')}\n\nPrepared locally. Not submitted by this website.`;
  }
  function updateEmail() {
    email.href = 'mailto:j@electri.ai?subject=' + encodeURIComponent('OpenTwin + OpenZoo inquiry: ' + new FormData(form).get('type')) + '&body=' + encodeURIComponent(payload());
  }
  form.addEventListener('input', updateEmail);
  form.addEventListener('change', updateEmail);
  email.addEventListener('click', event => {
    if (!form.reportValidity()) { event.preventDefault(); return; }
    updateEmail();
    status.textContent = 'Your email app will open a draft to j@electri.ai. Review it and send it there. This website has not sent the inquiry.';
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const text = payload();
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = 'Inquiry copied. It has not been sent. Paste it into an email to j@electri.ai, then review and send.';
    } catch {
      fallback.value = text;
      fallback.hidden = false;
      fallback.focus();
      fallback.select();
      status.textContent = 'Copy is unavailable. Your inquiry is selected below. Copy it into an email to j@electri.ai, then review and send. Nothing has been sent.';
    }
  });
  updateEmail();
})();
