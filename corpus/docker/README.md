# The corpus runner in Docker

Corpus runs execute third-party kernels on files from elsewhere. On a shared machine they run in this
image: with no network, as an unprivileged user, with dropped capabilities, under CPU, memory and
process caps, with the data mounted read-only and only the results directory writable.

```bash
docker build -t ckb-corpus -f corpus/docker/Dockerfile .
corpus/docker/run-in-docker.sh DATA_DIR manifest.tsv results/ --jobs 3
```

The image holds OCCT (cadquery-ocp 8.0.1), cadrs (built from the commit `CADRS_COMMIT` names), and
SMLib's `usd-brep`. SMLib reads only its own formats, not STEP, so it does not take part in corpus runs;
it is there for the generated families.
