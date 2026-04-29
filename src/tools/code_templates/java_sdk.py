"""
Java SDK Templates for IBMB Integration
Supports: Spring Boot, OkHttp, standard HTTP client
"""

JAVA_SDK_TEMPLATE = '''
package com.merchant.ibmb;

import okhttp3.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Map;
import java.util.HashMap;
import java.util.concurrent.TimeUnit;

/**
 * IBMB Payment SDK
 * 
 * @author Merchant Integration Team
 * @version 1.0.0
 */
public class IbmbPaymentClient {
    
    private final String baseUrl;
    private final String apiKey;
    private final String merchantId;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;
    
    public IbmbPaymentClient(String baseUrl, String apiKey, String merchantId) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.merchantId = merchantId;
        this.objectMapper = new ObjectMapper();
        
        // Configure HTTP client with timeouts
        this.httpClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build();
    }
    
    /**
     * Initialize a UPI transaction
     * 
     * @param payeeVpa Merchant VPA handle
     * @param payerVpa Customer VPA handle
     * @param amount Transaction amount
     * @param merchantRequestId Unique request ID
     * @param txnType Transaction type (COLLECT or PAY)
     * @return Transaction response
     * @throws IOException on network error
     * @throws IbmbApiException on API error
     */
    public TransactionResponse initiateTransaction(
            String payeeVpa,
            String payerVpa,
            String amount,
            String merchantRequestId,
            TransactionType txnType) throws IOException, IbmbApiException {
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("payeeVpaHandle", payeeVpa);
        payload.put("payerVpaHandle", payerVpa);
        payload.put("amount", amount);
        payload.put("merchantRequestId", merchantRequestId);
        payload.put("merchantId", merchantId);
        payload.put("upiTxnType", txnType.name());
        payload.put("currency", "INR");
        
        String jsonBody = objectMapper.writeValueAsString(payload);
        
        Request request = new Request.Builder()
            .url(baseUrl + "/api/merchants/v1/transaction/initiate")
            .post(RequestBody.create(jsonBody, MediaType.parse("application/json")))
            .addHeader("X-API-Key", apiKey)
            .addHeader("Content-Type", "application/json")
            .addHeader("Accept", "application/json")
            .build();
        
        try (Response response = httpClient.newCall(request).execute()) {
            String responseBody = response.body() != null ? response.body().string() : "";
            
            if (!response.isSuccessful()) {
                ErrorResponse error = objectMapper.readValue(responseBody, ErrorResponse.class);
                throw new IbmbApiException(error.getResponseCode(), error.getResponseMessage());
            }
            
            return objectMapper.readValue(responseBody, TransactionResponse.class);
        }
    }
    
    /**
     * Query transaction status
     * 
     * @param merchantRequestId The original request ID
     * @param upiTxnId UPI transaction ID (optional)
     * @return Transaction status
     * @throws IOException on network error
     */
    public TransactionStatusResponse getTransactionStatus(
            String merchantRequestId,
            String upiTxnId) throws IOException {
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("merchantId", merchantId);
        payload.put("merchantRequestId", merchantRequestId);
        if (upiTxnId != null) {
            payload.put("upiTxnId", upiTxnId);
        }
        
        String jsonBody = objectMapper.writeValueAsString(payload);
        
        Request request = new Request.Builder()
            .url(baseUrl + "/api/merchants/v1/transaction/status")
            .post(RequestBody.create(jsonBody, MediaType.parse("application/json")))
            .addHeader("X-API-Key", apiKey)
            .addHeader("Content-Type", "application/json")
            .build();
        
        try (Response response = httpClient.newCall(request).execute()) {
            String responseBody = response.body() != null ? response.body().string() : "";
            return objectMapper.readValue(responseBody, TransactionStatusResponse.class);
        }
    }
    
    /**
     * Process a refund
     * 
     * @param orderId Original order ID
     * @param amount Refund amount (null for full refund)
     * @param reason Refund reason
     * @param uniqueRequestId Unique refund request ID
     * @return Refund response
     * @throws IOException on network error
     */
    public RefundResponse createRefund(
            String orderId,
            String amount,
            String reason,
            String uniqueRequestId) throws IOException {
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("orderId", orderId);
        payload.put("uniqueRequestId", uniqueRequestId);
        if (amount != null) {
            payload.put("amount", amount);
        }
        if (reason != null) {
            payload.put("reason", reason);
        }
        
        String jsonBody = objectMapper.writeValueAsString(payload);
        
        Request request = new Request.Builder()
            .url(baseUrl + "/api/merchants/v1/refund")
            .post(RequestBody.create(jsonBody, MediaType.parse("application/json")))
            .addHeader("X-API-Key", apiKey)
            .addHeader("Content-Type", "application/json")
            .build();
        
        try (Response response = httpClient.newCall(request).execute()) {
            String responseBody = response.body() != null ? response.body().string() : "";
            return objectMapper.readValue(responseBody, RefundResponse.class);
        }
    }
}

enum TransactionType {
    COLLECT, PAY
}

class TransactionResponse {
    private String result;
    private String responseCode;
    private String responseMessage;
    private TransactionPayload payload;
    
    // Getters and setters
    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
    public String getResponseCode() { return responseCode; }
    public void setResponseCode(String responseCode) { this.responseCode = responseCode; }
    public TransactionPayload getPayload() { return payload; }
    public void setPayload(TransactionPayload payload) { this.payload = payload; }
}

class TransactionPayload {
    private String merchantRequestId;
    private String intentExpiry;
    private String url;
    
    // Getters and setters
    public String getMerchantRequestId() { return merchantRequestId; }
    public void setMerchantRequestId(String merchantRequestId) { this.merchantRequestId = merchantRequestId; }
    public String getIntentExpiry() { return intentExpiry; }
    public void setIntentExpiry(String intentExpiry) { this.intentExpiry = intentExpiry; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
}

class TransactionStatusResponse {
    private String result;
    private String txnStatus;
    private String amount;
    private String currency;
    private String transactionId;
    
    // Getters and setters
}

class RefundResponse {
    private String refundId;
    private String status;
    private String amount;
    
    // Getters and setters
}

class ErrorResponse {
    private String responseCode;
    private String responseMessage;
    
    public String getResponseCode() { return responseCode; }
    public void setResponseCode(String responseCode) { this.responseCode = responseCode; }
    public String getResponseMessage() { return responseMessage; }
    public void setResponseMessage(String responseMessage) { this.responseMessage = responseMessage; }
}

class IbmbApiException extends Exception {
    private final String errorCode;
    
    public IbmbApiException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }
    
    public String getErrorCode() { return errorCode; }
}
'''

JAVA_WEBHOOK_TEMPLATE = '''
package com.merchant.ibmb;

import org.springframework.web.bind.annotation.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Webhook Controller for IBMB Events
 */
@RestController
@RequestMapping("/webhook")
public class WebhookController {
    
    private final String webhookSecret;
    private final ObjectMapper objectMapper;
    private final PaymentEventHandler eventHandler;
    
    public WebhookController(
            @Value("${ibmb.webhook.secret}") String webhookSecret,
            PaymentEventHandler eventHandler) {
        this.webhookSecret = webhookSecret;
        this.objectMapper = new ObjectMapper();
        this.eventHandler = eventHandler;
    }
    
    @PostMapping
    public ResponseEntity<String> handleWebhook(
            @RequestHeader("X-Juspay-Signature") String signature,
            @RequestBody String rawBody) {
        
        // Verify signature
        if (!verifySignature(rawBody, signature)) {
            return ResponseEntity.status(401).body("Invalid signature");
        }
        
        try {
            // Parse event
            WebhookEvent event = objectMapper.readValue(rawBody, WebhookEvent.class);
            
            // Route to handler
            switch (event.getEvent()) {
                case "order.charged":
                    eventHandler.handlePaymentSuccess(event);
                    break;
                case "order.failed":
                    eventHandler.handlePaymentFailure(event);
                    break;
                case "refund.processed":
                    eventHandler.handleRefundComplete(event);
                    break;
                default:
                    System.out.println("Unknown event type: " + event.getEvent());
            }
            
            return ResponseEntity.ok("OK");
            
        } catch (Exception e) {
            System.err.println("Error processing webhook: " + e.getMessage());
            // Still return 200 to prevent retries for processing errors
            // Log and alert internally
            return ResponseEntity.ok("Accepted");
        }
    }
    
    /**
     * Verify webhook signature using HMAC-SHA256
     */
    private boolean verifySignature(String payload, String signature) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec secretKey = new SecretKeySpec(
                webhookSecret.getBytes(StandardCharsets.UTF_8),
                "HmacSHA256"
            );
            mac.init(secretKey);
            
            byte[] hash = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            String expected = Base64.getEncoder().encodeToString(hash);
            
            // Use constant-time comparison
            return MessageDigest.isEqual(
                signature.getBytes(StandardCharsets.UTF_8),
                expected.getBytes(StandardCharsets.UTF_8)
            );
            
        } catch (Exception e) {
            System.err.println("Signature verification error: " + e.getMessage());
            return false;
        }
    }
}

class WebhookEvent {
    private String event;
    private String orderId;
    private String status;
    private Map<String, Object> data;
    
    // Getters and setters
    public String getEvent() { return event; }
    public void setEvent(String event) { this.event = event; }
    public String getOrderId() { return orderId; }
    public void setOrderId(String orderId) { this.orderId = orderId; }
}

@Service
class PaymentEventHandler {
    
    public void handlePaymentSuccess(WebhookEvent event) {
        // Update order status
        // Fulfill order
        // Notify customer
        System.out.println("Payment successful for order: " + event.getOrderId());
    }
    
    public void handlePaymentFailure(WebhookEvent event) {
        // Update order status
        // Notify customer
        System.out.println("Payment failed for order: " + event.getOrderId());
    }
    
    public void handleRefundComplete(WebhookEvent event) {
        // Update refund status
        // Notify customer
        System.out.println("Refund processed for order: " + event.getOrderId());
    }
}
'''

JAVA_RETRY_TEMPLATE = '''
package com.merchant.ibmb;

import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.concurrent.Callable;

/**
 * Retry handler with exponential backoff
 */
public class RetryHandler {
    
    private static final int MAX_RETRIES = 3;
    private static final long BASE_DELAY_MS = 1000;
    private static final Random random = new Random();
    
    private static final List<String> RETRYABLE_ERRORS = Arrays.asList(
        "TIMEOUT",
        "RATE_LIMITED",
        "GATEWAY_ERROR",
        "SERVICE_UNAVAILABLE",
        "CONNECTION_ERROR"
    );
    
    /**
     * Execute operation with retry
     */
    public static <T> T executeWithRetry(Callable<T> operation) throws Exception {
        Exception lastException = null;
        
        for (int attempt = 0; attempt < MAX_RETRIES; attempt++) {
            try {
                return operation.call();
            } catch (Exception e) {
                lastException = e;
                
                if (!shouldRetry(e) || attempt == MAX_RETRIES - 1) {
                    throw e;
                }
                
                long delay = calculateDelay(attempt);
                Thread.sleep(delay);
            }
        }
        
        throw lastException;
    }
    
    private static boolean shouldRetry(Exception e) {
        String message = e.getMessage();
        if (message == null) return false;
        
        return RETRYABLE_ERRORS.stream()
            .anyMatch(error -> message.contains(error));
    }
    
    private static long calculateDelay(int attempt) {
        // Exponential backoff: 1s, 2s, 4s
        long delay = BASE_DELAY_MS * (long) Math.pow(2, attempt);
        // Add jitter (0-10%)
        delay += random.nextInt((int) (delay * 0.1));
        return delay;
    }
}

// Usage:
// TransactionResponse response = RetryHandler.executeWithRetry(() ->
//     client.initiateTransaction(...)
// );
'''

# Maven dependencies
MAVEN_DEPENDENCIES = '''
<!-- Required dependencies for IBMB Java SDK -->
<dependencies>
    <!-- HTTP Client -->
    <dependency>
        <groupId>com.squareup.okhttp3</groupId>
        <artifactId>okhttp</artifactId>
        <version>4.12.0</version>
    </dependency>
    
    <!-- JSON Processing -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
        <version>2.16.0</version>
    </dependency>
    
    <!-- Spring Boot (for web applications) -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
</dependencies>
'''

def generate_java_sdk(include_comments: bool = True, include_error_handling: bool = True) -> str:
    """Generate Java SDK code."""
    sections = []
    
    if include_comments:
        sections.append("// IBMB Payment Java SDK")
        sections.append("// Dependencies: OkHttp, Jackson")
        sections.append("")
    
    sections.append(JAVA_SDK_TEMPLATE.strip())
    
    if include_error_handling:
        sections.append("")
        sections.append("// Retry Handler")
        sections.append(JAVA_RETRY_TEMPLATE.strip())
    
    return "\n\n".join(sections)

def generate_java_webhook_handler(include_comments: bool = True) -> str:
    """Generate Java webhook handler."""
    return JAVA_WEBHOOK_TEMPLATE.strip()

def get_maven_dependencies() -> str:
    """Get Maven dependencies XML."""
    return MAVEN_DEPENDENCIES.strip()
