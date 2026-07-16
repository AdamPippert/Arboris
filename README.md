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

## Layout

```
src/arboris/     library code (architecture, training, eval) — WIP
LICENSE, NOTICE  Apache-2.0
```

## Partnership

Arboris is developed by Adam Pippert as independent research. Coastal Digital
Research trains and publishes the models on Hugging Face:
<https://huggingface.co/CoastalDigitalResearch/Arboris>.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
