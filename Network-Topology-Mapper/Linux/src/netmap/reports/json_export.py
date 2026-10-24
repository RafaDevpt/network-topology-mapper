#!/usr/bin/env python3
"""
PT-PT: Exportação do mapa em JSON.

       O Excel é para pessoas; este ficheiro é para outros programas — em
       particular o Network Twin 3D, que desenha a rede em 3D e cruza o que foi
       descoberto com o que foi desenhado no Network Config Builder.

       Duas decisões que importam:

       1. Vai a tabela de portas de cada equipamento (estado, VLAN, PoE). É o
          que permite a outro programa verificar, porta a porta, se a realidade
          bate certo com o desenho.
       2. Cada ligação diz **quem a anunciou**. O mapa deduplica os cabos (A→B
          e B→A são o mesmo cabo), e com isso perdia-se uma informação valiosa:
          um cabo visto só de um lado é um cabo suspeito — LLDP desligado numa
          ponta, ou um equipamento que não se conseguiu alcançar.

       Não vai: tabelas MAC e ARP em bruto (os pontos finais já são o resultado
       cruzado delas) nem, evidentemente, credenciais — essas nunca chegam ao
       `Topology`.

EN-UK: Map export as JSON.

       Excel is for people; this file is for other programs — in particular
       Network Twin 3D, which draws the network in 3D and cross-checks what was
       discovered against what was designed in Network Config Builder.

       Two decisions that matter:

       1. Every device's port table goes in (state, VLAN, PoE). It is what lets
          another program check, port by port, whether reality matches design.
       2. Every link states **who announced it**. The map deduplicates cables
          (A→B and B→A are the same cable), and with that a valuable fact was
          lost: a cable seen from one side only is a suspect cable — LLDP off
          at one end, or a device that could not be reached.

       Left out: raw MAC and ARP tables (endpoints are already their
       cross-referenced result) and, obviously, credentials — those never reach
       the `Topology`.

Created by Redfox using Claude
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Link, NetworkDevice, Topology

# PT-PT: Identificação do formato. Quem lê confirma o tipo e a versão antes de
#        confiar no conteúdo; uma mudança incompatível sobe a versão.
# EN-UK: Format identification. Readers check type and version before trusting
#        the content; an incompatible change bumps the version.
FORMAT_TYPE = "netmap-topology"
FORMAT_VERSION = 1


def write(topology: Topology, path: Path, started: datetime | None = None) -> Path:
    """
    PT-PT: Escreve o mapa em JSON legível (indentado, UTF-8).
    EN-UK: Writes the map as readable JSON (indented, UTF-8).

    :param topology:
        PT-PT: O mapa completo. / EN-UK: The complete map.
    :param path:
        PT-PT: Onde escrever. / EN-UK: Where to write.
    :param started:
        PT-PT: Quando o mapeamento começou. / EN-UK: When the mapping started.
    :return:
        PT-PT: O caminho escrito. / EN-UK: The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_dict(topology, started), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def to_dict(topology: Topology, started: datetime | None = None) -> dict[str, Any]:
    """
    PT-PT: O mapa como dicionário serializável. Separado de `write` para os
           testes não precisarem de disco.
    EN-UK: The map as a serialisable dict. Split from `write` so tests need no
           disk.
    """
    announcers = _announcers(topology)
    return {
        "formato": FORMAT_VERSION,
        "tipo": FORMAT_TYPE,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "iniciado_em": started.isoformat(timespec="seconds") if started else None,
        "devices": [_device(d) for d in topology.devices.values()],
        "links": [
            {
                "a_device": link.a_device,
                "a_port": link.a_port,
                "b_device": link.b_device,
                "b_port": link.b_port,
                "source": link.source.value,
                "announced_by": sorted(announcers.get(link, set())),
            }
            for link in topology.links
        ],
        "endpoints": [
            {
                **asdict(ponto),
                "role": ponto.role.value,
                "confidence": ponto.confidence.value,
                "located": ponto.located,
            }
            for ponto in topology.endpoints
        ],
        "issues": [
            {"severity": p.severity, "subject": p.subject, "message": p.message}
            for p in topology.issues
        ],
    }


def _device(device: NetworkDevice) -> dict[str, Any]:
    """PT-PT: Um equipamento, sem as tabelas em bruto. / EN-UK: One device, minus raw tables."""
    facts = device.facts
    return {
        "label": device.label,
        "host": device.host,
        "name": device.name,
        "platform": device.platform.value,
        "model": device.model or facts.model,
        "version": facts.version,
        "source": device.source.value,
        "reached": device.reached,
        "error": device.error,
        "depth": device.depth,
        "ports": [asdict(porta) for porta in facts.ports],
        "neighbours": [
            {
                "local_port": v.local_port,
                "remote_name": v.remote_name,
                "remote_port": v.remote_port,
                "remote_chassis": v.remote_chassis,
                "management_ip": v.management_ip,
                # PT-PT: Conjunto → lista ordenada, para o JSON ser estável
                #        entre execuções e um `git diff` fazer sentido.
                # EN-UK: Set → sorted list, so the JSON is stable across runs
                #        and a `git diff` makes sense.
                "capabilities": sorted(v.capabilities),
                "source": v.source.value,
            }
            for v in facts.neighbours
        ],
    }


def _announcers(topology: Topology) -> dict[Link, set[str]]:
    """
    PT-PT: Para cada ligação do mapa, que equipamentos a anunciaram.

           Reconstrói-se a partir dos vizinhos: `Link.between` ordena as pontas
           e ignora a origem na igualdade, por isso o mesmo cabo anunciado de
           cada lado (ou por LLDP e CDP) cai na mesma chave.

    EN-UK: For every link on the map, which devices announced it.

           Rebuilt from the neighbours: `Link.between` orders the ends and
           ignores the source in equality, so the same cable announced from
           each side (or over LLDP and CDP) lands on the same key.
    """
    conhecidas = set(topology.links)
    resultado: dict[Link, set[str]] = {}
    for dispositivo in topology.reached:
        for vizinho in dispositivo.facts.neighbours:
            outro = vizinho.remote_name or vizinho.remote_chassis
            if not outro:
                continue
            chave = Link.between(dispositivo.label, vizinho.local_port, outro, vizinho.remote_port)
            if chave in conhecidas:
                resultado.setdefault(chave, set()).add(dispositivo.label)
    return resultado
