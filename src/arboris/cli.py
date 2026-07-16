"""Arboris command line entry point.

Only implemented commands are exposed; later migration stages add data, simulator,
training, evaluation, and pack command groups.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

from .ontology import Ontology
from .schemas import StateGraph

app = typer.Typer(help="Arboris structured world-model research tools.")
ontology_app = typer.Typer(help="Inspect and validate versioned ontologies.")
app.add_typer(ontology_app, name="ontology")


@ontology_app.command("validate")
def validate_ontology(
    ontology: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    graph: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Load an ontology and optionally validate a serialized StateGraph."""
    contract = Ontology.load(ontology)
    issues = (
        []
        if graph is None
        else contract.validate(StateGraph.model_validate_json(graph.read_text()))
    )
    result = {
        "ontology_version": contract.version,
        "valid": not issues,
        "issues": [i.model_dump() for i in issues],
    }
    if json_output:
        typer.echo(json.dumps(result, default=str, sort_keys=True))
    else:
        typer.echo(
            f"{contract.version}: {'valid' if not issues else 'invalid'} ({len(issues)} issues)"
        )
    if issues:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
