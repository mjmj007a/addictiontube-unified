<?php
header('Content-Type: application/json');
error_reporting(E_ALL);
ini_set('display_errors', 1);

$query = $_GET['q'] ?? '';
$category = $_GET['category'] ?? '';

if (empty($query) || empty($category)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing query or category']);
    exit;
}

$apiUrl = "https://addictiontube-unified.onrender.com/search?q=" . urlencode($query) . "&category_id=" . urlencode($category);

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $apiUrl);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);

$response = curl_exec($ch);
if (curl_errno($ch)) {
    http_response_code(500);
    echo json_encode(['error' => 'CURL Error', 'details' => curl_error($ch)]);
    curl_close($ch);
    exit;
}

curl_close($ch);
echo $response;
