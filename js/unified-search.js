document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('searchForm');
  const resultsDiv = document.getElementById('results');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = document.getElementById('query').value.trim();
    const category = document.getElementById('category').value;

    if (!query) return;

    resultsDiv.innerHTML = '<p>Searching...</p>';

    try {
      const res = await fetch(`/unified/unified-search-proxy.php?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`);
      const data = await res.json();

      if (data.error) {
        resultsDiv.innerHTML = `<p>Error: ${data.error}</p>`;
        return;
      }

      if (data.results.length === 0) {
        resultsDiv.innerHTML = '<p>No results found.</p>';
        return;
      }

      const html = data.results.map(item => `
        <div class="result-item">
          <h3>${item.title}</h3>
          <p>${item.description}</p>
          <small>Score: ${item.score.toFixed(4)} | Type: ${item.category_id}</small>
        </div>
      `).join('');

      resultsDiv.innerHTML = html;
    } catch (err) {
      resultsDiv.innerHTML = `<p>Error fetching results.</p>`;
    }
  });
});
