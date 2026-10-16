package http

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/rs/zerolog"

	genhttp "github.com/hellkirl/credit-decision/pkg/generated/http"
)

type TokenParser interface {
	Parse(token string) (userID int64, err error)
}

const userIDKey = "auth.user_id"

func userID(ctx context.Context) int64 {
	id, _ := ctx.Value(userIDKey).(int64)
	return id
}

func Authenticate(tokens TokenParser) genhttp.MiddlewareFunc {
	return func(c *gin.Context) {
		if _, secured := c.Get(genhttp.BearerAuthScopes); !secured {
			return
		}
		header := c.GetHeader("Authorization")
		scheme, token, ok := strings.Cut(header, " ")
		if !ok || !strings.EqualFold(scheme, "Bearer") || strings.TrimSpace(token) == "" {
			abortUnauthorized(c, "missing bearer token")
			return
		}
		id, err := tokens.Parse(strings.TrimSpace(token))
		if err != nil {
			abortUnauthorized(c, "invalid or expired token")
			return
		}
		c.Set(userIDKey, id)
	}
}

func abortUnauthorized(c *gin.Context, msg string) {
	c.Header("WWW-Authenticate", `Bearer error="invalid_token"`)
	c.AbortWithStatusJSON(http.StatusUnauthorized, genhttp.Error{Error: msg})
}

func ParamError(c *gin.Context, err error, status int) {
	c.AbortWithStatusJSON(status, genhttp.Error{Error: err.Error()})
}

func Errors(log zerolog.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()

		status := c.Writer.Status()
		if !c.Writer.Written() {
			switch {
			case status == http.StatusBadRequest:
				msg := "malformed request body"
				if len(c.Errors) > 0 {
					msg += ": " + c.Errors.Last().Error()
				}
				c.JSON(status, genhttp.Error{Error: msg})
			case status >= http.StatusInternalServerError:
				c.JSON(status, genhttp.Error{Error: "internal server error"})
			}
		}

		ev := log.Info()
		if status >= http.StatusInternalServerError {
			ev = log.Error()
		}
		if len(c.Errors) > 0 {
			ev = ev.Str("error", c.Errors.String())
		}
		ev.Str("method", c.Request.Method).
			Str("path", c.Request.URL.Path).
			Int("status", status).
			Dur("duration", time.Since(start)).
			Msg("request")
	}
}

func NewRouter(server *Server, tokens TokenParser, log zerolog.Logger) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery(), Errors(log))
	r.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, genhttp.Error{Error: "not found"})
	})

	genhttp.RegisterHandlersWithOptions(r, genhttp.NewStrictHandler(server, nil), genhttp.GinServerOptions{
		Middlewares:  []genhttp.MiddlewareFunc{Authenticate(tokens)},
		ErrorHandler: ParamError,
	})
	return r
}
