# Openness: source, weights, and data

Arboris commits to full openness on **three pillars** for the base iteration
of the model. Many projects are open on one pillar and closed on the others —
open code with secret data, or downloadable weights with an undisclosed
recipe.
Arboris treats the three as a single reproducibility chain. **You should be
able to retrace the whole path from raw sources to a working model using only
public artifacts.**

```mermaid
flowchart LR
    subgraph pillars["The three pillars (base iteration)"]
        direction TB
        OS["🔓 Open source<br/>all code, Apache-2.0"]
        OD["🔓 Open data<br/>dataset + rebuild recipe"]
        OW["🔓 Open weights<br/>checkpoints + model card"]
    end
    RAW["Raw sources"] --> OD
    OS -->|"data pipeline<br/>(public code)"| OD
    OD -->|"training pipeline<br/>(public code)"| OW
    OW --> USE["Anyone: use, study,<br/>verify, retrain, fork"]
```

**In plain terms:** you can read every line of the instructions (source). You
can see every page of the study material (data) and download the finished
student (weights). Nothing about how the base model came to be is a secret.

---

## Pillar 1 — Open source

**What:** every line of code the project produces. The scope covers the
architecture (`graph/`, `dendrite/`, `dynamics/`, `encoders/`), the
[data pipeline](data-pipeline.md) (`data/`), the
[training pipeline](training-pipeline.md) (`training/`), and the evaluation
suite (`eval/`).

**Where:** this repository, <https://github.com/AdamPippert/Arboris>.

**License:** [Apache-2.0](../LICENSE) — a permissive license allowing
commercial use, modification, and redistribution, with an explicit patent
grant. See also [`NOTICE`](../NOTICE).

**Why it matters:** for a researcher, the code *is* the precise specification
of the method. There is no ambiguity between what a paper says and what was
run. For everyone else: nothing the model does is hidden machinery. Anyone
qualified can inspect exactly how it works.

**Status:** the repository is public from day one, pre-alpha scaffold
included. Development happens in the open rather than being released after
the fact.

---

## Pillar 2 — Open data

**What:** the complete training dataset for the base iteration **and** the
recipe to rebuild it. The recipe includes the source manifest (origins,
licenses, content hashes), the ingestion code, and the audit report. The
audit report records what the pipeline included and excluded and why. See
[data-pipeline.md](data-pipeline.md) for the full pipeline and its
reproducibility contract.

**Where:** published alongside the model release with a dataset card.

**Why it matters:** data is the pillar most often left closed, and it is the
one that makes results actually reproducible. Open data means a researcher
can check for contamination, measure composition effects, or rebuild a
variant. A layperson can literally see what the model studied. The pipeline
enforces provenance *before* processing (the license gate) instead of
auditing it after.

**Status:** in design; the pipeline specification is public ahead of the
implementation so the guarantees are on record first.

---

## Pillar 3 — Open weights

**What:** the trained checkpoints of the base model — parameters **plus** the
dendritically grown structure. In Arboris, the grown structure is part of
what training produces. Each release also carries the training config, the
exact dataset version consumed, evaluation results, and a model card. The
model card documents capabilities and limitations. See
[training-pipeline.md](training-pipeline.md) for what a checkpoint bundles.

**Where:** Hugging Face,
<https://huggingface.co/CoastalDigitalResearch/Arboris>, published by Coastal
Digital Research.

**Why it matters:** open weights make the model a usable artifact, not just a
described one. Researchers can probe the grown structure directly; in a
dendritic model, the learned *shape* is itself a scientific result.
Practitioners can run, fine-tune, or fork the model without asking
permission.

**Status:** no weights released yet. When training runs complete and meet the
evaluation criteria, Coastal Digital Research will publish the base
iteration's checkpoints.

---

## Scope and honesty notes

- **"Base iteration"** means the first trained release of Arboris: its code,
  its dataset, and its weights are all open as described above. We expect
  future iterations to follow the same policy for artifacts published under
  this project. The commitment stated here, however, is for the base
  iteration.
- **Pre-alpha means pre-alpha:** today the code is a scaffold, and the
  dataset and weights do not exist yet. This document states commitments and
  design, published deliberately *before* the artifacts, so the project can
  be held to them.

## Summary table

| Pillar | Artifact | License / terms | Home | Status |
|---|---|---|---|---|
| Source | Architecture, pipelines, eval code | Apache-2.0 | This repo | Scaffold public, in development |
| Data | Base dataset + manifest + rebuild recipe + audit report | Open release with per-source provenance | With model release | In design |
| Weights | Base checkpoints + grown structure + configs + model card | Open release | [Hugging Face](https://huggingface.co/CoastalDigitalResearch/Arboris) | Pending training |
