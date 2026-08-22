from __future__ import annotations

import networkx as nx

from core.models import BuildData, Part, Step


class BuildContext:
    """Indexed, in-memory view of a BuildData: id lookups + the Step dependency graph.

    Built once (from a parsed BuildData) and shared by every core function and the
    API layer, so nothing has to linearly scan build_data.steps/parts to find a
    step or part by id.
    """

    def __init__(self, build_data: BuildData):
        self.build_data = build_data
        self.parts_by_id: dict[str, Part] = {p.id: p for p in build_data.parts}
        self.steps_by_id: dict[str, Step] = {s.id: s for s in build_data.steps}
        self.graph: nx.DiGraph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        graph: nx.DiGraph = nx.DiGraph()
        for step in self.build_data.steps:
            graph.add_node(step.id)
        for step in self.build_data.steps:
            for prior_id in step.required_prior_steps:
                # edge direction: prior_id must happen before step.id
                graph.add_edge(prior_id, step.id)
        return graph
