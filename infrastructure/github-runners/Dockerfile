# GitHub Actions Self-Hosted Runner (lightweight, for deploy-only workflows)
#
# Build: docker build -t ghrunner-proxycraft .
# Run via docker-compose (see docker-compose.yml)

FROM ubuntu:24.04

ARG RUNNER_VERSION=2.331.0

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# System dependencies (minimal — deploy uses SSH action only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    jq \
    ca-certificates \
    gnupg \
    locales \
    sudo \
    openssh-client \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Runner user (non-root)
RUN useradd -m -s /bin/bash runner \
    && echo "runner ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# GitHub Actions Runner
WORKDIR /home/runner
RUN curl -sSfL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    | tar xz \
    && ./bin/installdependencies.sh \
    && rm -rf /var/lib/apt/lists/*

# Fix permissions
RUN chown -R runner:runner /home/runner

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER runner

ENTRYPOINT ["/entrypoint.sh"]
