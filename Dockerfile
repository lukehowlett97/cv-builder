FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/lukehowlett97/cv-builder" \
      org.opencontainers.image.description="Generic Python, Pandoc and XeLaTeX toolchain for CV PDF rendering" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        git \
        make \
        pandoc \
        texlive-fonts-recommended \
        texlive-latex-extra \
        texlive-xetex \
        fonts-texgyre \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
