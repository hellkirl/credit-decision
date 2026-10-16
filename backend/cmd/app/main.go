package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/rs/zerolog"

	httpin "github.com/hellkirl/credit-decision/internal/adapters/in/http"
	"github.com/hellkirl/credit-decision/internal/adapters/out/auth"
	"github.com/hellkirl/credit-decision/internal/adapters/out/ml"
	"github.com/hellkirl/credit-decision/internal/adapters/out/postgres"
	applicationsrepository "github.com/hellkirl/credit-decision/internal/adapters/out/postgres/applications_repository"
	usersrepository "github.com/hellkirl/credit-decision/internal/adapters/out/postgres/users_repository"
	"github.com/hellkirl/credit-decision/internal/application/commands"
	"github.com/hellkirl/credit-decision/internal/application/queries"
	"github.com/hellkirl/credit-decision/internal/config"
	"github.com/hellkirl/credit-decision/internal/domain"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	logger := zerolog.New(zerolog.ConsoleWriter{Out: os.Stderr}).With().Timestamp().Logger()

	if err := run(ctx, logger); err != nil {
		logger.Fatal().Err(err).Msg("backend stopped")
	}
}

func run(ctx context.Context, log zerolog.Logger) error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("config: %w", err)
	}

	db, err := postgres.NewPostgresClient(cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer postgres.Close(db)
	if err := postgres.Migrate(ctx, db); err != nil {
		return err
	}

	users := usersrepository.New(db)
	applications := applicationsrepository.New(db)
	hasher := auth.Bcrypt{}
	tokens := auth.NewTokens(cfg.JWTSecret, cfg.JWTTTL)
	scorer, err := ml.NewClient(cfg.MLURL, cfg.MLTimeout, cfg.RubPerDM)
	if err != nil {
		return err
	}

	if cfg.SeedLogin != "" {
		hash, err := hasher.Hash(cfg.SeedPassword)
		if err != nil {
			return err
		}
		if err := users.Upsert(ctx, &domain.User{
			Login:        cfg.SeedLogin,
			PasswordHash: hash,
			FullName:     cfg.SeedFullName,
			Position:     cfg.SeedPosition,
		}); err != nil {
			return fmt.Errorf("seed user: %w", err)
		}
		log.Info().Str("login", cfg.SeedLogin).Msg("seed user ready")
	}

	server := httpin.NewServer(httpin.Handlers{
		CreateApplication: commands.NewCreateApplicationHandler(applications, scorer, cfg.ApproveThreshold),
		UpdateApplication: commands.NewUpdateApplicationHandler(applications, scorer, cfg.ApproveThreshold),
		DeleteApplication: commands.NewDeleteApplicationHandler(applications),
		SaveDecision:      commands.NewSaveDecisionHandler(applications),
		Login:             commands.NewLoginHandler(users, hasher, tokens),
		ListApplications:  queries.NewListApplicationsHandler(applications),
		GetApplication:    queries.NewGetApplicationHandler(applications),
		GetStats:          queries.NewGetStatsHandler(applications),
		GetCurrentUser:    queries.NewGetCurrentUserHandler(users),
	})

	srv := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           httpin.NewRouter(server, tokens, log),
		ReadHeaderTimeout: 10 * time.Second,
	}

	errc := make(chan error, 1)
	go func() {
		log.Info().Str("addr", cfg.HTTPAddr).Msg("listening")
		errc <- srv.ListenAndServe()
	}()

	select {
	case err := <-errc:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case <-ctx.Done():
	}

	log.Info().Msg("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	return srv.Shutdown(shutdownCtx)
}
