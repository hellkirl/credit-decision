package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	HTTPAddr    string
	DatabaseURL string

	JWTSecret string
	JWTTTL    time.Duration

	MLURL            string
	MLTimeout        time.Duration
	RubPerDM         float64
	ApproveThreshold float64

	SeedLogin    string
	SeedPassword string
	SeedFullName string
	SeedPosition string
}

func Load() (Config, error) {
	var errs []error
	c := Config{
		HTTPAddr:     env("HTTP_ADDR", ":5000"),
		DatabaseURL:  os.Getenv("DATABASE_URL"),
		JWTSecret:    os.Getenv("JWT_SECRET"),
		MLURL:        env("ML_URL", "http://ml:5001"),
		SeedLogin:    os.Getenv("SEED_USER_LOGIN"),
		SeedPassword: os.Getenv("SEED_USER_PASSWORD"),
		SeedFullName: env("SEED_USER_FULL_NAME", "Иванов Иван Александрович"),
		SeedPosition: env("SEED_USER_POSITION", "Кредитный специалист"),
	}
	c.JWTTTL = duration("JWT_TTL", 8*time.Hour, &errs)
	c.MLTimeout = duration("ML_TIMEOUT", 5*time.Second, &errs)
	c.RubPerDM = float("RUB_PER_DM", 100, &errs)
	c.ApproveThreshold = float("APPROVE_THRESHOLD", 0.25, &errs)

	if c.DatabaseURL == "" {
		errs = append(errs, errors.New("DATABASE_URL is required"))
	}
	if len(c.JWTSecret) < 32 {
		errs = append(errs, errors.New("JWT_SECRET must be at least 32 characters"))
	}
	if c.RubPerDM <= 0 {
		errs = append(errs, errors.New("RUB_PER_DM must be positive"))
	}
	if c.ApproveThreshold < 0 || c.ApproveThreshold > 1 {
		errs = append(errs, errors.New("APPROVE_THRESHOLD must be between 0 and 1"))
	}
	if c.SeedLogin != "" && c.SeedPassword == "" {
		errs = append(errs, errors.New("SEED_USER_PASSWORD is required when SEED_USER_LOGIN is set"))
	}
	return c, errors.Join(errs...)
}

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func duration(key string, fallback time.Duration, errs *[]error) time.Duration {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		*errs = append(*errs, fmt.Errorf("%s: %w", key, err))
	}
	return d
}

func float(key string, fallback float64, errs *[]error) float64 {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		*errs = append(*errs, fmt.Errorf("%s: %w", key, err))
	}
	return f
}
