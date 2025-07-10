<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Unified Search | AddictionTube</title>
  <link rel="stylesheet" href="/css/style.css">
  <script src="/js/unified-search.js" defer></script>
</head>
<body>
  <div class="container">
    <h1>Unified Search: Songs, Poems, Stories</h1>
    <form id="searchForm">
      <input type="text" id="query" placeholder="Enter your search term..." required>
      <select id="category">
        <option value="song">song</option>
        <option value="poem">poem</option>
        <option value="story">story</option>
      </select>
      <button type="submit">Search</button>
    </form>
    <div id="results"></div>
  </div>
</body>
</html>