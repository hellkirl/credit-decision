package http

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func newHTTPMetrics() (gin.HandlerFunc, http.Handler) {
	registry := prometheus.NewRegistry()
	requests := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "backend_http_requests_total",
			Help: "Total HTTP requests by method, route and status.",
		},
		[]string{"method", "route", "status"},
	)
	duration := prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "backend_http_request_duration_seconds",
			Help:    "HTTP request duration in seconds.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "route"},
	)
	registry.MustRegister(requests, duration)

	middleware := func(c *gin.Context) {
		if c.FullPath() == "/metrics" {
			c.Next()
			return
		}
		start := time.Now()
		c.Next()

		route := c.FullPath()
		if route == "" {
			route = "unmatched"
		}
		method := c.Request.Method
		switch method {
		case "GET", "HEAD", "POST", "PUT", "PATCH",
			"DELETE", "OPTIONS", "CONNECT", "TRACE":
		default:
			method = "OTHER"
		}
		requests.WithLabelValues(method, route, strconv.Itoa(c.Writer.Status())).Inc()
		duration.WithLabelValues(method, route).Observe(time.Since(start).Seconds())
	}
	return middleware, promhttp.HandlerFor(registry, promhttp.HandlerOpts{})
}
