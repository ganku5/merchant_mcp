"""
PHP SDK Templates for IBMB Integration
Supports: Standard cURL, Guzzle (popular PHP HTTP client)
"""

PHP_SDK_TEMPLATE = '''
<?php
/**
 * IBMB Payment PHP SDK
 * 
 * @package IbmbPayment
 * @author Merchant Integration Team
 * @version 1.0.0
 */

namespace IbmbPayment;

use Exception;
use RuntimeException;

/**
 * IBMB API Client
 */
class Client
{
    private string $baseUrl;
    private string $apiKey;
    private string $merchantId;
    private int $timeout;

    /**
     * Constructor
     * 
     * @param string $baseUrl API base URL
     * @param string $apiKey API key
     * @param string $merchantId Merchant ID
     * @param int $timeout Request timeout in seconds
     */
    public function __construct(
        string $baseUrl,
        string $apiKey,
        string $merchantId,
        int $timeout = 30
    ) {
        $this->baseUrl = rtrim($baseUrl, '/');
        $this->apiKey = $apiKey;
        $this->merchantId = $merchantId;
        $this->timeout = $timeout;
    }

    /**
     * Initiate a UPI transaction
     * 
     * @param string $payeeVpa Merchant VPA
     * @param string $payerVpa Customer VPA
     * @param string $amount Transaction amount
     * @param string $merchantRequestId Unique request ID
     * @param string $txnType Transaction type (COLLECT or PAY)
     * @param array $extra Extra parameters
     * @return array API response
     * @throws IbmbApiException on API error
     */
    public function initiateTransaction(
        string $payeeVpa,
        string $payerVpa,
        string $amount,
        string $merchantRequestId,
        string $txnType = 'COLLECT',
        array $extra = []
    ): array {
        $payload = array_merge([
            'payeeVpaHandle' => $payeeVpa,
            'payerVpaHandle' => $payerVpa,
            'amount' => $amount,
            'merchantRequestId' => $merchantRequestId,
            'merchantId' => $this->merchantId,
            'upiTxnType' => $txnType,
            'currency' => 'INR',
        ], $extra);

        return $this->makeRequest('POST', '/api/merchants/v1/transaction/initiate', $payload);
    }

    /**
     * Get transaction status
     * 
     * @param string $merchantRequestId Request ID
     * @param string|null $upiTxnId UPI transaction ID
     * @return array API response
     * @throws IbmbApiException
     */
    public function getTransactionStatus(
        string $merchantRequestId,
        ?string $upiTxnId = null
    ): array {
        $payload = [
            'merchantId' => $this->merchantId,
            'merchantRequestId' => $merchantRequestId,
        ];

        if ($upiTxnId !== null) {
            $payload['upiTxnId'] = $upiTxnId;
        }

        return $this->makeRequest('POST', '/api/merchants/v1/transaction/status', $payload);
    }

    /**
     * Create a refund
     * 
     * @param string $orderId Original order ID
     * @param string $uniqueRequestId Unique refund request ID
     * @param string|null $amount Refund amount (null for full)
     * @param string|null $reason Refund reason
     * @return array API response
     * @throws IbmbApiException
     */
    public function createRefund(
        string $orderId,
        string $uniqueRequestId,
        ?string $amount = null,
        ?string $reason = null
    ): array {
        $payload = [
            'orderId' => $orderId,
            'uniqueRequestId' => $uniqueRequestId,
        ];

        if ($amount !== null) {
            $payload['amount'] = $amount;
        }
        if ($reason !== null) {
            $payload['reason'] = $reason;
        }

        return $this->makeRequest('POST', '/api/merchants/v1/refund', $payload);
    }

    /**
     * Make HTTP request
     * 
     * @param string $method HTTP method
     * @param string $endpoint API endpoint
     * @param array $data Request data
     * @return array Response data
     * @throws IbmbApiException
     */
    private function makeRequest(string $method, string $endpoint, array $data = []): array
    {
        $url = $this->baseUrl . $endpoint;
        $jsonData = json_encode($data);

        $ch = curl_init();

        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_POSTFIELDS => $jsonData,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'Accept: application/json',
                'X-API-Key: ' . $this->apiKey,
            ],
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_FOLLOWLOCATION => true,
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);

        curl_close($ch);

        if ($error) {
            throw new RuntimeException('cURL Error: ' . $error);
        }

        $decoded = json_decode($response, true);

        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new RuntimeException('JSON Decode Error: ' . json_last_error_msg());
        }

        if ($httpCode !== 200 || ($decoded['result'] ?? '') !== 'SUCCESS') {
            throw new IbmbApiException(
                $decoded['responseCode'] ?? 'UNKNOWN',
                $decoded['responseMessage'] ?? 'Unknown error',
                $httpCode
            );
        }

        return $decoded;
    }
}

/**
 * IBMB API Exception
 */
class IbmbApiException extends Exception
{
    private string $errorCode;
    private int $httpCode;

    public function __construct(string $errorCode, string $message, int $httpCode = 0)
    {
        parent::__construct($message, $httpCode);
        $this->errorCode = $errorCode;
        $this->httpCode = $httpCode;
    }

    public function getErrorCode(): string
    {
        return $this->errorCode;
    }

    public function getHttpCode(): int
    {
        return $this->httpCode;
    }
}
'''

PHP_WEBHOOK_TEMPLATE = '''
<?php
/**
 * Webhook Handler for IBMB Events
 */

require_once 'vendor/autoload.php';

use Psr\\Http\\Message\\ResponseInterface as Response;
use Psr\\Http\\Message\\ServerRequestInterface as Request;
use Slim\\Factory\\AppFactory;

$app = AppFactory::create();

$app->post('/webhook', function (Request $request, Response $response) {
    // Get raw body
    $body = (string) $request->getBody();
    
    // Get signature
    $signature = $request->getHeaderLine('X-Juspay-Signature');
    
    if (empty($signature)) {
        return $response->withStatus(401)->write('Missing signature');
    }
    
    // Verify signature
    $webhookSecret = $_ENV['WEBHOOK_SECRET'];
    if (!verifySignature($body, $signature, $webhookSecret)) {
        return $response->withStatus(401)->write('Invalid signature');
    }
    
    // Parse event
    $event = json_decode($body, true);
    
    if (json_last_error() !== JSON_ERROR_NONE) {
        return $response->withStatus(400)->write('Invalid JSON');
    }
    
    // Process event asynchronously (queue it)
    // In production, use a proper job queue like RabbitMQ, Redis, etc.
    processEventAsync($event);
    
    // Return success immediately
    $response->getBody()->write(json_encode(['status' => 'ok']));
    return $response->withHeader('Content-Type', 'application/json');
});

/**
 * Verify webhook signature using HMAC-SHA256
 */
function verifySignature(string $payload, string $signature, string $secret): bool
{
    $expected = hash_hmac('sha256', $payload, $secret);
    return hash_equals($signature, $expected);
}

/**
 * Process event (should be done asynchronously in production)
 */
function processEventAsync(array $event): void
{
    $eventType = $event['event'] ?? 'unknown';
    
    switch ($eventType) {
        case 'order.charged':
            handlePaymentSuccess($event);
            break;
            
        case 'order.failed':
            handlePaymentFailure($event);
            break;
            
        case 'refund.processed':
            handleRefundProcessed($event);
            break;
            
        default:
            error_log("Unknown event type: $eventType");
    }
}

function handlePaymentSuccess(array $event): void
{
    $orderId = $event['order_id'] ?? null;
    // Fulfill order
    // Notify customer
    error_log("Payment successful for order: $orderId");
}

function handlePaymentFailure(array $event): void
{
    $orderId = $event['order_id'] ?? null;
    // Update order status
    // Notify customer
    error_log("Payment failed for order: $orderId");
}

function handleRefundProcessed(array $event): void
{
    $orderId = $event['order_id'] ?? null;
    // Update refund status
    // Notify customer
    error_log("Refund processed for order: $orderId");
}

$app->run();
'''

PHP_RETRY_TEMPLATE = '''
<?php
/**
 * Retry handler with exponential backoff
 */

namespace IbmbPayment;

use Exception;
use Throwable;

class RetryHandler
{
    private int $maxRetries;
    private float $baseDelay;
    private float $maxDelay;
    private array $retryableErrors;

    public function __construct(
        int $maxRetries = 3,
        float $baseDelay = 1.0,
        float $maxDelay = 30.0,
        array $retryableErrors = []
    ) {
        $this->maxRetries = $maxRetries;
        $this->baseDelay = $baseDelay;
        $this->maxDelay = $maxDelay;
        $this->retryableErrors = $retryableErrors ?: [
            'TIMEOUT',
            'RATE_LIMITED',
            'GATEWAY_ERROR',
            'SERVICE_UNAVAILABLE',
            'CONNECTION_ERROR',
        ];
    }

    /**
     * Execute callable with retry logic
     * 
     * @template T
     * @param callable(): T $operation
     * @return T
     * @throws Exception
     */
    public function execute(callable $operation)
    {
        $lastException = null;

        for ($attempt = 0; $attempt < $this->maxRetries; $attempt++) {
            try {
                return $operation();
            } catch (Throwable $e) {
                $lastException = $e;

                if (!$this->shouldRetry($e) || $attempt === $this->maxRetries - 1) {
                    throw $e;
                }

                $delay = $this->calculateDelay($attempt);
                usleep((int) ($delay * 1000000)); // Convert to microseconds
            }
        }

        throw $lastException;
    }

    private function shouldRetry(Throwable $e): bool
    {
        $message = $e->getMessage();
        
        foreach ($this->retryableErrors as $error) {
            if (strpos($message, $error) !== false) {
                return true;
            }
        }

        return false;
    }

    private function calculateDelay(int $attempt): float
    {
        // Exponential backoff: base * 2^attempt
        $delay = $this->baseDelay * pow(2, $attempt);
        
        // Add jitter (0-10%)
        $jitter = $delay * 0.1 * (mt_rand() / mt_getrandmax());
        $delay += $jitter;
        
        // Cap at max delay
        return min($delay, $this->maxDelay);
    }
}

// Usage:
// $handler = new RetryHandler();
// $result = $handler->execute(function() use ($client, $request) {
//     return $client->initiateTransaction(...);
// });
'''

PHP_GUZZLE_TEMPLATE = '''
<?php
/**
 * IBMB Client using Guzzle HTTP
 */

namespace IbmbPayment;

use GuzzleHttp\\Client as GuzzleClient;
use GuzzleHttp\\Exception\\RequestException;

class GuzzleClient
{
    private GuzzleClient $httpClient;
    private string $merchantId;

    public function __construct(string $baseUrl, string $apiKey, string $merchantId)
    {
        $this->merchantId = $merchantId;
        $this->httpClient = new GuzzleClient([
            'base_uri' => rtrim($baseUrl, '/') . '/',
            'timeout' => 30,
            'headers' => [
                'X-API-Key' => $apiKey,
                'Content-Type' => 'application/json',
                'Accept' => 'application/json',
            ],
        ]);
    }

    public function initiateTransaction(array $data): array
    {
        $data['merchantId'] = $this->merchantId;

        try {
            $response = $this->httpClient->post('api/merchants/v1/transaction/initiate', [
                'json' => $data,
            ]);

            return json_decode($response->getBody()->getContents(), true);
        } catch (RequestException $e) {
            $response = $e->getResponse();
            $body = $response ? json_decode($response->getBody()->getContents(), true) : [];
            
            throw new IbmbApiException(
                $body['responseCode'] ?? 'UNKNOWN',
                $body['responseMessage'] ?? $e->getMessage(),
                $response ? $response->getStatusCode() : 0
            );
        }
    }
}
'''

PHP_EXAMPLE_USAGE = '''
<?php
require_once 'vendor/autoload.php';

use IbmbPayment\\Client;
use IbmbPayment\\RetryHandler;

// Initialize client
$client = new Client(
    $_ENV['IBMB_BASE_URL'],
    $_ENV['IBMB_API_KEY'],
    $_ENV['IBMB_MERCHANT_ID']
);

// Create transaction with retry
$handler = new RetryHandler();

try {
    $response = $handler->execute(function() use ($client) {
        return $client->initiateTransaction(
            'merchant@juspay',
            'customer@okaxis',
            '1000.00',
            'ORDER_' . uniqid(),
            'COLLECT',
            ['description' => 'Payment for Order #12345']
        );
    });

    echo "Transaction initiated successfully!\\n";
    echo "Intent URL: " . $response['payload']['url'] . "\\n";
    
} catch (IbmbApiException $e) {
    echo "API Error: {$e->getErrorCode()} - {$e->getMessage()}\\n";
} catch (Exception $e) {
    echo "Error: {$e->getMessage()}\\n";
}

// Check transaction status
try {
    $status = $client->getTransactionStatus('ORDER_xxx', 'TXNyyy');
    echo "Status: " . $status['txnStatus'] . "\\n";
} catch (Exception $e) {
    echo "Failed to get status: {$e->getMessage()}\\n";
}
'''

# Composer dependencies
COMPOSER_JSON = '''
{
    "name": "merchant/ibmb-payment-sdk",
    "description": "PHP SDK for IBMB Payment API",
    "type": "library",
    "require": {
        "php": ">=7.4",
        "ext-curl": "*",
        "ext-json": "*",
        "ext-hash": "*"
    },
    "require-dev": {
        "phpunit/phpunit": "^9.0",
        "guzzlehttp/guzzle": "^7.0"
    },
    "autoload": {
        "psr-4": {
            "IbmbPayment\\\\": "src/"
        }
    }
}
'''

def generate_php_sdk(include_comments: bool = True, include_error_handling: bool = True) -> str:
    """Generate PHP SDK code (standard cURL version)."""
    sections = []
    
    if include_comments:
        sections.append("<?php")
        sections.append("/**")
        sections.append(" * IBMB Payment PHP SDK")
        sections.append(" * Standard PHP cURL (no external dependencies)")
        sections.append(" */")
        sections.append("")
    
    sections.append(PHP_SDK_TEMPLATE.strip())
    
    if include_error_handling:
        sections.append("")
        sections.append("/**")
        sections.append(" * Retry Handler")
        sections.append(" */")
        sections.append(PHP_RETRY_TEMPLATE.strip())
    
    return "\n\n".join(sections)

def generate_php_webhook_handler(include_comments: bool = True) -> str:
    """Generate PHP webhook handler (Slim framework)."""
    return PHP_WEBHOOK_TEMPLATE.strip()

def generate_php_guzzle_sdk(include_comments: bool = True) -> str:
    """Generate PHP SDK using Guzzle."""
    return PHP_GUZZLE_TEMPLATE.strip()

def get_composer_json() -> str:
    """Get composer.json content."""
    return COMPOSER_JSON.strip()

def get_php_example_usage() -> str:
    """Get PHP example usage."""
    return PHP_EXAMPLE_USAGE.strip()
