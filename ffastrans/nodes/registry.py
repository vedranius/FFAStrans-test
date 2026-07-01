"""Node registry - maps node type strings to their classes."""
from .monitor_nodes import MONITOR_NODES
from .encoder_nodes import ENCODER_NODES
from .decoder_nodes import DECODER_NODES
from .filter_nodes import FILTER_NODES
from .operator_nodes import OPERATOR_NODES
from .base import BaseNode
from ..core.models import Node, Job
from ..core.variables import VariableEngine


ALL_NODES = {}
ALL_NODES.update(MONITOR_NODES)
ALL_NODES.update(ENCODER_NODES)
ALL_NODES.update(DECODER_NODES)
ALL_NODES.update(FILTER_NODES)
ALL_NODES.update(OPERATOR_NODES)

NODE_CATEGORIES = {
    "Monitors": {k: v.node_type for k, v in MONITOR_NODES.items()},
    "Decoders": {k: v.node_type for k, v in DECODER_NODES.items()},
    "Encoders": {k: v.node_type for k, v in ENCODER_NODES.items()},
    "Filters": {k: v.node_type for k, v in FILTER_NODES.items()},
    "Operators": {k: v.node_type for k, v in OPERATOR_NODES.items()},
}


def get_node_class(node_type: str) -> type | None:
    return ALL_NODES.get(node_type)


def create_node_instance(node: Node, job: Job, var_engine: VariableEngine) -> BaseNode | None:
    cls = get_node_class(node.node_type)
    if cls is None:
        return None
    return cls(node=node, job=job, var_engine=var_engine)


def list_available_nodes() -> dict:
    result = {}
    for category, nodes in NODE_CATEGORIES.items():
        result[category] = []
        for name, ntype in nodes.items():
            result[category].append({
                "name": name,
                "type": ntype,
            })
    return result
