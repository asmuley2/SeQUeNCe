"""Topology configuration key constants and node type enumerations."""

from enum import Enum


class NodeType(Enum):
    """All known node types in the simulation.

    String values match the TYPE strings used in config files and NODE_TYPES dicts.
    Add new node types here — the _unclassified check below fires at import time if
    you forget to classify the new member as MIDPOINT or ENDPOINT.
    """
    QUANTUM_ROUTER = "QuantumRouter"
    DQC_NODE       = "DQCNode"
    BSM_NODE       = "BSMNode"
    QKD_NODE       = "QKDNode"
    ORCHESTRATOR   = "QlanOrchestratorNode"
    CLIENT         = "QlanClientNode"
    # Future:
    # YB_NODE      = "YbNode"
    # ER_NODE      = "ErNode"
    # HET_BSM_NODE = "HetBSMNode"


# Midpoint nodes — sit between two endpoints, never appear in routing tables.
# Add new BSM variants here when heterogeneous hardware is introduced.
MIDPOINT_NODE_TYPES = frozenset({
    NodeType.BSM_NODE,
})

# Endpoint nodes — participate in routing and computation.
ENDPOINT_NODE_TYPES = frozenset({
    NodeType.QUANTUM_ROUTER,
    NodeType.DQC_NODE,
    NodeType.QKD_NODE,
    NodeType.ORCHESTRATOR,
    NodeType.CLIENT,
})

# Every NodeType member must belong to exactly one classification set.
# This fires at import time — adding a new NodeType without classifying it
# is a hard error, not a silent wrong simulation.
_unclassified = frozenset(NodeType) - MIDPOINT_NODE_TYPES - ENDPOINT_NODE_TYPES
if _unclassified:
    raise TypeError(
        f"NodeType members are not classified as MIDPOINT or ENDPOINT: "
        f"{[t.value for t in _unclassified]}. "
        f"Add them to MIDPOINT_NODE_TYPES or ENDPOINT_NODE_TYPES in const_topo.py."
    )

# Topology base config keys
ALL_C_CONNECT = "cconnections"
ALL_C_CHANNEL = "cchannels"
ALL_NODE = "nodes"
ALL_Q_CONNECT = "qconnections"
ALL_Q_CHANNEL = "qchannels"
ATTENUATION = "attenuation"
CONNECT_NODE_1 = "node1"
CONNECT_NODE_2 = "node2"
DELAY = "delay"
DISTANCE = "distance"
DST = "destination"
NAME = "name"
SEED = "seed"
SRC = "source"
STOP_TIME = "stop_time"
TRUNC = "truncation"
TYPE = "type"
ALL_TEMPLATES = "templates"
TEMPLATE = "template"
GATE_FIDELITY = "gate_fidelity"
MEASUREMENT_FIDELITY = "measurement_fidelity"
FORMALISM = "formalism"

# RouterNetTopo config keys
BSM_NODE = "BSMNode"
MEET_IN_THE_MID = "meet_in_the_middle"
MEMO_ARRAY_SIZE = "memo_size"
PORT = "port"
PROC_NUM = "process_num"
QUANTUM_ROUTER = "QuantumRouter"
CONTROLLER = "Controller"

# QKDTopo config keys
QKD_NODE = "QKDNode"

# QlanStarTopo config keys
ORCHESTRATOR = "QlanOrchestratorNode"
CLIENT = "QlanClientNode"
LOCAL_MEMORIES = "local_memories"
CLIENT_NUMBER = "client_number"
MEM_FIDELITY_ORCH = "memo_fidelity_orch"
MEM_FREQUENCY_ORCH = "memo_frequency_orch"
MEM_EFFICIENCY_ORCH = "memo_efficiency_orch"
MEM_COHERENCE_ORCH = "memo_coherence_orch"
MEM_WAVELENGTH_ORCH = "memo_wavelength_orch"
MEM_FIDELITY_CLIENT = "memo_fidelity_client"
MEM_FREQUENCY_CLIENT = "memo_frequency_client"
MEM_EFFICIENCY_CLIENT = "memo_efficiency_client"
MEM_COHERENCE_CLIENT = "memo_coherence_client"
MEM_WAVELENGTH_CLIENT = "memo_wavelength_client"
MEASUREMENT_BASES = "measurement_bases"
MEM_SIZE = "memo_size"

# DQCNetTopo config keys
DQC_NODE = "DQCNode"
DATA_MEMO_ARRAY_SIZE = "data_memo_size"
