# Build from the reviewed repository root, not a directory containing user state.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libsqlcipher-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY third_party/cognee/LICENSE third_party/cognee/NOTICE.md third_party/cognee/import-manifest.json ./third_party/cognee/
COPY atmem ./atmem
RUN python -m pip install --no-cache-dir '.[chatgpt]' && useradd --uid 10001 --create-home atmem
USER 10001
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
# Config is operator-mounted; master key comes from Secret Manager key_env.
ENTRYPOINT ["python","-m","atmem.chatgpt","serve","--config","/run/atmem/config.json","--host","0.0.0.0","--port","8080"]
