"""What DIGSI writes into an SCL file beside the standard.

An SCD from the Siemens IEC 61850 System Configurator is ordinary SCL with a
second layer folded into it, under two namespaces of Siemens' own and a long
list of ``<Private type="Siemens-*">`` elements. The reference station -- 14
IEDs -- carries **2,473** of those privates. None of them is visible to a
vendor-neutral reader, and they hold the things a commissioning engineer
actually asks about a SIPROTEC: which device it is, which application template
it was built from, what DIGSI calls it, and when it last changed.

Two structures are read here.

**The IEDs.** Each carries its SIPROTEC 5 product code
(``7SJ85-JAAA-AA0-...``), the application template it came from
(``7SJ85_Non_Directional_OC``), DIGSI's own name for it (the ``s7ManagerName``,
which is NOT the SCL IED name), its folder in the DIGSI project tree, and a
modification counter and date. An IED with no Siemens private is skipped: a
station is not one vendor, and the reference file has SEL relays sitting
beside the SIPROTECs.

**The GOOSE applications.** DIGSI groups datasets into named applications --
"138 kV", "34,5 kV" -- each with an APPID, a VLAN, a priority profile and
transmission times. The grouping is by GUID, and resolving it is the reason
this module earns its place::

    <siedig:GooseApplication name="138 kV">
        <siedig:DataSet guidRef="1f741f02..." />      <-- an opaque hex string

    <IED name="QPC1_TR1_UPC1"> ... <LN0> <DataSet>
        <Private type="Siemens-GUID">1f741f02...</Private>   <-- lives here

Without walking that link an application is a list of hex strings; with it,
an application names the IEDs that publish in it. A GUID an application
references but no dataset in the file carries is reported as unresolved
rather than dropped -- a station that points at something missing is exactly
what a reader wants to be shown.

Nothing here parses the standard half. That is `sellib.scl`'s, for any vendor.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

#: DIGSI's own namespace, on the GOOSE application storage.
NS_SIEDIG = "http://www.siemens.com/energy/2011/11/Siedig"
#: The SIPROTEC 5 base namespace. Declared by these files; nothing is read
#: from it yet, and it is named here so the next reader knows where to look.
NS_SIEBASE = "http://www.siemens.com/energy/2009/09/siprotec5/SieBase"

#: Every `Private` this module reads. The prefix is what marks a private as
#: Siemens' rather than another tool's -- `IsNodeProcessed`, for one, is in
#: the same files and is not.
PRIVATE_PREFIX = "Siemens-"

_P_IED_ID = "Siemens-IED-Id"
_P_PRODUCT_CODE = "Siemens-Siprotec5-Product-Code"
_P_TEMPLATE = "Siemens-Siprotec5-Application-Template"
_P_DIGSI_NAME = "Siemens-s7ManagerName"
_P_FOLDER = "Siemens-FolderPath"
_P_MOD_COUNT = "Siemens-ModificationCounter"
_P_MOD_DATE = "Siemens-ModifiedDate"
_P_GUID = "Siemens-GUID"


@dataclass(frozen=True)
class SiprotecIed:
    """One IED, as DIGSI describes it. Fields are "" when DIGSI wrote none.

    Empty rather than absent because DIGSI does not write every private for
    every device, and a station that half-answers is still worth reading.
    `modification_counter` is None for the same reason -- 0 is a real count.
    """

    name: str                       # the SCL IED name
    digsi_name: str = ""            # what the DIGSI project calls it
    product_code: str = ""          # 7SJ85-JAAA-AA0-...
    application_template: str = ""  # 7SJ85_Non_Directional_OC
    ied_id: str = ""
    folder_path: str = ""           # the DIGSI project tree
    modification_counter: int | None = None
    modified: str = ""              # DIGSI's own format, kept as written

    @property
    def device(self) -> str:
        """The SIPROTEC model: the product code up to its first dash.

        ``7SJ85-JAAA-AA0-...`` is a 7SJ85. What follows describes the cards
        fitted, which is a different question from what the relay is.
        """
        return self.product_code.split("-", 1)[0]


@dataclass(frozen=True)
class GooseApplication:
    """A DIGSI GOOSE application: a named group of datasets and its network."""

    name: str
    desc: str = ""
    profile: str = ""               # e.g. "PriorityLow"
    app_id: str = ""
    min_time_ms: int | None = None
    max_time_ms: int | None = None
    vlan_id: str = ""
    vlan_priority: int | None = None
    dataset_guids: list[str] = field(default_factory=list)
    #: The IEDs owning those datasets, in the order the guids appear, each
    #: named once.
    ied_names: list[str] = field(default_factory=list)
    #: Referenced guids no dataset in this file carries.
    unresolved_guids: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _root(path: Path | str) -> ET.Element:
    return ET.parse(str(path)).getroot()


def _privates(node: ET.Element) -> dict[str, str]:
    """The `Siemens-*` privates that are this node's OWN.

    Direct children only. An `IED` contains its access points and their whole
    data model, and those carry privates of their own -- a descendant search
    would hand an IED the GUID of one of its datasets.
    """
    out: dict[str, str] = {}
    for child in node:
        if _local(child.tag) != "Private":
            continue
        kind = child.get("type", "")
        if kind.startswith(PRIVATE_PREFIX):
            out[kind] = (child.text or "").strip()
    return out


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def is_digsi(path: Path | str) -> bool:
    """Does this SCL carry anything of Siemens' at all?

    Answered from the content -- a `Siemens-*` private or the DIGSI namespace
    -- and never from a filename or a `manufacturer` attribute. A station is
    not one vendor: the reference SCD has SEL relays in it too.
    """
    root = _root(path)
    if any(NS_SIEDIG in t for t in (root.tag, *(k for k in root.keys()))):
        return True
    for node in root.iter():
        if NS_SIEDIG in node.tag:
            return True
        if (_local(node.tag) == "Private"
                and node.get("type", "").startswith(PRIVATE_PREFIX)):
            return True
    return False


def read_ieds(path: Path | str) -> list[SiprotecIed]:
    """Every IED DIGSI describes, in document order.

    An IED with no `Siemens-*` private of its own is not returned. It is not
    an error and not a gap: it is another vendor's relay in the same station,
    and describing it is not this library's job.
    """
    out: list[SiprotecIed] = []
    for ied in _root(path).iter():
        if _local(ied.tag) != "IED":
            continue
        p = _privates(ied)
        if not p:
            continue
        out.append(SiprotecIed(
            name=ied.get("name", ""),
            digsi_name=p.get(_P_DIGSI_NAME, ""),
            product_code=p.get(_P_PRODUCT_CODE, ""),
            application_template=p.get(_P_TEMPLATE, ""),
            ied_id=p.get(_P_IED_ID, ""),
            folder_path=p.get(_P_FOLDER, ""),
            modification_counter=_int_or_none(p.get(_P_MOD_COUNT, "")),
            modified=p.get(_P_MOD_DATE, ""),
        ))
    return out


def _dataset_owners(root: ET.Element) -> dict[str, str]:
    """`Siemens-GUID` of a DataSet -> the name of the IED that holds it."""
    owners: dict[str, str] = {}
    for ied in root.iter():
        if _local(ied.tag) != "IED":
            continue
        ied_name = ied.get("name", "")
        for node in ied.iter():
            if _local(node.tag) != "DataSet":
                continue
            guid = _privates(node).get(_P_GUID, "")
            if guid:
                owners[guid] = ied_name
    return owners


def _text(node: ET.Element, local: str) -> str:
    for child in node:
        if _local(child.tag) == local:
            return (child.text or "").strip()
    return ""


def read_goose_applications(path: Path | str) -> list[GooseApplication]:
    """The GOOSE applications, with their datasets resolved to IEDs.

    Empty when the file has no `GooseApplicationStorage` -- an SCL from
    another tool simply has none, which is not an error.
    """
    root = _root(path)
    owners = _dataset_owners(root)
    out: list[GooseApplication] = []

    for node in root.iter():
        if _local(node.tag) != "GooseApplication":
            continue
        guids = [ds.get("guidRef", "") for ds in node
                 if _local(ds.tag) == "DataSet" and ds.get("guidRef")]
        ieds: list[str] = []
        unresolved: list[str] = []
        for guid in guids:
            owner = owners.get(guid)
            if owner is None:
                unresolved.append(guid)
            elif owner not in ieds:
                ieds.append(owner)
        out.append(GooseApplication(
            name=node.get("name", ""),
            desc=node.get("desc", ""),
            profile=node.get("profileName", ""),
            app_id=_text(node, "AppId"),
            min_time_ms=_int_or_none(_text(node, "MinTime")),
            max_time_ms=_int_or_none(_text(node, "MaxTime")),
            vlan_id=_text(node, "VLanId"),
            vlan_priority=_int_or_none(_text(node, "VLanPriority")),
            dataset_guids=guids,
            ied_names=ieds,
            unresolved_guids=unresolved,
        ))
    return out
