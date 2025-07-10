<?php
header('Content-Type: application/json');

$query = $_GET['q'] ?? '';
$category = $_GET['category'] ?? '';

if (empty($query) || empty($category)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing query or category']);
    exit;
}

$apiUrl = "https://addictiontube-proxy.onrender.com/rag_answer?q=" . urlencode($query) . "&category_id=" . urlencode($category);

$ch = curl_init($apiUrl);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);

echo $response;
