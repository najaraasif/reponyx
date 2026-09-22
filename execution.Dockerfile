FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir --upgrade pip==25.3 \
    && python -m pip install --no-cache-dir pytest==8.4.2 ruff==0.14.4 mypy==1.18.2 \
        numpy hypothesis

USER 65532:65532

ENTRYPOINT []
