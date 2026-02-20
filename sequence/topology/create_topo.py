"""CreateTopo — programmatic topology construction without JSON config files.

Instead of writing a config file and passing its path, users pass Python
dicts directly. This is the recommended entry point for interactive use,
notebooks, and rapid prototyping.

Example:
    from sequence.topology.create_topo import CreateTopo
    from sequence.topology.network_impls import BsmNetworkImpl
    from sequence.topology.node import QuantumRouter
    from sequence.topology.const_topo import QUANTUM_ROUTER

    topo = CreateTopo(
        impl       = BsmNetworkImpl(),
        node_types = {QUANTUM_ROUTER: QuantumRouter},
        nodes      = [
            {"name": "r1", "type": "QuantumRouter", "seed": 0, "memo_size": 20,
             "template": "high_fidelity"},
            {"name": "r2", "type": "QuantumRouter", "seed": 1, "memo_size": 20},
        ],
        templates  = {
            "high_fidelity": {"MemoryArray": {"fidelity": 1.0}},
        },
        qconnections = [
            {"node1": "r1", "node2": "r2", "attenuation": 0.0002,
             "distance": 2000, "type": "meet_in_the_middle"},
        ],
        cconnections = [
            {"node1": "r1", "node2": "r2", "delay": 1_000_000_000},
        ],
        stop_time = 1e12,
    )
"""

from collections import defaultdict
from .topology import Topology, NetworkImpl
from .const_topo import (
    ALL_C_CHANNEL, ALL_C_CONNECT, ALL_NODE, ALL_Q_CHANNEL,
    ALL_Q_CONNECT, ALL_TEMPLATES, STOP_TIME, TRUNC, FORMALISM,
)


class CreateTopo(Topology):
    """Topology built from Python dicts — no config file required.

    Accepts the same data that would go in a JSON config, but as keyword
    arguments. Ideal for notebooks, quick experiments, and programmatic
    network generation.

    Args:
        impl (NetworkImpl):      the implementor for this topology family
        node_types (dict):       NODE_TYPES mapping {type_str: NodeClass}
        nodes (list[dict]):      node descriptors (name, type, seed, ...)
        templates (dict):        hardware templates keyed by template name
        qconnections (list):     quantum connection descriptors
        cconnections (list):     classical connection descriptors
        qchannels (list):        explicit quantum channel descriptors (optional)
        cchannels (list):        explicit classical channel descriptors (optional)
        stop_time (float):       simulation stop time
        formalism (str):         quantum state formalism (default: ket state)
        truncation (int):        Hilbert space truncation for Fock formalism
        **extra:                 any additional top-level config keys
                                 (e.g. QLAN structural params like local_memories)
    """

    def __init__(
        self,
        impl:         NetworkImpl,
        node_types:   dict,
        nodes:        list[dict],
        templates:    dict       = None,
        qconnections: list[dict] = None,
        cconnections: list[dict] = None,
        qchannels:    list[dict] = None,
        cchannels:    list[dict] = None,
        stop_time:    float      = float('inf'),
        formalism:    str        = None,
        truncation:   int        = 1,
        **extra,
    ):
        self.NODE_TYPES = node_types
        self._setup(impl)

        config = {
            ALL_NODE:      nodes,
            ALL_TEMPLATES: templates    or {},
            ALL_Q_CONNECT: qconnections or [],
            ALL_C_CONNECT: cconnections or [],
            ALL_Q_CHANNEL: qchannels    or [],
            ALL_C_CHANNEL: cchannels    or [],
            STOP_TIME:     stop_time,
            TRUNC:         truncation,
            **extra,
        }
        if formalism is not None:
            config[FORMALISM] = formalism

        self._raw_cfg = config
        self._run_pipeline(config)
