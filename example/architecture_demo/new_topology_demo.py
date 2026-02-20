"""Demo 1 — Defining a new topology.

Shows how thin a new topology class is under the refactored architecture.
A hypothetical YbRepeaterTopo (Ytterbium repeater network) is defined in
~10 lines of real code. The rest is docs and deprecated-attr backwards compat.

Compare to the old RouterNetTopo which was ~220 lines doing the same job.
"""

from sequence.topology.topology import Topology
from sequence.topology.network_impls import BsmNetworkImpl
from sequence.topology.const_topo import BSM_NODE, QUANTUM_ROUTER

# Placeholder — YbNode would extend QuantumRouter with Yb-specific hardware
# and implement from_config. See node_workflow_demo.py for the full process.
from sequence.topology.node import QuantumRouter as YbNode  # swap when real


YB_NODE = "YbNode"  # would live in const_topo.py alongside NodeType.YB_NODE


class YbRepeaterTopo(Topology):
    """Ytterbium neutral-atom repeater network.

    Nodes:    YbNode (long-coherence repeater endpoints)
    Midpoint: BSMNode (auto-created at link midpoints)
    Routing:  static or distributed (inherited from BsmNetworkImpl)
    """

    NODE_TYPES = {YB_NODE: YbNode}

    def __init__(self, conf_file_name: str):
        super().__init__(conf_file_name, BsmNetworkImpl())

# That's the entire topology class. 5 lines of real code.
# BsmNetworkImpl handles all BSM infrastructure, forwarding tables,
# qconnection auto-creation, and node dispatch via NODE_TYPES.


# ── Its config file (shown as a dict for demo purposes) ──────────────────────

YB_NETWORK_CONFIG = {
    "stop_time": 2e12,
    "templates": {
        "yb_memory": {
            "MemoryArray": {
                "fidelity":      0.99,
                "frequency":     1000,
                "efficiency":    0.95,
                "coherence_time": 20,
                "wavelength":    1389,
            }
        }
    },
    "nodes": [
        {"name": "yb1", "type": "YbNode", "seed": 0,
         "memo_size": 10, "template": "yb_memory"},
        {"name": "yb2", "type": "YbNode", "seed": 1,
         "memo_size": 10, "template": "yb_memory"},
        {"name": "yb3", "type": "YbNode", "seed": 2,
         "memo_size": 10, "template": "yb_memory"},
    ],
    "qconnections": [
        {"node1": "yb1", "node2": "yb2", "attenuation": 0.0002,
         "distance": 10000, "type": "meet_in_the_middle"},
        {"node1": "yb2", "node2": "yb3", "attenuation": 0.0002,
         "distance": 10000, "type": "meet_in_the_middle"},
    ],
    "cconnections": [
        {"node1": "yb1", "node2": "yb2", "delay": 50_000_000},
        {"node1": "yb2", "node2": "yb3", "delay": 50_000_000},
    ],
}

# Notice: no flat hardware keys anywhere. All hardware lives in templates.
# The topology class never needs to know about Yb-specific params.


# ── The same network with CreateTopo — no config file at all ─────────────────

from sequence.topology.create_topo import CreateTopo

def build_yb_network_programmatic():
    return CreateTopo(
        impl       = BsmNetworkImpl(),
        node_types = {YB_NODE: YbNode},
        nodes      = [
            {"name": "yb1", "type": "YbNode", "seed": 0,
             "memo_size": 10, "template": "yb_memory"},
            {"name": "yb2", "type": "YbNode", "seed": 1,
             "memo_size": 10, "template": "yb_memory"},
            {"name": "yb3", "type": "YbNode", "seed": 2,
             "memo_size": 10, "template": "yb_memory"},
        ],
        templates  = {
            "yb_memory": {"MemoryArray": {
                "fidelity": 0.99, "frequency": 1000,
                "efficiency": 0.95, "coherence_time": 20, "wavelength": 1389,
            }}
        },
        qconnections = [
            {"node1": "yb1", "node2": "yb2", "attenuation": 0.0002,
             "distance": 10000, "type": "meet_in_the_middle"},
            {"node1": "yb2", "node2": "yb3", "attenuation": 0.0002,
             "distance": 10000, "type": "meet_in_the_middle"},
        ],
        cconnections = [
            {"node1": "yb1", "node2": "yb2", "delay": 50_000_000},
            {"node1": "yb2", "node2": "yb3", "delay": 50_000_000},
        ],
        stop_time = 2e12,
    )

# Same network. No file on disk. Pure Python.
