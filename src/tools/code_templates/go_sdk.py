"""
Go SDK Templates for IBMB Integration
Supports: Standard net/http, popular libraries
"""

GO_SDK_TEMPLATE = '''
package ibmb

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const (
	DefaultTimeout = 30 * time.Second
)

// Client for IBMB Payment API
type Client struct {
	BaseURL    string
	APIKey     string
	MerchantID string
	HTTPClient *http.Client
}

// NewClient creates a new IBMB API client
func NewClient(baseURL, apiKey, merchantID string) *Client {
	return &Client{
		BaseURL:    baseURL,
		APIKey:     apiKey,
		MerchantID: merchantID,
		HTTPClient: &http.Client{
			Timeout: DefaultTimeout,
		},
	}
}

// TransactionRequest represents a transaction initiation request
type TransactionRequest struct {
	PayeeVpaHandle    string `json:"payeeVpaHandle"`
	PayerVpaHandle    string `json:"payerVpaHandle"`
	Amount            string `json:"amount"`
	MerchantRequestID string `json:"merchantRequestId"`
	MerchantID        string `json:"merchantId"`
	UpiTxnType        string `json:"upiTxnType"`
	Currency          string `json:"currency,omitempty"`
	Description       string `json:"description,omitempty"`
}

// TransactionResponse represents the API response
type TransactionResponse struct {
	Result          string             `json:"result"`
	ResponseCode    string             `json:"responseCode"`
	ResponseMessage string             `json:"responseMessage"`
	Payload         TransactionPayload `json:"payload"`
}

// TransactionPayload contains the transaction details
type TransactionPayload struct {
	MerchantRequestID string `json:"merchantRequestId"`
	IntentExpiry      string `json:"intentExpiry"`
	URL               string `json:"url"`
}

// ErrorResponse represents an API error
type ErrorResponse struct {
	ResponseCode    string `json:"responseCode"`
	ResponseMessage string `json:"responseMessage"`
}

// APIError is a custom error type for API errors
type APIError struct {
	Code    string
	Message string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("API Error %s: %s", e.Code, e.Message)
}

// InitiateTransaction creates a new UPI transaction
func (c *Client) InitiateTransaction(req *TransactionRequest) (*TransactionResponse, error) {
	// Set defaults
	if req.Currency == "" {
		req.Currency = "INR"
	}
	req.MerchantID = c.MerchantID

	url := c.BaseURL + "/api/merchants/v1/transaction/initiate"

	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "application/json")
	httpReq.Header.Set("X-API-Key", c.APIKey)

	resp, err := c.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		var errResp ErrorResponse
		if err := json.Unmarshal(respBody, &errResp); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(respBody))
		}
		return nil, &APIError{
			Code:    errResp.ResponseCode,
			Message: errResp.ResponseMessage,
		}
	}

	var result TransactionResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &result, nil
}

// GetTransactionStatus queries the status of a transaction
func (c *Client) GetTransactionStatus(merchantRequestID, upiTxnID string) (*TransactionStatusResponse, error) {
	payload := map[string]string{
		"merchantId":        c.MerchantID,
		"merchantRequestId": merchantRequestID,
	}
	if upiTxnID != "" {
		payload["upiTxnId"] = upiTxnID
	}

	url := c.BaseURL + "/api/merchants/v1/transaction/status"

	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-API-Key", c.APIKey)

	resp, err := c.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	var result TransactionStatusResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// TransactionStatusResponse represents transaction status
type TransactionStatusResponse struct {
	Result        string `json:"result"`
	TxnStatus     string `json:"txnStatus"`
	Amount        string `json:"amount"`
	Currency      string `json:"currency"`
	TransactionID string `json:"transactionId"`
}
'''

GO_WEBHOOK_TEMPLATE = '''
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"os"
)

// WebhookEvent represents a webhook payload
type WebhookEvent struct {
	Event   string                 `json:"event"`
	OrderID string                 `json:"order_id"`
	Status  string                 `json:"status"`
	Data    map[string]interface{} `json:"data"`
}

// WebhookHandler handles incoming webhooks
func WebhookHandler(w http.ResponseWriter, r *http.Request) {
	// Read raw body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Verify signature
	signature := r.Header.Get("X-Juspay-Signature")
	if signature == "" {
		http.Error(w, "Missing signature", http.StatusUnauthorized)
		return
	}

	webhookSecret := os.Getenv("WEBHOOK_SECRET")
	if !verifySignature(body, signature, webhookSecret) {
		http.Error(w, "Invalid signature", http.StatusUnauthorized)
		return
	}

	// Parse event
	var event WebhookEvent
	if err := json.Unmarshal(body, &event); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Process event asynchronously
	go processEvent(&event)

	// Return success immediately
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}

// verifySignature verifies HMAC-SHA256 signature
func verifySignature(body []byte, signature, secret string) bool {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	expected := hex.EncodeToString(mac.Sum(nil))

	// Constant-time comparison
	return hmac.Equal([]byte(signature), []byte(expected))
}

// processEvent routes events to appropriate handlers
func processEvent(event *WebhookEvent) {
	switch event.Event {
	case "order.charged":
		handlePaymentSuccess(event)
	case "order.failed":
		handlePaymentFailure(event)
	case "refund.processed":
		handleRefundProcessed(event)
	default:
		// Log unknown event
	}
}

func handlePaymentSuccess(event *WebhookEvent) {
	// Fulfill order
	// Notify customer
}

func handlePaymentFailure(event *WebhookEvent) {
	// Update order status
	// Notify customer
}

func handleRefundProcessed(event *WebhookEvent) {
	// Update refund status
	// Notify customer
}

func main() {
	http.HandleFunc("/webhook", WebhookHandler)
	http.ListenAndServe(":8080", nil)
}
'''

GO_RETRY_TEMPLATE = '''
package ibmb

import (
	"math"
	"math/rand"
	"strings"
	"time"
)

// RetryConfig configures retry behavior
type RetryConfig struct {
	MaxRetries  int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
	Multiplier  float64
	RetryErrors []string
}

// DefaultRetryConfig returns sensible defaults
func DefaultRetryConfig() *RetryConfig {
	return &RetryConfig{
		MaxRetries:  3,
		BaseDelay:   1 * time.Second,
		MaxDelay:    30 * time.Second,
		Multiplier:  2.0,
		RetryErrors: []string{
			"TIMEOUT",
			"RATE_LIMITED",
			"GATEWAY_ERROR",
			"SERVICE_UNAVAILABLE",
		},
	}
}

// ExecuteWithRetry executes a function with exponential backoff
func ExecuteWithRetry(operation func() error, config *RetryConfig) error {
	if config == nil {
		config = DefaultRetryConfig()
	}

	var lastErr error

	for attempt := 0; attempt < config.MaxRetries; attempt++ {
		err := operation()
		if err == nil {
			return nil
		}

		lastErr = err

		if !shouldRetry(err, config.RetryErrors) {
			return err
		}

		if attempt < config.MaxRetries-1 {
			delay := calculateDelay(attempt, config)
			time.Sleep(delay)
		}
	}

	return lastErr
}

func shouldRetry(err error, retryErrors []string) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()
	for _, retryErr := range retryErrors {
		if strings.Contains(errStr, retryErr) {
			return true
		}
	}
	return false
}

func calculateDelay(attempt int, config *RetryConfig) time.Duration {
	// Exponential backoff: base * 2^attempt
	delay := float64(config.BaseDelay) * math.Pow(config.Multiplier, float64(attempt))

	// Add jitter (0-10%)
	jitter := delay * 0.1 * rand.Float64()
	delay += jitter

	// Cap at max delay
	if delay > float64(config.MaxDelay) {
		delay = float64(config.MaxDelay)
	}

	return time.Duration(delay)
}

// Usage example:
// err := ExecuteWithRetry(func() error {
//     _, err := client.InitiateTransaction(req)
//     return err
// }, nil)
'''

GO_EXAMPLE_USAGE = '''
package main

import (
	"fmt"
	"log"
	"os"
	
	"yourmodule/ibmb"
)

func main() {
	// Initialize client
	client := ibmb.NewClient(
		os.Getenv("IBMB_BASE_URL"),
		os.Getenv("IBMB_API_KEY"),
		os.Getenv("IBMB_MERCHANT_ID"),
	)

	// Create transaction request
	req := &ibmb.TransactionRequest{
		PayeeVpaHandle:    "merchant@juspay",
		PayerVpaHandle:    "customer@okaxis",
		Amount:            "1000.00",
		MerchantRequestID: "ORDER_20240901123456",
		UpiTxnType:        "COLLECT",
		Description:       "Payment for Order #12345",
	}

	// Execute with retry
	err := ibmb.ExecuteWithRetry(func() error {
		resp, err := client.InitiateTransaction(req)
		if err != nil {
			return err
		}
		
		fmt.Printf("Transaction initiated: %s\\n", resp.Payload.URL)
		return nil
	}, nil)

	if err != nil {
		log.Fatalf("Transaction failed: %v", err)
	}
}
'''

# Go mod dependencies
GO_MOD_DEPENDENCIES = '''
// go.mod
module your-module

go 1.21

require (
    github.com/gorilla/mux v1.8.1 // for routing (optional)
)
'''

def generate_go_sdk(include_comments: bool = True, include_error_handling: bool = True) -> str:
    """Generate Go SDK code."""
    sections = []
    
    if include_comments:
        sections.append("// IBMB Payment Go SDK")
        sections.append("// Standard library only (net/http)")
        sections.append("")
    
    sections.append(GO_SDK_TEMPLATE.strip())
    
    if include_error_handling:
        sections.append("")
        sections.append("// Retry utilities")
        sections.append(GO_RETRY_TEMPLATE.strip())
    
    return "\n\n".join(sections)

def generate_go_webhook_handler(include_comments: bool = True) -> str:
    """Generate Go webhook handler."""
    return GO_WEBHOOK_TEMPLATE.strip()

def get_go_mod() -> str:
    """Get go.mod dependencies."""
    return GO_MOD_DEPENDENCIES.strip()

def get_go_example_usage() -> str:
    """Get Go example usage."""
    return GO_EXAMPLE_USAGE.strip()
