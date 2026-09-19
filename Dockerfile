# Entorno Linux local para desarrollo. El HPC usará el mismo environment.yml
# directamente mediante Conda, sin requerir Docker.
FROM mambaorg/micromamba:2.3.3

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba create --yes --name metvis3d --file /tmp/environment.yml \
    && micromamba clean --all --yes

ENV PATH=/opt/conda/envs/metvis3d/bin:$PATH
WORKDIR /workspace

COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml README.md ./
COPY --chown=$MAMBA_USER:$MAMBA_USER src ./src
RUN micromamba run --name metvis3d pip install --no-deps .

ENTRYPOINT ["micromamba", "run", "--name", "metvis3d"]
CMD ["metvis", "--help"]
