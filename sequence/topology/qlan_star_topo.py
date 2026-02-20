"""QlanStarTopo — QLAN star topology with one orchestrator and multiple clients."""

from .topology import Topology
from .network_impls import QlanNetworkImpl
from .qlan.orchestrator import QlanOrchestratorNode
from .qlan.client import QlanClientNode
from .const_topo import (
    CLIENT, CLIENT_NUMBER, LOCAL_MEMORIES, MEASUREMENT_BASES, MEET_IN_THE_MID,
    MEM_COHERENCE_CLIENT, MEM_COHERENCE_ORCH,
    MEM_EFFICIENCY_CLIENT, MEM_EFFICIENCY_ORCH,
    MEM_FIDELITY_CLIENT, MEM_FIDELITY_ORCH,
    MEM_FREQUENCY_CLIENT, MEM_FREQUENCY_ORCH,
    MEM_SIZE, MEM_WAVELENGTH_CLIENT, MEM_WAVELENGTH_ORCH,
    ORCHESTRATOR,
)


class QlanStarTopo(Topology):
    """Topology for QLAN networks with a single orchestrator and multiple clients.

    Entanglement is generated abstractly (linear chain graph state injected directly).
    No BSM nodes. No routing table.

    Attributes:
        orchestrator_nodes (list[QlanOrchestratorNode]): orchestrator nodes.
        client_nodes (list[QlanClientNode]): client nodes.
        remote_memories_array (list[Memory]): client memory objects.
        nodes (dict[str, list[Node]]): mapping of node type to list of nodes.
        qchannels (list[QuantumChannel]): quantum channels in the network.
        cchannels (list[ClassicalChannel]): classical channels in the network.
        tl (Timeline): simulation timeline.
    """

    NODE_TYPES = {
        ORCHESTRATOR: QlanOrchestratorNode,
        CLIENT:       QlanClientNode,
    }

    _deprecated_attrs = {
        "MEET_IN_THE_MID":      MEET_IN_THE_MID,
        "ORCHESTRATOR":         ORCHESTRATOR,
        "CLIENT":               CLIENT,
        "LOCAL_MEMORIES":       LOCAL_MEMORIES,
        "CLIENT_NUMBER":        CLIENT_NUMBER,
        "MEM_FIDELITY_ORCH":    MEM_FIDELITY_ORCH,
        "MEM_FREQUENCY_ORCH":   MEM_FREQUENCY_ORCH,
        "MEM_EFFICIENCY_ORCH":  MEM_EFFICIENCY_ORCH,
        "MEM_COHERENCE_ORCH":   MEM_COHERENCE_ORCH,
        "MEM_WAVELENGTH_ORCH":  MEM_WAVELENGTH_ORCH,
        "MEM_FIDELITY_CLIENT":  MEM_FIDELITY_CLIENT,
        "MEM_FREQUENCY_CLIENT": MEM_FREQUENCY_CLIENT,
        "MEM_EFFICIENCY_CLIENT": MEM_EFFICIENCY_CLIENT,
        "MEM_COHERENCE_CLIENT": MEM_COHERENCE_CLIENT,
        "MEM_WAVELENGTH_CLIENT": MEM_WAVELENGTH_CLIENT,
        "MEASUREMENT_BASES":    MEASUREMENT_BASES,
        "MEM_SIZE":             MEM_SIZE,
    }

    def __init__(self, conf_file_name: str):
        impl = QlanNetworkImpl()
        super().__init__(conf_file_name, impl)
        # Expose impl's populated lists as topology attributes for public API
        self.orchestrator_nodes    = impl.orchestrator_nodes
        self.client_nodes          = impl.client_nodes
        self.remote_memories_array = impl.remote_memories_array

    def _add_protocols(self):
        """Wire measurement and correction protocols on all nodes."""
        for orch in self._impl.orchestrator_nodes:
            orch.resource_manager.create_protocol()
        for client in self._impl.client_nodes:
            client.resource_manager.create_protocol()
