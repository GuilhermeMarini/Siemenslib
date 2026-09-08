"""The file formats a Siemens protective relay project is made of.

Everything here reads what DIGSI writes. Nothing here talks to a relay, opens
a socket, or knows what a web request is.

    from py61850.scl import SclDocument    # pip install siemenslib
    from siemenslib import digsi

    doc = SclDocument.parse("station.scd")
    for ied in digsi.read_ieds(doc):
        print(ied.name, ied.device, ied.application_template)

Every reader also takes a plain path and parses one document for itself; pass
one ``SclDocument`` when asking more than one question about the same file.

What is inside:

``siemenslib.digsi``
    The Siemens-private half of an SCL file: the SIPROTEC product code and
    application template of each IED, the DIGSI names and revision counters,
    and the GOOSE applications DIGSI groups datasets into.

What is deliberately NOT inside: the standard half of IEC 61850. An SCD's
IEDs, GOOSE control blocks, addressing and data model are ordinary SCL, and
``py61850.scl`` reads them for any vendor. A second reader for one standard
format would be two things to keep right instead of one. This library is for
what is Siemens' *own*, and what no vendor-neutral reader looks at.

**Nothing here parses XML.** Every answer is read off the model nodes
``py61850`` builds -- ``Private`` elements, which is SCL's own vendor seam,
keyed by ``type`` on every node. The sibling library ``sellib`` reads SEL's
half off the same nodes, sharing no code with this one and never opening the
file a second time.
"""

from __future__ import annotations

__version__ = "0.2.1"

__all__ = ["digsi"]

from siemenslib import digsi  # noqa: E402,F401  (re-export, after the docstring)
