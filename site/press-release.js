(() => {
  const button = document.getElementById('copy-press-release');
  const source = document.getElementById('press-copy-source');
  const status = document.getElementById('press-copy-status');
  if (!button || !source || !status) return;
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(source.value);
      status.textContent = 'Press release copied.';
    } catch {
      source.hidden = false;
      source.focus();
      source.select();
      status.textContent = 'Copy is unavailable in this browser. The full release is selected below so you can copy it manually.';
    }
  });
})();
