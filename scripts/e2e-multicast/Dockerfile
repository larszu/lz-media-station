FROM debian:trixie-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3 python3-flask xvfb chromium ffmpeg pulseaudio pulseaudio-utils curl fonts-dejavu ca-certificates && rm -rf /var/lib/apt/lists/*
