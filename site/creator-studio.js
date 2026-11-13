/* Local-only human reactions for renderer-generated Creator Studio samples. */
(function () {
  'use strict';

  function storageKey(receipt, vote) {
    return 'openzoo_studio_' + vote + '_' + receipt;
  }

  function readVote(receipt, vote) {
    try {
      const value = Number.parseInt(window.localStorage.getItem(storageKey(receipt, vote)) || '0', 10);
      return Number.isSafeInteger(value) && value >= 0 ? value : 0;
    } catch (error) {
      return 0;
    }
  }

  function saveVote(receipt, vote, value) {
    try {
      window.localStorage.setItem(storageKey(receipt, vote), String(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  document.querySelectorAll('.creator-studio-sample').forEach(function (figure) {
    const receipt = figure.getAttribute('data-receipt');
    if (!/^[0-9a-f]{64}$/.test(receipt || '')) return;
    const status = figure.querySelector('.creator-studio-status');

    figure.querySelectorAll('button[data-studio-vote]').forEach(function (button) {
      const vote = button.getAttribute('data-studio-vote');
      if (!['appreciate', 'curious', 'remix'].includes(vote)) return;
      if (button.getAttribute('data-receipt') !== receipt) return;
      const count = button.querySelector('.studio-vote-count');
      count.textContent = String(readVote(receipt, vote));

      button.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        const next = readVote(receipt, vote) + 1;
        const persisted = saveVote(receipt, vote, next);
        count.textContent = String(next);
        button.classList.remove('studio-vote-pop');
        void button.offsetWidth;
        button.classList.add('studio-vote-pop');
        const label = vote === 'appreciate' ? 'Appreciation' : vote === 'curious' ? 'Curiosity' : 'Remix interest';
        status.textContent = label + ' counted for receipt ' + receipt.slice(0, 12) + '… · ' +
          (persisted ? 'Saved only in this browser; not sent to a room.' : 'Counted on this page only; browser storage is unavailable.');
      });
    });
  });
}());
