"""Definition of the Topology class.

This module provides a definition of the Topology class, which can be used to
manage a network's structure.
Topology instances automatically perform many useful network functions.
"""

import json
import warnings
import numpy as np

from abc import ABC, ABCMeta, abstractmethod
from collections import defaultdict

from ..kernel.timeline import Timeline
from ..kernel.quantum_manager import KET_STATE_FORMALISM, QuantumManager

from .node import *
from .const_topo import (
    ALL_C_CONNECT, ALL_C_CHANNEL, ALL_NODE, ALL_Q_CONNECT, ALL_Q_CHANNEL,
    ATTENUATION, CONNECT_NODE_1, CONNECT_NODE_2, DELAY, DISTANCE, DST,
    NAME, SEED, SRC, STOP_TIME, TRUNC, TYPE, ALL_TEMPLATES, TEMPLATE,
    GATE_FIDELITY, MEASUREMENT_FIDELITY, FORMALISM,
    ORCHESTRATOR, CLIENT,
    LOCAL_MEMORIES, CLIENT_NUMBER, MEASUREMENT_BASES,
    MEM_FIDELITY_ORCH, MEM_FREQUENCY_ORCH, MEM_EFFICIENCY_ORCH,
    MEM_COHERENCE_ORCH, MEM_WAVELENGTH_ORCH,
    MEM_FIDELITY_CLIENT, MEM_FREQUENCY_CLIENT, MEM_EFFICIENCY_CLIENT,
    MEM_COHERENCE_CLIENT, MEM_WAVELENGTH_CLIENT,
)
from ..components.optical_channel import QuantumChannel, ClassicalChannel
from ..constants import SPEED_OF_LIGHT


class NetworkImpl(ABC):
    """Abstract base for topology implementors.

    Each concrete subclass owns the infrastructure for one family of topologies
    (BSM-based nets, QLAN, etc.). Topology delegates its variable pipeline steps
    here via composition rather than inheritance.

    All methods are no-op defaults except _create_node which every impl must define.
    Concrete implementations live in network_impls.py.
    """

    def _add_parameters(self, config: dict, topo) -> None: pass

    def _map_bsm_routers(self, config: dict, bsm_to_router_map: dict) -> None: pass

    def _add_bsm_node_to_router(self, bsm_to_router_map: dict, tl) -> None: pass

    def _handle_qconnection(self, q_connect: dict, cc_delay: float, config: dict) -> None: pass

    def _generate_forwarding_table(self, config: dict, nodes: dict, qchannels: list) -> None: pass

    def _ordered_node_dicts(self, node_list: list) -> list:
        return node_list

    #every child is responsible of implementing this
    @abstractmethod
    def _create_node(self, node_config: dict, node_type: str, template: dict,
                     tl, nodes: dict, bsm_to_router_map: dict, node_types: dict) -> None:
        """Construct node, call set_seed, append to nodes[node_type].

        Args:
            node_config:       one entry from config[ALL_NODE]
            node_type:         the TYPE string for this node
            template:          resolved template dict for this node (may be empty)
            tl:                simulation timeline
            nodes:             topology's nodes defaultdict — append here
            bsm_to_router_map: needed by BSMNode construction
            node_types:        topology's NODE_TYPES dict for from_config dispatch
        """
        pass


class _DeprecatedAttrMeta(ABCMeta):
    """Metaclass that warns when deprecated class attributes are accessed.

    Each class using this metaclass can define a _deprecated_attrs dict
    mapping old attribute names to their values. The metaclass walks the
    MRO to find the right dict.
    """

    def __getattr__(cls, name):
        for klass in cls.__mro__:
            deprecated = klass.__dict__.get("_deprecated_attrs", {})
            if name in deprecated:
                warnings.warn(
                    f"Accessing {cls.__name__}.{name} is deprecated. "
                    f"Use 'from sequence.topology.const_topo import {name}' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return deprecated[name]
        raise AttributeError(
            f"type object {cls.__name__!r} has no attribute {name!r}"
        )


class Topology(ABC, metaclass=_DeprecatedAttrMeta):
    """Class for generating network from configuration file.

    The topology class provides a simple interface for managing the nodes
    and connections in a network.
    A network may also be generated using an external json file.

    Attributes:
        bsm_to_router_map (dict): mapping BSM nodes to router nodes.
        nodes (dict[str, list[Node]]): mapping of type of node to a list of same type node.
        qchannels (list[QuantumChannel]): list of quantum channel objects in network.
        cchannels (list[ClassicalChannel]): list of classical channel objects in network.
        tl (Timeline): the timeline used for simulation
    """

    _deprecated_attrs = {
        "ALL_C_CONNECT": ALL_C_CONNECT,
        "ALL_C_CHANNEL": ALL_C_CHANNEL,
        "ALL_NODE": ALL_NODE,
        "ALL_Q_CONNECT": ALL_Q_CONNECT,
        "ALL_Q_CHANNEL": ALL_Q_CHANNEL,
        "ATTENUATION": ATTENUATION,
        "CONNECT_NODE_1": CONNECT_NODE_1,
        "CONNECT_NODE_2": CONNECT_NODE_2,
        "DELAY": DELAY,
        "DISTANCE": DISTANCE,
        "DST": DST,
        "NAME": NAME,
        "SEED": SEED,
        "SRC": SRC,
        "STOP_TIME": STOP_TIME,
        "TRUNC": TRUNC,
        "TYPE": TYPE,
        "ALL_TEMPLATES": ALL_TEMPLATES,
        "TEMPLATE": TEMPLATE,
        "GATE_FIDELITY": GATE_FIDELITY,
        "MEASUREMENT_FIDELITY": MEASUREMENT_FIDELITY,
        "FORMALISM": FORMALISM,
    }

    # Concrete subclasses declare which node type strings map to which node classes.
    # Used by _add_nodes to dispatch node creation to the impl.
    NODE_TYPES: dict = {}

    def __init__(self, conf_file_name: str, networkimpl: NetworkImpl):
        """Build a network topology from a config file (.json or .yaml).

        Args:
            conf_file_name (str): path to a .json or .yaml/.yml config file
            networkimpl (NetworkImpl): composed implementor for this topology family
        """
        if not conf_file_name.endswith(('.json', '.yaml', '.yml')):
            raise ValueError(
                f"Unsupported config file format: {conf_file_name}. "
                "Use .json or .yaml/.yml"
            )
        with open(conf_file_name) as fh:
            if conf_file_name.endswith(('.yaml', '.yml')):
                import yaml
                config = yaml.safe_load(fh)
            else:
                config = json.load(fh)

        self._setup(networkimpl)
        self._raw_cfg = config
        self._run_pipeline(config)

    def _setup(self, networkimpl: NetworkImpl) -> None:
        """Initialise all topology state. Called before _run_pipeline."""
        self.bsm_to_router_map = {}
        self.nodes: dict[str, list[Node]] = defaultdict(list)
        self.qchannels: list[QuantumChannel] = []
        self.cchannels: list[ClassicalChannel] = []
        self.templates: dict[str, dict] = {}
        self.tl: Timeline | None = None
        self._impl = networkimpl

    def _run_pipeline(self, config: dict) -> None:
        """Execute the full build pipeline on a config dict.

        Separated from __init__ so CreateTopo can supply a programmatically
        built config dict instead of a file.
        """
        self._get_templates(config)
        self._add_parameters(config)
        self._add_qconnections(config)
        self._add_timeline(config)
        self._impl._map_bsm_routers(config, self.bsm_to_router_map)
        self._add_nodes(config)
        self._impl._add_bsm_node_to_router(self.bsm_to_router_map, self.tl)
        self._add_qchannels(config)
        self._add_cchannels(config)
        self._add_cconnections(config)
        self._impl._generate_forwarding_table(config, self.nodes, self.qchannels)
        self._add_protocols()

    def _add_nodes(self, config: dict):
        ordered_configs = self._impl._ordered_node_dicts(config[ALL_NODE])
        for node_config in ordered_configs:
            node_type = node_config[TYPE]
            template  = self.templates.get(node_config.get(TEMPLATE), {})
            self._impl._create_node(node_config, node_type, template,
                                    self.tl, self.nodes, self.bsm_to_router_map,
                                    self.NODE_TYPES)

    def _add_parameters(self, config: dict):
        """Read topology-level parameters from config.

        Detects QLAN topologies by node types present and handles both
        legacy flat format and new template format automatically.
        Then delegates to impl for any impl-internal state initialization.
        """
        node_types_present = {n[TYPE] for n in config.get(ALL_NODE, [])}
        if ORCHESTRATOR in node_types_present or CLIENT in node_types_present:
            self._add_qlan_parameters(config)
        self._impl._add_parameters(config, self)

    def _add_qlan_parameters(self, config: dict) -> None:
        """Read QLAN structural and hardware params. Handles both config formats.

        Flat (legacy): top-level keys like memo_fidelity_orch, measurement_bases.
        Template (new): per-node MemoryArray entries in the templates section.
        """
        self.n_local_memories = config.get(LOCAL_MEMORIES, 1)
        self.n_clients        = config.get(CLIENT_NUMBER, 1)
        self.meas_bases       = config.get(MEASUREMENT_BASES, 'z')

        if MEM_FIDELITY_ORCH in config:
            self.memo_fidelity_orch     = config.get(MEM_FIDELITY_ORCH,     0.9)
            self.memo_freq_orch         = config.get(MEM_FREQUENCY_ORCH,    2000)
            self.memo_efficiency_orch   = config.get(MEM_EFFICIENCY_ORCH,   1)
            self.memo_coherence_orch    = config.get(MEM_COHERENCE_ORCH,    -1)
            self.memo_wavelength_orch   = config.get(MEM_WAVELENGTH_ORCH,   500)
            self.memo_fidelity_client   = config.get(MEM_FIDELITY_CLIENT,   0.9)
            self.memo_freq_client       = config.get(MEM_FREQUENCY_CLIENT,  2000)
            self.memo_efficiency_client = config.get(MEM_EFFICIENCY_CLIENT, 1)
            self.memo_coherence_client  = config.get(MEM_COHERENCE_CLIENT,  -1)
            self.memo_wavelength_client = config.get(MEM_WAVELENGTH_CLIENT, 500)
        else:
            orch_mem   = self._qlan_memarray(config, ORCHESTRATOR)
            client_mem = self._qlan_memarray(config, CLIENT)
            self.memo_fidelity_orch     = orch_mem.get("fidelity",       0.9)
            self.memo_freq_orch         = orch_mem.get("frequency",      2000)
            self.memo_efficiency_orch   = orch_mem.get("efficiency",     1)
            self.memo_coherence_orch    = orch_mem.get("coherence_time", -1)
            self.memo_wavelength_orch   = orch_mem.get("wavelength",     500)
            self.memo_fidelity_client   = client_mem.get("fidelity",       0.9)
            self.memo_freq_client       = client_mem.get("frequency",      2000)
            self.memo_efficiency_client = client_mem.get("efficiency",     1)
            self.memo_coherence_client  = client_mem.get("coherence_time", -1)
            self.memo_wavelength_client = client_mem.get("wavelength",     500)

    def _qlan_memarray(self, config: dict, node_type: str) -> dict:
        """Return the MemoryArray template dict for the first node of node_type."""
        for node in config.get(ALL_NODE, []):
            if node[TYPE] == node_type:
                tmpl_name = node.get(TEMPLATE)
                if tmpl_name and tmpl_name in self.templates:
                    return self.templates[tmpl_name].get("MemoryArray", {})
        return {}

    def _add_protocols(self):
        pass

    def _get_templates(self, config: dict) -> None:
        self.templates = config.get(ALL_TEMPLATES, {})

    def _add_timeline(self, config: dict):
        stop_time = config.get(STOP_TIME, float('inf'))
        formalism = config.get(FORMALISM, KET_STATE_FORMALISM)
        truncation = config.get(TRUNC, 1)
        QuantumManager.set_global_manager_formalism(formalism)
        self.tl = Timeline(stop_time=stop_time, truncation=truncation)

    def _add_qconnections(self, config: dict) -> None:
        """Compute cc_delay (common across all topologies) then delegate to impl."""
        for q_connect in config.get(ALL_Q_CONNECT, []):
            node1     = q_connect[CONNECT_NODE_1]
            node2     = q_connect[CONNECT_NODE_2]
            endpoints = frozenset({node1, node2})
            cc_delay  = []

            for section, src_key, dst_key in (
                (ALL_C_CHANNEL, SRC, DST),
                (ALL_C_CONNECT, CONNECT_NODE_1, CONNECT_NODE_2),
            ):
                for cc in config.get(section, []):
                    if frozenset({cc[src_key], cc[dst_key]}) == endpoints:
                        cc_delay.append(cc.get(DELAY, cc.get(DISTANCE, 1000) / SPEED_OF_LIGHT))

            if len(cc_delay) == 0:
                assert 0, q_connect
            cc_delay = int(np.mean(cc_delay) // 2)

            self._impl._handle_qconnection(q_connect, cc_delay, config)

    def _add_qchannels(self, config: dict) -> None:
        for qc in config.get(ALL_Q_CHANNEL, []):
            src_str, dst_str = qc[SRC], qc[DST]
            src_node = self.tl.get_entity_by_name(src_str)
            if src_node is not None:
                name = qc.get(NAME, f"qc-{src_str}-{dst_str}")
                qc_obj = QuantumChannel(name, self.tl, qc[ATTENUATION], qc[DISTANCE])
                qc_obj.set_ends(src_node, dst_str)
                self.qchannels.append(qc_obj)

    def _add_cchannels(self, config: dict) -> None:
        for cc in config.get(ALL_C_CHANNEL, []):
            self._make_classical_channel(
                cc[SRC], cc[DST],
                cc.get(DISTANCE, -1), cc.get(DELAY, -1),
                name=cc.get(NAME),
            )

    def _add_cconnections(self, config: dict) -> None:
        for c in config.get(ALL_C_CONNECT, []):
            distance = c.get(DISTANCE, -1)
            delay    = c.get(DELAY, -1)
            for src_str, dst_str in zip(
                [c[CONNECT_NODE_1], c[CONNECT_NODE_2]],
                [c[CONNECT_NODE_2], c[CONNECT_NODE_1]],
            ):
                self._make_classical_channel(src_str, dst_str, distance, delay)

    def _make_classical_channel(self, src_str: str, dst_str: str,
                                 distance: float, delay: float,
                                 name: str = None) -> None:
        src_obj = self.tl.get_entity_by_name(src_str)
        if src_obj is not None:
            cc_obj = ClassicalChannel(
                name or f"cc-{src_str}-{dst_str}",
                self.tl, distance, delay,
            )
            cc_obj.set_ends(src_obj, dst_str)
            self.cchannels.append(cc_obj)

    def get_timeline(self) -> "Timeline":
        if self.tl is None:
            raise RuntimeError("Timeline is not set — topology may not be fully initialised.")
        return self.tl

    def get_nodes_by_type(self, type: str) -> list[Node]:
        return self.nodes[type]

    def get_qchannels(self) -> list["QuantumChannel"]:
        return self.qchannels

    def get_cchannels(self) -> list["ClassicalChannel"]:
        return self.cchannels

    def get_nodes(self) -> dict[str, list["Node"]]:
        return self.nodes
