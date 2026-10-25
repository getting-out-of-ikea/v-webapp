# This is an example Dockerfile that builds a minimal container for running LK Agents
# For more information on the build process, see https://docs.livekit.io/agents/ops/deployment/builds/
# syntax=docker/dockerfile:1

# Use the official UV Python base image with Python 3.13 on Debian Bookworm
# UV is a fast Python package manager that provides better performance than pip
# We use the slim variant to keep the image size smaller while still having essential tools
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Compile Python source to bytecode (.pyc) during install so the first import
# doesn't pay the compilation cost. This reduces agent cold-start time at the
# expense of a slightly longer build.
ENV UV_COMPILE_BYTECODE=1

# uv downloads any Python it "manages" under $HOME by default. During the build
# that is /root, which the runtime user (appuser, uid 10001) cannot even
# traverse. As a result, resolving `<venv>/bin/python3` — a symlink chain that
# ends inside /root/.local/share/uv/python/... — fails at startup with:
#   Failed to query Python interpreter
#   Caused by: failed to canonicalize path `/app/.venv/bin/python3`:
#              Permission denied (os error 13)
# Point uv's managed-Python install dir at a dedicated path outside the
# application tree. It is set in `base` so the build and production stages
# agree on the location, and it is explicitly copied (and chowned to appuser)
# in the final stage below, so the interpreter stays accessible at runtime.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python

# --- Build stage ---
# Install dependencies, build native extensions, and prepare the application
FROM base AS build

# Install build dependencies required for Python packages with native extensions
# gcc: C compiler needed for building Python packages with C extensions
# g++: C++ compiler needed for building Python packages with C++ extensions
# python3-dev: Python development headers needed for compilation
# We clean up the apt cache after installation to keep the image size down
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Create a new directory for our application code
# And set it as the working directory
WORKDIR /app

# Copy just the dependency files first, for more efficient layer caching
COPY pyproject.toml uv.lock .python-version ./
RUN mkdir -p src
ENV UV_PYTHON_DOWNLOADS=never

# Install Python dependencies using UV's lock file
# --locked ensures we use exact versions from uv.lock for reproducible builds
# This creates a virtual environment and installs all dependencies
# Ensure your uv.lock file is checked in for consistency across environments
#
# --no-install-project: install only the *dependencies* here. The `bot-agent`
# package itself lives in src/, which has not been copied into the image yet
# (only an empty `src/` directory was created above). Without this flag,
# `uv_build` fails with:
#   "Expected a Python module at: src/bot_agent/__init__.py"
# The project itself is installed by the second `uv sync` below, once the
# source has actually been copied in.
#
# This is also where uv installs its managed interpreter (into
# UV_PYTHON_INSTALL_DIR, /opt/uv-python), which the final stage carries over.
RUN uv sync --locked --no-install-project --no-dev

# Pre-download any ML models or files the agent needs
# This runs before COPY . . so the download layer is cached across code-only changes.
# The module-level command discovers installed livekit-plugins-* packages without
# loading your agent code.
#
# --no-sync: the project source is not on disk yet, so skip uv's automatic
# re-sync (which would try to build `bot-agent` and hit the same
# "Expected a Python module at: src/bot_agent/__init__.py" error). The
# dependency environment created by the previous `uv sync` is reused as-is.
RUN uv run --no-sync --module livekit.agents download-files

# Copy all remaining application files into the container
# This includes source code, configuration files, and dependency specifications
# (Excludes files specified in .dockerignore)
COPY . .

# Now that src/ is in the image, install the `bot-agent` package itself.
# This registers the `bot-agent` console script declared in pyproject.toml
# (`[project.scripts] bot-agent = "bot_agent:main"`), which is what the CMD
# below invokes.
RUN uv sync --locked --no-dev

# --- Production stage ---
# Build tools (gcc, g++, python3-dev) are not included in the final image
FROM base

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/build/building/best-practices/#user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/app" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

WORKDIR /app

# sounddevice (a transitive dep of livekit-agents) dlopens libportaudio.so.2.
# The slim base has neither it nor a mic/speaker; we install only the shared
# library so `bot-agent console` can even import, and keep --text so it never
# opens a device.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libportaudio2 \
 && rm -rf /var/lib/apt/lists/*

# Copy the application and virtual environment with correct ownership in a single layer
# This avoids expensive recursive chown and excludes build tools from the final image
COPY --from=build --chown=appuser:appuser /app /app

# Switch to the non-privileged user for all subsequent operations
# This improves security by not running as root
USER appuser

# Run the application using UV
# UV will activate the virtual environment and run the agent.
# The "start" command tells the worker to connect to LiveKit and begin waiting for jobs.
#
# We invoke the `bot-agent` console script (installed by the second `uv sync`
# above) instead of running the entrypoint file by path. Running
# `python src/bot_agent/agent.py` directly would execute agent.py as a
# top-level script, and its relative import
# (`from .plugins import PiperTTS, WhisperSTT`) would fail at startup with
# "attempted relative import with no known parent package". The console
# script goes through the `bot_agent` package, so the relative import
# resolves correctly.
CMD ["/app/.venv/bin/bot-agent", "start"]
