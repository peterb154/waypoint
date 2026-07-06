# waypoint agent image — lean FastAPI server (server.py).
# Does NOT use the vendored strands_pg package.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ca-certs + curl for https calls from tools; psycopg[binary] bundles libpq.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App modules.
COPY server.py area.py cache.py places.py chains.py verdict.py tracks.py ./

# Static web UI, migrations, one-shot scripts, and source data (gazetteer).
COPY web/        /app/web/
COPY migrations/ /app/migrations/
COPY scripts/    /app/scripts/
COPY data/       /app/data/

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Bake the commit SHA into the image so /api/health can report it.
# docker-compose passes this as a build arg from the host's git checkout.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
