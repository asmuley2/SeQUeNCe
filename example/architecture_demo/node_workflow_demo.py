"""Demo 2 - Adding a new node type end-to-end.

Step 1: Add to NodeType enum in const_topo.py
Step 2: Define the node class and register it in your topology's NODE_TYPES
Step 3: Add it to the midpoint dispatch dict if it's a midpoint node
Step 4: Done - everything else is inherited
"""

# Step 1: in const_topo.py add one line to NodeType:
#
#   class NodeType(Enum):
#       QUANTUM_ROUTER = "QuantumRouter"
#       DQC_NODE       = "DQCNode"
#       BSM_NODE       = "BSMNode"
#       YB_NODE        = "YbNode"    # <- add this
#
# and add it to ENDPOINT_NODE_TYPES:
#   ENDPOINT_NODE_TYPES = frozenset({
#       NodeType.QUANTUM_ROUTER,
#       NodeType.DQC_NODE,
#       NodeType.YB_NODE,           # <- add this
#   })


# Step 2: define the class and register it
#
# BsmNetworkImpl._add_parameters harvests memo_size (and data_memo_size)
# from the config and passes them as kwargs to the constructor, so if your
# new node type is hardware-only the class body can be empty:

from sequence.topology.node import QuantumRouter, BSMNode
from sequence.topology.const_topo import NodeType, MIDPOINT_NODE_TYPES, NAME

YB_NODE = "YbNode"  # would live in const_topo.py alongside NodeType.YB_NODE


class YbNode(QuantumRouter):
    """Ytterbium neutral-atom quantum repeater node.

    Hardware differences (1389 nm wavelength, 20 s coherence) live in
    the config template - no constructor overrides needed.
    """


# BsmNetworkImpl constructs it as:
#   YbNode(name, tl, memo_size=config_value, component_templates=template)
# which matches QuantumRouter.__init__ exactly.

from sequence.topology.topology import Topology
from sequence.topology.network_impls import BsmNetworkImpl


class YbRepeaterTopo(Topology):
    NODE_TYPES = {YB_NODE: YbNode}

    def __init__(self, conf_file_name: str):
        super().__init__(conf_file_name, BsmNetworkImpl())


# If you forget to register, _create_node raises immediately:
#   NotImplementedError: NodeType 'YbNode' has no entry in NODE_TYPES.
#   Register it in the topology's NODE_TYPES dict.


# Step 3: add a handler to the node constructor dispatch dict
#
# Every NodeType must have an entry here. The assertion below fires at import
# time when the codebase grows and someone adds a NodeType without a handler.
# This is the same idea as Rust exhaustive matching, just enforced at startup.

from sequence.topology.const_topo import NodeType

def _make_bsm_node(cfg, tl, tmpl, node_types, kwargs, bsm_map):
    return BSMNode(cfg[NAME], tl, bsm_map[cfg[NAME]], component_templates=tmpl)

def _make_endpoint_node(cfg, tl, tmpl, node_types, kwargs, bsm_map):
    return node_types[cfg["type"]](cfg[NAME], tl, **kwargs, component_templates=tmpl)

_NODE_CONSTRUCTORS = {
    NodeType.BSM_NODE:        _make_bsm_node,
    NodeType.QUANTUM_ROUTER:  _make_endpoint_node,
    NodeType.DQC_NODE:        _make_endpoint_node,
    NodeType.QKD_NODE:        _make_endpoint_node,
    NodeType.ORCHESTRATOR:    _make_endpoint_node,
    NodeType.CLIENT:          _make_endpoint_node,
    # NodeType.YB_NODE:       _make_endpoint_node,
}

_missing = frozenset(NodeType) - set(_NODE_CONSTRUCTORS)
if _missing:
    raise TypeError(
        f"_NODE_CONSTRUCTORS is missing entries for: "
        f"{[t.value for t in _missing]}. "
        f"Add a handler or update the NodeType enum."
    )

# _create_node dispatch then looks like:
#
#   nt = NodeType(node_type)
#   node_obj = _NODE_CONSTRUCTORS[nt](
#       node_config, tl, template, node_types, kwargs, bsm_to_router_map
#   )


# Step 4: done
#
# Didn't touch:
#   - Topology base class or other topology subclasses
#   - BsmNetworkImpl
#   - forwarding table logic
#   - channel creation
#   - tests for other topologies
#
# When you DO need a non-trivial class body: override __init__ only when you
# need behaviour QuantumRouter doesn't provide. BsmNetworkImpl still calls the
# constructor the same way so your __init__ just needs to accept the same args.
