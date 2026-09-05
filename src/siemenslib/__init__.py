"""The file formats a Siemens protective relay project is made of.

Everything here reads what DIGSI writes. Nothing here talks to a relay, opens
a socket, or knows what a web request is.

    from siemenslib import digsi          # pip install siemenslib

    for ied in digsi.read_ieds(Path("station.scd")):
        print(ied.name, ied.device, ied.application_template)

What is inside:

``siemenslib.digsi``
    The Siemens-private half of an SCL file: the SIPROTEC product code and
    application template of each IED, the DIGSI names and revision counters,
    and the GOOSE applications DIGSI groups datasets into.

What is deliberately NOT inside: the standard half of IEC 61850. An SCD's
IEDs, GOOSE control blocks, addressing and data model are ordinary SCL, and
``sellib.scl`` reads them for any vendor -- the reference station here parses
with it unchanged. A second reader for one standard format would be two
things to keep right instead of one. This library is for what is Siemens'
*own*, and what no vendor-neutral reader looks at.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["digsi"]

from siemenslib import digsi  # noqa: E402,F401  (re-export, after the docstring)
