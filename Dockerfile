FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /build
RUN python -m venv "${VIRTUAL_ENV}"
COPY pyproject.toml constraints-langchain.txt README.md ./
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -c constraints-langchain.txt \
       ".[dev,dashboard,postgres-checkpoint]"

FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

RUN groupadd --system snoc \
    && useradd --system --gid snoc --home-dir /app --create-home snoc

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic/ alembic/
COPY scripts/ scripts/
COPY dashboard.py ./
COPY src/ src/
RUN mkdir -p /app/outputs /app/var \
    && chown -R snoc:snoc /app/outputs /app/var

USER snoc
CMD ["snoc-agent", "worker", "run"]
