#!/usr/bin/env python3
"""
PT-PT: Testes da exportação em JSON.

       O que se protege aqui é o contrato com o Network Twin 3D: as chaves que
       ele lê, e sobretudo o campo `announced_by`, que é a única forma de saber
       se um cabo foi visto dos dois lados depois de o mapa o deduplicar.

EN-UK: JSON export tests.

       What is protected here is the contract with Network Twin 3D: the keys it
       reads, and above all `announced_by`, the only way to know whether a cable
       was seen from both sides once the map has deduplicated it.

Created by Redfox using Claude
"""

from __future__ import annotations

import json
from pathlib import Path

from netmap import reports
from netmap.models import (
    DeviceFacts,
    Endpoint,
    Issue,
    Link,
    LldpNeighbour,
    NetworkDevice,
    Platform,
    PortStatus,
    Role,
    Topology,
)
from netmap.reports import json_export


def _mapa() -> Topology:
    """
    PT-PT: Núcleo ligado a dois acessos. O acesso 1 anuncia o cabo de volta;
           o acesso 2 não foi alcançado, por isso o seu cabo só tem um lado.
    EN-UK: A core linked to two access switches. Access 1 announces the cable
           back; access 2 was not reached, so its cable has one side only.
    """
    core = NetworkDevice(
        host="10.0.0.1",
        name="SW-CORE",
        platform=Platform.CISCO_IOS,
        reached=True,
        facts=DeviceFacts(
            hostname="SW-CORE",
            model="C9300-48P",
            neighbours=[
                LldpNeighbour("Gi1/0/47", "SW-ACC1", "Gi1/0/48", capabilities={"bridge"}),
                LldpNeighbour("Gi1/0/48", "SW-ACC2", "Gi1/0/48", capabilities={"bridge"}),
            ],
            ports=[PortStatus("Gi1/0/1", "PC Rececao", True, 20, "1000", 0.0, True)],
        ),
    )
    acc1 = NetworkDevice(
        host="10.0.0.2",
        name="SW-ACC1",
        platform=Platform.CISCO_IOS,
        reached=True,
        depth=1,
        facts=DeviceFacts(
            neighbours=[LldpNeighbour("Gi1/0/48", "SW-CORE", "Gi1/0/47", capabilities={"bridge"})]
        ),
    )
    acc2 = NetworkDevice(host="10.0.0.3", name="SW-ACC2", reached=False, error="Timeout", depth=1)

    return Topology(
        devices={d.label: d for d in (core, acc1, acc2)},
        links=[
            Link.between("SW-CORE", "Gi1/0/47", "SW-ACC1", "Gi1/0/48"),
            Link.between("SW-CORE", "Gi1/0/48", "SW-ACC2", "Gi1/0/48"),
        ],
        endpoints=[
            Endpoint(mac="02:00:00:00:00:01", ip="10.0.20.10", role=Role.PC, switch="SW-CORE", port="Gi1/0/1", vlan=20)
        ],
        issues=[Issue("AVISO", "SW-ACC2", "Timeout")],
    )


def test_envelope_identifica_formato() -> None:
    dados = json_export.to_dict(_mapa())
    assert dados["tipo"] == "netmap-topology"
    assert dados["formato"] == 1
    assert {"devices", "links", "endpoints", "issues"} <= dados.keys()


def test_announced_by_distingue_um_e_dois_lados() -> None:
    ligacoes = {
        (lig["a_device"], lig["b_device"]): lig["announced_by"]
        for lig in json_export.to_dict(_mapa())["links"]
    }
    assert ligacoes[("SW-ACC1", "SW-CORE")] == ["SW-ACC1", "SW-CORE"]
    assert ligacoes[("SW-ACC2", "SW-CORE")] == ["SW-CORE"]


def test_portas_e_pontos_finais_seguem_serializaveis() -> None:
    dados = json_export.to_dict(_mapa())
    core = next(d for d in dados["devices"] if d["label"] == "SW-CORE")
    assert core["ports"][0]["vlan"] == 20
    assert core["neighbours"][0]["capabilities"] == ["bridge"]
    assert dados["endpoints"][0]["role"] == "Posto de trabalho"
    assert dados["endpoints"][0]["located"] is True
    # PT-PT: Tem de passar pelo json sem conversores especiais.
    # EN-UK: Must go through json with no special converters.
    json.dumps(dados)


def test_write_json_escreve_ficheiro(tmp_path: Path) -> None:
    caminho = reports.write_json(_mapa(), tmp_path / "sub" / "mapa.json")
    lido = json.loads(caminho.read_text(encoding="utf-8"))
    assert len(lido["links"]) == 2
