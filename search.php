<?php
header('Content-Type: application/json');

$query = $_GET['q'] ?? '';
$category = $_GET['category'] ?? '';
$page = $_GET['page'] ?? 1;
$perPage = $_GET['per_page'] ?? 5;

if (empty($query) || empty($category)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing query or category']);
    exit;
}

$apiUrl = "https://addictiontube-proxy.onrender.com/search?q=" . urlencode($query) . "&category_id=" . urlencode($category) . "&page=$page&per_page=$perPage";

$ch = curl_init($apiUrl);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);

echo $response;
