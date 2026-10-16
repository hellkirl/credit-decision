package commands

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type PasswordHasher interface {
	Compare(hash, password string) bool
}

type TokenIssuer interface {
	Issue(userID int64) (token string, ttl time.Duration, err error)
}

type Login struct {
	Login    string
	Password string
}

type Token struct {
	AccessToken string
	TTL         time.Duration
}

type LoginHandler struct {
	users  ports.UserRepository
	hasher PasswordHasher
	tokens TokenIssuer
}

func NewLoginHandler(users ports.UserRepository, hasher PasswordHasher, tokens TokenIssuer) *LoginHandler {
	return &LoginHandler{users: users, hasher: hasher, tokens: tokens}
}

func (h *LoginHandler) Handle(ctx context.Context, cmd Login) (Token, error) {
	login := strings.TrimSpace(cmd.Login)
	if login == "" || cmd.Password == "" {
		fields := map[string]string{}
		if login == "" {
			fields["login"] = "is required"
		}
		if cmd.Password == "" {
			fields["password"] = "is required"
		}
		return Token{}, &domain.ValidationError{Fields: fields}
	}

	user, err := h.users.ByLogin(ctx, login)
	if errors.Is(err, domain.ErrNotFound) {
		return Token{}, domain.ErrInvalidCredentials
	}
	if err != nil {
		return Token{}, fmt.Errorf("find user: %w", err)
	}
	if !h.hasher.Compare(user.PasswordHash, cmd.Password) {
		return Token{}, domain.ErrInvalidCredentials
	}

	token, ttl, err := h.tokens.Issue(user.ID)
	if err != nil {
		return Token{}, fmt.Errorf("issue token: %w", err)
	}
	return Token{AccessToken: token, TTL: ttl}, nil
}
