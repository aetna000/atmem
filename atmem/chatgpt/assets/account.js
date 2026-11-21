// The desktop client owns its loopback response. Keep the user's foreground
// tab on AtMem while the original sign-in tab returns control to the client.
const form = document.querySelector('form[data-native]');
if (form) form.addEventListener('submit', async (event) => {
  if (event.submitter?.value !== 'approve') return;
  const confirmation = window.open('about:blank', '_blank');
  if (!confirmation) return; // Standard OAuth navigation when popups are blocked.
  event.preventDefault();
  confirmation.opener = null;
  confirmation.document.title = 'Connecting to AtMem';
  confirmation.document.head.append(document.querySelector('style').cloneNode(true));
  const shell = confirmation.document.createElement('div');
  shell.className = 'shell';
  const card = confirmation.document.createElement('main');
  card.append(document.querySelector('.brand').cloneNode(true));
  const title = confirmation.document.createElement('h1');
  title.textContent = 'Connecting to Codex…';
  card.append(title); shell.append(card); confirmation.document.body.append(shell);
  const submit = event.submitter;
  const feedback = document.querySelector('#feedback');
  submit.disabled = true;
  feedback.textContent = '';
  try {
    const data = new FormData(form);
    data.set('decision', 'approve');
    const response = await fetch(form.action, {method:'POST',body:data,headers:{Accept:'application/json'}});
    if (!response.ok) throw new Error(response.status === 403 ? 'Sign-in was unsuccessful. Check your account details or start a new connection.' : 'This connection has expired. Start again from your chat.');
    const result = await response.json();
    form.querySelector('input[type=password]').value = '';
    confirmation.location.replace('/connection/complete');
    window.location.replace(result.callback);
  } catch (err) {
    confirmation.close();
    feedback.textContent = err.message || 'Could not connect. Please try again.';
    submit.disabled = false;
  }
});

const progress = document.querySelector('[data-connection-status]');
async function confirmConnection() {
  for (let attempt = 0; attempt < 50; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    try {
      const response = await fetch(progress.dataset.connectionStatus, {cache:'no-store'});
      if (response.ok && (await response.json()).connected) {
        window.location.reload();
        return;
      }
    } catch { /* A transient network error can be retried during the handoff. */ }
  }
  document.querySelector('h1').textContent = 'Connection unconfirmed';
  progress.textContent = 'Return to your chat and choose Reconnect to try again.';
}
if (progress) confirmConnection();
