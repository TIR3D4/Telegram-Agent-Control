FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TAC_LISTEN_HOST=0.0.0.0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libcairo2 curl && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 tac && useradd -u 10001 -g tac -m tac
COPY requirements.lock /app/
RUN pip install --no-cache-dir -r requirements.lock
COPY . /app
RUN pip install --no-deps . && mkdir -p /data/media && chown -R tac:tac /data /app
USER tac
EXPOSE 8787
CMD ["tac", "serve"]
