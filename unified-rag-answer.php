<?php
header('Content-Type: application/json');
$query = $_GET['q'] ?? '';
$category = $_GET['category'] ?? '';

if (!$query || !$category) {
  http_response_code(400);
  echo json_encode(['error' => 'Missing query or category']);
  exit;
}

$url = "https://addictiontube-unified.onrender.com/rag_answer?q=" . urlencode($query) .
       "&category_id=" . urlencode($category);

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
http_response_code(curl_getinfo($ch, CURLINFO_HTTP_CODE));
echo $response;