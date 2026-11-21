const consent = document.querySelector('form[data-web-consent]');
if (consent) {
  let submitting = false;
  consent.addEventListener('submit', event => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    submitting = true;
  });
  window.addEventListener('pageshow', () => { submitting = false; });
}

const callback = document.querySelector('[data-oauth-callback]');
if (callback) window.location.replace(callback.href);
