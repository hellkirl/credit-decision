FROM golang:1.27.1-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/app ./cmd/app

FROM alpine:3.22
RUN apk add --no-cache curl ca-certificates tzdata \
    && adduser -D -H -u 10001 app
COPY --from=build /out/app /usr/local/bin/app
USER app
EXPOSE 5000
ENTRYPOINT ["/usr/local/bin/app"]
