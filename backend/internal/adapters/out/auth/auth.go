package auth

import (
	"fmt"
	"strconv"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

type Tokens struct {
	secret []byte
	ttl    time.Duration
	now    func() time.Time
}

func NewTokens(secret string, ttl time.Duration) *Tokens {
	return &Tokens{secret: []byte(secret), ttl: ttl, now: time.Now}
}

func (t *Tokens) Issue(userID int64) (string, time.Duration, error) {
	now := t.now()
	claims := jwt.RegisteredClaims{
		Subject:   strconv.FormatInt(userID, 10),
		IssuedAt:  jwt.NewNumericDate(now),
		ExpiresAt: jwt.NewNumericDate(now.Add(t.ttl)),
	}
	signed, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(t.secret)
	return signed, t.ttl, err
}

func (t *Tokens) Parse(token string) (int64, error) {
	var claims jwt.RegisteredClaims
	_, err := jwt.ParseWithClaims(token, &claims, func(*jwt.Token) (any, error) {
		return t.secret, nil
	},
		jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
		jwt.WithExpirationRequired(),
		jwt.WithTimeFunc(t.now),
	)
	if err != nil {
		return 0, err
	}
	id, err := strconv.ParseInt(claims.Subject, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("invalid subject: %w", err)
	}
	return id, nil
}

type Bcrypt struct{}

func (Bcrypt) Hash(password string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	return string(hash), err
}

func (Bcrypt) Compare(hash, password string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) == nil
}
