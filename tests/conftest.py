import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ontology-playground"


@pytest.fixture()
def coffee_fixture():
    """The Fourth Coffee ontology from the testbed corpus if built locally,
    else an equivalent inline miniature so tests never require network."""
    path = FIXTURES / "fixtures.json"
    if path.is_file():
        for fx in json.loads(path.read_text()):
            if fx["id"] == "official/cosmic-coffee":
                return fx
    return {
        "id": "inline/coffee-mini",
        "graph": {
            "nodes": [
                {"id": "customer", "name": "Customer", "description": "a person who buys coffee"},
                {"id": "order", "name": "Order", "description": "a purchase of products"},
                {"id": "product", "name": "Product", "description": "a coffee drink for sale"},
                {"id": "store", "name": "Store", "description": "a coffee shop location"},
                {"id": "supplier", "name": "Supplier", "description": "provides coffee beans"},
                {"id": "bean", "name": "Bean", "description": "green coffee beans"},
            ],
            "edges": [
                {"id": "e1", "source": "customer", "target": "order", "relation": "places"},
                {"id": "e2", "source": "order", "target": "product", "relation": "contains"},
                {"id": "e3", "source": "order", "target": "store", "relation": "processedAt"},
                {"id": "e4", "source": "supplier", "target": "bean", "relation": "provides"},
                {"id": "e5", "source": "product", "target": "bean", "relation": "madeFrom"},
            ],
        },
    }
