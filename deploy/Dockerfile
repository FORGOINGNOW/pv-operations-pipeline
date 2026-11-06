FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/pv
COPY pyproject.toml constraints.txt ./
COPY src ./src
RUN python -m pip install --no-cache-dir -c constraints.txt .
COPY scripts ./scripts
COPY configs ./configs
COPY sql ./sql
RUN useradd --uid 10001 --create-home pv && mkdir runtime && chown -R pv:pv /opt/pv
USER 10001:10001
ENV PV_PYTHON=python OMP_NUM_THREADS=2
ENTRYPOINT ["bash", "scripts/90_demo.sh"]
CMD ["--config", "configs/smoke.yaml"]
