window.addEventListener('load', async function() {
  const chatkit = document.getElementById('chatkit-element');

  // Fetch client token from backend
  const response = await fetch('/api/chatkit/session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  const { client_secret } = await response.json();

  chatkit.setOptions({
    api: {
      clientToken: client_secret
    }
  });
});
