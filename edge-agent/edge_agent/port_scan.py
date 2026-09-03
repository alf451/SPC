"""Elenco delle porte seriali disponibili sulla macchina dove gira l'agent.

Serve a riportare al backend cosa e' fisicamente collegato a questa stazione
(vedi ws_client.py::_send_hello), cosi' chi configura una sorgente DAQ dal
pannello admin/frontend vede un elenco reale invece di dover controllare
Gestione dispositivi via RDP su ogni singola postazione.
"""
from __future__ import annotations

try:
    from serial.tools import list_ports
except ImportError:  # pyserial non installato (es. ambiente di solo test)
    list_ports = None  # type: ignore[assignment]


def list_available_ports() -> list[dict]:
    """Ritorna [{device, description, hwid}, ...] - lista vuota se pyserial
    non e' disponibile o non ci sono porte seriali sul sistema (non e' un
    errore, e' un dato legittimo: nessuna porta collegata in questo momento)."""
    if list_ports is None:
        return []
    return [
        {
            "device": p.device,
            "description": p.description or "",
            "hwid": p.hwid or "",
        }
        for p in list_ports.comports()
    ]
