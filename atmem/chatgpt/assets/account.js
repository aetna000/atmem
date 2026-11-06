// For native OAuth, keep the branded tab visible while Codex receives its callback.
const form = document.querySelector('form[data-native]');
if (form) form.addEventListener('submit', async (event) => {
  if (event.submitter?.value !== 'approve') return;
  const handoff = window.open('about:blank', '_blank', 'popup,width=440,height=260');
  if (!handoff) return; // Browser popup policy: use the standard OAuth navigation.
  event.preventDefault();
  handoff.opener = null;
  handoff.document.title = 'Connecting to AtMem';
  handoff.document.body.textContent = 'Connecting to AtMem…';
  const submit = event.submitter;
  const feedback = document.querySelector('#feedback');
  const heading = document.querySelector('h1');
  submit.disabled = true;
  feedback.textContent = '';
  let accepted = false;
  try {
    const data = new FormData(form);
    data.set('decision', 'approve');
    const response = await fetch(form.action, {method:'POST',body:data,headers:{Accept:'application/json'}});
    if (!response.ok) throw new Error(response.status === 403 ? 'Sign-in was unsuccessful. Check your account details or start a new connection.' : 'This connection has expired. Start again from your chat.');
    const result = await response.json();
    accepted = true;
    form.querySelector('input[type=password]').value = '';
    document.querySelector('#login').hidden = true;
    heading.textContent = 'Connecting to Codex…';
    const progress = document.querySelector('#progress');
    progress.hidden = false;
    handoff.location.replace(result.callback);
    for (let attempt = 0; attempt < 50; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const status = await fetch(result.status, {cache:'no-store'});
      if (status.ok && (await status.json()).connected) {
        handoff.close();
        window.location.replace('/connection/complete');
        return;
      }
    }
    throw new Error('AtMem could not confirm the connection. Return to your chat and choose Reconnect to try again.');
  } catch (err) {
    handoff.close();
    if (accepted) {
      heading.textContent = 'Connection unconfirmed';
      document.querySelector('#progress').hidden = true;
    }
    feedback.textContent = err.message || 'Could not connect. Please try again.';
  } finally {
    submit.disabled = false;
  }
});
