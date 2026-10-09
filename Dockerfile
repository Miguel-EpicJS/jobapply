FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        poppler-utils \
        texlive-latex-base \
        texlive-latex-extra \
        xclip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /data/.jobapply /data/generated-resumes

ENTRYPOINT ["jobapply"]
CMD ["tui"]
