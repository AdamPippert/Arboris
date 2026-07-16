# Arboris

A graph-based, dendritic model exploring an alternative approach to world models.

> **Status:** pre-alpha, in active development. The architecture is still taking
> shape and no trained weights have been released. This repository is the source
> home for the code and data. Trained models, once they exist, are published by
> Coastal Digital Research on Hugging Face.

## Idea

Most world models compress state into a single latent that rolls forward in time
under one predictive objective. Arboris takes a different route: it represents
state as a graph and grows its predictive structure dendritically, branching along
the relations that carry signal rather than flattening everything into a monolithic
latent. The bet is that a branching, graph-native representation captures the
structure of an environment more faithfully.

This is a research direction, not a finished result. Expect the design to change.

## Implemented foundation

The first migration stage provides canonical Pydantic graph/provenance records,
deterministic graph differencing and rollback, versioned upper and infrastructure
ontology documents, executable domain/range and integrity validation, and an
`arboris ontology validate` CLI. Dendritic computation, prediction, arbitration,
simulation, training, and model weights are not implemented yet.

Development setup and checks:

```bash
uv sync --extra dev
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/arboris ontology validate \
  --ontology ontologies/domains/infrastructure-0.1.0.json --json
```

Install the `model` extra only when working on neural stages, using a PyTorch source
appropriate for the host's CPU or CUDA platform.

See [`docs/repository_assessment.md`](docs/repository_assessment.md) and
[`docs/migration_plan.md`](docs/migration_plan.md) for the audited baseline, gap
analysis, decisions, target tree, and staged experiment plan.

## Partnership

Arboris is developed by Adam Pippert as independent research. Coastal Digital
Research trains and publishes the models on Hugging Face:
<https://huggingface.co/CoastalDigitalResearch/Arboris>.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
