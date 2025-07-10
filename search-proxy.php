// search-proxy.php
header('Content-Type: application/json');

$query = $_GET['q'] ?? '';
$category = $_GET['category'] ?? '';
$reroll = $_GET['reroll'] ?? 'no';

if (empty($query) || empty($category)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing query or category']);
    exit;
}

$url = "https://your-backend-domain.com/rag_answer?q=" . urlencode($query) . "&category_id=" . urlencode($category);
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);

echo $response;
