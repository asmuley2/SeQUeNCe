"""Concrete NetworkImpl subclasses.

All topology implementors live here. To add a new topology family,
add a new NetworkImpl subclass and register it in the relevant topology file.
"""

from .topology import NetworkImpl
from .qlan.orchestrator import QlanOrchestratorNode
from .qlan.client import QlanClientNode

from networkx import Graph, dijkstra_path, exception

from ..network_management.routing_distributed import DistributedRoutingProtocol
from ..network_management.routing_static import StaticRoutingProtocol

from .node import BSMNode
from .const_topo import (
    ALL_NODE, ALL_Q_CHANNEL, ALL_C_CHANNEL,
    ATTENUATION, BSM_NODE, CONNECT_NODE_1, CONNECT_NODE_2,
    DELAY, DISTANCE, MEET_IN_THE_MID,
    MEMO_ARRAY_SIZE, DATA_MEMO_ARRAY_SIZE,
    NAME, SEED, SRC, DST, TEMPLATE, TYPE,
    ORCHESTRATOR, CLIENT,
    NodeType, MIDPOINT_NODE_TYPES,
)


# Config keys that double as constructor param names — harvested per-node in _add_parameters.
_NODE_CONSTRUCTOR_PARAMS = (MEMO_ARRAY_SIZE, DATA_MEMO_ARRAY_SIZE) #TODO: enumify this one to maybe

class NoOpNetworkImpl(NetworkImpl):
    """Minimal impl for topologies that manage their own node creation and
    inherit from class Topology without need for BSM/QLAN infrastructure
    """

    def _create_node(self, node_config, node_type, template,
                     tl, nodes, bsm_to_router_map, node_types) -> None:
        raise NotImplementedError(
            "NoOpNetworkImpl does not create nodes. "
            "The topology must override _add_nodes itself."
        )


class BsmNetworkImpl(NetworkImpl):
    """Implementor for BSM-based entanglement distribution networks.

    Used by RouterNetTopo and DQCNetTopo. Owns BSM node auto-creation,
    router-BSM wiring, and forwarding table generation.
    """

    def _add_parameters(self, config: dict, topo) -> None:
        """Pre-read per-node constructor kwargs from config.

        MEMO_ARRAY_SIZE == "memo_size" and DATA_MEMO_ARRAY_SIZE == "data_memo_size",
        so harvested keys are identical to constructor param names and can be
        splatted directly in _create_node — no type-specific dispatch needed.
        """
        self._node_kwargs = {
            node[NAME]: {k: node[k] for k in _NODE_CONSTRUCTOR_PARAMS if k in node}
            for node in config.get(ALL_NODE, [])
        }

    def _map_bsm_routers(self, config: dict, bsm_to_router_map: dict) -> None:
        for qc in config[ALL_Q_CHANNEL]:
            src, dst = qc[SRC], qc[DST]
            if dst in bsm_to_router_map:
                bsm_to_router_map[dst].append(src)
            else:
                bsm_to_router_map[dst] = [src]

    def _add_bsm_node_to_router(self, bsm_to_router_map: dict, tl) -> None:
        for bsm in bsm_to_router_map:
            r0_str, r1_str = bsm_to_router_map[bsm]
            r0 = tl.get_entity_by_name(r0_str)
            r1 = tl.get_entity_by_name(r1_str)
            if r0 is not None:
                r0.add_bsm_node(bsm, r1_str)
            if r1 is not None:
                r1.add_bsm_node(bsm, r0_str)

    def _handle_qconnection(self, q_connect: dict, cc_delay: float, config: dict) -> None:
        node1        = q_connect[CONNECT_NODE_1]
        node2        = q_connect[CONNECT_NODE_2]
        attenuation  = q_connect[ATTENUATION]
        distance     = q_connect[DISTANCE] // 2
        channel_type = q_connect[TYPE]

        if channel_type == MEET_IN_THE_MID:
            # .auto suffix distinguishes auto-generated BSM nodes from manually specified ones
            bsm_name = f"BSM.{node1}.{node2}.auto"
            config[ALL_NODE].append({
                NAME:     bsm_name,
                TYPE:     BSM_NODE,
                SEED:     q_connect.get(SEED, 0),
                TEMPLATE: q_connect.get(TEMPLATE, None),
            })
            for src in [node1, node2]:
                config.setdefault(ALL_Q_CHANNEL, []).append({
                    NAME: f"QC.{src}.{bsm_name}", SRC: src,
                    DST: bsm_name, DISTANCE: distance, ATTENUATION: attenuation,
                })
                config.setdefault(ALL_C_CHANNEL, []).append({
                    NAME: f"CC.{src}.{bsm_name}", SRC: src,
                    DST: bsm_name, DISTANCE: distance, DELAY: cc_delay,
                })
                config[ALL_C_CHANNEL].append({
                    NAME: f"CC.{bsm_name}.{src}", SRC: bsm_name,
                    DST: src, DISTANCE: distance, DELAY: cc_delay,
                })
        else:
            raise NotImplementedError(f"Unknown quantum connection type '{channel_type}'")

    def _generate_forwarding_table(self, config: dict, nodes: dict, qchannels: list) -> None:
        graph = Graph()
        for node in config[ALL_NODE]:
            if NodeType(node[TYPE]) not in MIDPOINT_NODE_TYPES:
                graph.add_node(node[NAME])

        costs = {}
        for qc in qchannels:
            router, bsm = qc.sender.name, qc.receiver
            if bsm not in costs:
                costs[bsm] = [router, qc.distance]
            else:
                costs[bsm] = [router] + costs[bsm]
                costs[bsm][-1] += qc.distance

        routing_protocol = None
        for node_type, node_list in nodes.items():
            if NodeType(node_type) not in MIDPOINT_NODE_TYPES and node_list:
                routing_protocol = node_list[0].network_manager.get_routing_protocol()
                break

        if isinstance(routing_protocol, StaticRoutingProtocol):
            graph.add_weighted_edges_from(costs.values())
            for node_type, node_list in nodes.items():
                if NodeType(node_type) in MIDPOINT_NODE_TYPES:
                    continue
                for src in node_list:
                    for dst_name in graph.nodes:
                        if src.name == dst_name:
                            continue
                        try:
                            if dst_name > src.name:
                                path = dijkstra_path(graph, src.name, dst_name)
                            else:
                                path = dijkstra_path(graph, dst_name, src.name)[::-1]
                            routing_protocol = src.network_manager.get_routing_protocol()
                            routing_protocol.add_forwarding_rule(dst_name, path[1])
                        except exception.NetworkXNoPath:
                            pass

        elif isinstance(routing_protocol, DistributedRoutingProtocol):
            for node_type, node_list in nodes.items():
                if NodeType(node_type) in MIDPOINT_NODE_TYPES:
                    continue
                for q_router in node_list:
                    routing_protocol: DistributedRoutingProtocol = \
                        q_router.network_manager.get_routing_protocol()
                    for bsm, cost_info in costs.items():
                        if q_router.name in cost_info:
                            neighbor = cost_info[0] if cost_info[0] != q_router.name \
                                       else cost_info[1]
                            routing_protocol.link_cost[neighbor] = cost_info[2]
                    routing_protocol.init()

    def _create_node(self, node_config: dict, node_type: str, template: dict,
                     tl, nodes: dict, bsm_to_router_map: dict, node_types: dict) -> None:
        match NodeType(node_type):
            case NodeType.BSM_NODE:
                # BSMNode needs bsm_to_router_map — cannot use generic from_config
                others   = bsm_to_router_map[node_config[NAME]]
                node_obj = BSMNode(node_config[NAME], tl, others, component_templates=template)
            case _:
                if node_type not in node_types:
                    raise NotImplementedError(
                        f"NodeType '{node_type}' has no entry in NODE_TYPES. "
                        f"Register it in the topology's NODE_TYPES dict."
                    )
                kwargs = self._node_kwargs.get(node_config[NAME], {})
                node_obj = node_types[node_type](
                    node_config[NAME], tl,
                    **kwargs,
                    component_templates=template,
                )
        node_obj.set_seed(node_config[SEED])
        nodes[node_type].append(node_obj)



class QlanNetworkImpl(NetworkImpl):
    """Implementor for QLAN star topologies.

    Owns QLAN-specific parameter reading (dual flat/template format),
    node ordering (clients before orchestrator), and node construction.
    """

    def _add_parameters(self, config: dict, topo) -> None:
        # Structural params are already on topo (set by Topology._add_qlan_parameters).
        # Pull only what _create_node needs at construction time.
        self.n_local_memories  = topo.n_local_memories
        self.meas_bases        = topo.meas_bases

        # Accumulator lists — populated by _create_node, exposed on topo after init.
        self._remote_memories      = []
        self.orchestrator_nodes    = []
        self.client_nodes          = []
        self.remote_memories_array = []

    def _ordered_node_dicts(self, node_list: list) -> list:
        """Sort clients before orchestrators so single-pass construction works.

        By the time _create_node hits an orchestrator, all client Memory objects
        already exist in self._remote_memories.
        """
        clients       = [n for n in node_list if n[TYPE] == CLIENT]
        orchestrators = [n for n in node_list if n[TYPE] == ORCHESTRATOR]
        others        = [n for n in node_list if n[TYPE] not in (CLIENT, ORCHESTRATOR)]
        return others + clients + orchestrators  # TODO: test edge case behaviour

    def _create_node(self, node_config: dict, node_type: str, template: dict,
                     tl, nodes: dict, bsm_to_router_map: dict, node_types: dict) -> None:
        """Construct QLAN nodes. Template MemoryArray values take precedence over flat fallbacks."""
        memo_arr = template.get("MemoryArray", {})

        if node_type == CLIENT:
            node_obj = QlanClientNode(
                node_config[NAME], tl, 1,
                memo_arr.get("fidelity",       0.9),
                memo_arr.get("frequency",      2000),
                memo_arr.get("efficiency",     1),
                memo_arr.get("coherence_time", -1),
                memo_arr.get("wavelength",     500),
            )
            node_obj.set_seed(node_config[SEED])
            memo = node_obj.get_components_by_type("Memory")[0]
            self._remote_memories.append(memo)
            self.remote_memories_array.append(memo)
            self.client_nodes.append(node_obj)
            nodes[node_type].append(node_obj)

        elif node_type == ORCHESTRATOR:
            node_obj = QlanOrchestratorNode(
                node_config[NAME], tl,
                self.n_local_memories,
                self._remote_memories,
                memo_arr.get("fidelity",       0.9),
                memo_arr.get("frequency",      2000),
                memo_arr.get("efficiency",     1),
                memo_arr.get("coherence_time", -1),
                memo_arr.get("wavelength",     500),
            )
            node_obj.update_bases(self.meas_bases)
            node_obj.set_seed(node_config[SEED])
            self.orchestrator_nodes.append(node_obj)
            nodes[node_type].append(node_obj)

        else:
            raise ValueError(f"Unknown QLAN node type '{node_type}'")
