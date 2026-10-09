FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.lock ./
RUN pip install --no-compile --require-hashes -r requirements.lock
COPY pyproject.toml README.md LICENSE LICENSE-MAIGRET ./
COPY deeper ./deeper
RUN pip install --no-compile --no-deps .
COPY scripts/slim_runtime.py /tmp/slim_runtime.py
RUN python /tmp/slim_runtime.py /opt/venv/lib/python3.12/site-packages

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp
COPY --from=build /opt/venv /opt/venv
COPY scripts/slim_runtime.py /tmp/slim_runtime.py
RUN python /tmp/slim_runtime.py /usr/local/lib/python3.12/site-packages \
    && rm /tmp/slim_runtime.py \
    && mkdir /app

WORKDIR /app
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["python", "-m", "deeper", "--host", "0.0.0.0", "--port", "8080"]
