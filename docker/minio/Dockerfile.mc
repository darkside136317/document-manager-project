# Official Community client source release, built locally for bucket bootstrap.
FROM golang:1.24-bookworm AS build
RUN CGO_ENABLED=0 go install github.com/minio/mc@RELEASE.2025-08-13T08-35-41Z

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /go/bin/mc /usr/local/bin/mc
ENTRYPOINT ["mc"]
