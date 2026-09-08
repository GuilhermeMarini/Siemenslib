"""What DIGSI writes into an SCL file beside the standard.

An SCD from the Siemens IEC 61850 System Configurator is ordinary SCL with a
second layer folded into it, under two namespaces of Siemens' own and a long
list of ``<Private type="Siemens-*">`` elements. The reference station -- 14
IEDs -- carries **2,473** of those privates, and a larger mixed-vendor one
5,886. None of them is visible to a vendor-neutral reader, and they hold the
things a commissioning engineer actually asks about a SIPROTEC: which device
it is, which application template it was built from, what DIGSI calls it, and
when it last changed.

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

    <Private type="Siemens_SiedigGooseApplicationStorage">   <-- on <SCL>
      <siedig:GooseApplication name="138 kV">
        <siedig:DataSet guidRef="1f741f02..." />      <-- an opaque hex string

    <IED name="QPC1_TR1_UPC1"> ... <LN0> <DataSet>
        <Private type="Siemens-GUID">1f741f02...</Private>   <-- lives here

Without walking that link an application is a list of hex strings; with it,
an application names the IEDs that publish in it. A GUID an application
references but no dataset in the file carries is reported as unresolved
rather than dropped -- a station that points at something missing is exactly
what a reader wants to be shown.

**Nothing here parses XML.** The standard half of an SCL file -- the document,
the IEDs, the logical nodes, the datasets -- is read by ``py61850.scl``, for
any vendor, and everything below is read off the model nodes it builds::

    from py61850.scl import SclDocument
    from siemenslib import digsi

    doc = SclDocument.parse("station.scd")
    ieds = digsi.read_ieds(doc)
    apps = digsi.read_goose_applications(doc)

Every function also takes a plain path and parses one document for itself.
That is the convenience form, not the cheap one: on the 13.5 MB reference
station the parse is 257 ms against 167 ms of walking, so a caller asking
this module more than one question should pass one ``SclDocument``.

The seam this rests on is standard SCL, not an arrangement made for Siemens.
``Private`` elements hang off every model node, keyed by ``type``, and a
vendor library reads its own. `sellib` reads SEL's off the same nodes. That
two unrelated vendors extend one file by the same mechanism, and are read by
two libraries that share no code and never parse the file twice, is the whole
argument for the split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from py61850.scl import (
    DtdNotAllowed,  # noqa: F401  (re-exported: see `_document`)
    SclDocument,
    children_local,
    iter_local,
)

#: DIGSI's own namespace, on the GOOSE application storage.
NS_SIEDIG = "http://www.siemens.com/energy/2011/11/Siedig"
#: The SIPROTEC 5 base namespace. Declared by these files; nothing is read
#: from it yet, and it is named here so the next reader knows where to look.
NS_SIEBASE = "http://www.siemens.com/energy/2009/09/siprotec5/SieBase"

#: What marks a `Private` as Siemens' rather than another tool's --
#: `IsNodeProcessed` is in the same files and is not, and neither is any
#: `SEL_*`. BOTH separators, because DIGSI uses both and it is not a typo to
#: paper over: every private carrying DATA spells it `Siemens-`, while the two
#: that carry a whole nested STRUCTURE spell it `Siemens_`
#: (`Siemens_SiedigGooseApplicationStorage`, `Siemens_SiedigFolderDetails`).
#: A prefix test that knew only the dash answered "not Siemens'" for the very
#: element this module exists to read.
PRIVATE_PREFIXES = ("Siemens-", "Siemens_")

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


def _document(source: SclDocument | Path | str) -> SclDocument:
    """An `SclDocument` from a path, or straight through from one.

    `parse` and not `load`: these three functions have always raised on a file
    that will not read, and turning a broken file into "not a DIGSI file"
    would be the worst possible answer to `is_digsi`. The exceptions are
    `OSError`, `ET.ParseError` and `DtdNotAllowed` -- the last re-exported
    from this module, so a caller can catch it without reaching into
    `py61850.scl` for the name.

    The DTD refusal itself is py61850's, and used to be a copy of forty lines
    kept here. Two copies of a security check are two things to get right, and
    they had already drifted: this one raised `"formato nao usa"` where
    sellib's raised `"formato não usa"`.
    """
    if isinstance(source, SclDocument):
        return source
    return SclDocument.parse(Path(source))


def _is_siemens(private_type: str) -> bool:
    return private_type.startswith(PRIVATE_PREFIXES)


def _texts(privates: dict) -> dict[str, str]:
    """`{type: [Private element, ...]}` -> `{type: text}`, Siemens' only.

    py61850 hands over a LIST per type, because SCL permits several `Private`
    elements of one type on one node. DIGSI writes at most one of each -- 2,473
    privates across the reference station and not a single repeated type on a
    node -- so the first is taken and the shape is flattened here rather than
    inflicted on every caller.
    """
    out: dict[str, str] = {}
    for kind, elements in privates.items():
        if _is_siemens(kind) and elements:
            out[kind] = (elements[0].text or "").strip()
    return out


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def is_digsi(source: SclDocument | Path | str) -> bool:
    """Does this SCL carry anything of Siemens' at all?

    Answered from the content -- the DIGSI namespace, or a `Siemens-*` private
    on the document or on an IED -- and never from a filename or a
    `manufacturer` attribute. A station is not one vendor: the reference SCD
    has SEL relays in it too, and the mixed-vendor one is a DIGSI export
    containing SEL RTACs.

    Cheap on purpose: it reads the declared namespaces and two levels of
    privates, not the whole tree. Measured over the corpus, that is not a
    narrowing anyone can reach -- all three Siemens-touched files declare the
    DIGSI namespace on the root element and carry document-level privates, and
    a file whose ONLY Siemens content were a `Siemens-MasterId` buried on a
    logical node, with no namespace declared and no IED private, is not a
    DIGSI export.
    """
    doc = _document(source)
    if NS_SIEDIG in doc.namespaces:
        return True
    if any(_is_siemens(kind) for kind in doc.privates):
        return True
    return any(_is_siemens(kind)
               for header in doc.ied_headers.values()
               for kind in header.privates)


def read_ieds(source: SclDocument | Path | str) -> list[SiprotecIed]:
    """Every IED DIGSI describes, in document order.

    An IED with no `Siemens-*` private of its own is not returned. It is not
    an error and not a gap: it is another vendor's relay in the same station,
    and describing it is not this library's job.

    Read off `ied_headers`, the cheap half of py61850's model: these privates
    are direct children of `<IED>`, so no instance tree is built to reach
    them. It also settles a question this module used to answer by accident.
    DIGSI nests a bare `<IED uuidRef=... name=...>` cross-reference inside
    `<Private><FolderDetails><FolderInfo>` for every device -- 14 decoys
    against 14 real IEDs in the reference station, each ahead of the real
    element in document order. A descendant scan found them; they survived
    only because they carry no privates and so fell out of the filter below.
    `ied_headers` matches `<IED>` as a direct child of `<SCL>`, which is the
    only place 61850-6 allows one, so the decoys are never candidates.
    """
    doc = _document(source)
    out: list[SiprotecIed] = []
    for name, header in doc.ied_headers.items():
        p = _texts(header.privates)
        if not p:
            continue
        out.append(SiprotecIed(
            name=name,
            digsi_name=p.get(_P_DIGSI_NAME, ""),
            product_code=p.get(_P_PRODUCT_CODE, ""),
            application_template=p.get(_P_TEMPLATE, ""),
            ied_id=p.get(_P_IED_ID, ""),
            folder_path=p.get(_P_FOLDER, ""),
            modification_counter=_int_or_none(p.get(_P_MOD_COUNT, "")),
            modified=p.get(_P_MOD_DATE, ""),
        ))
    return out


def _dataset_owners(doc: SclDocument) -> dict[str, str]:
    """`Siemens-GUID` of a DataSet -> the name of the IED that holds it.

    Walks each IED's logical nodes and reads the private off the `DataSet`
    model nodes. `LogicalNode.data_sets` is direct children only, which is
    what keeps a dataset attributed to the ONE logical node that declares it
    -- collecting by descent from the LDevice would give every dataset in it
    to every node.

    Costs more than the raw descendant scan it replaces -- 167 ms against 54
    on the 13.5 MB station -- and is worth it anyway: the document is parsed
    once instead of three times (257 ms), and the model caches, so the second
    question of the same file walks nothing. All 14 GUIDs of the reference
    station and all 113 of the mixed one resolve to the same IEDs either way.
    """
    owners: dict[str, str] = {}
    for ied_name in doc.ied_names:
        ied = doc.ied(ied_name)
        if ied is None:
            continue
        for node in ied.logical_nodes():
            for data_set in node.data_sets.values():
                elements = data_set.privates.get(_P_GUID)
                if not elements:
                    continue
                guid = (elements[0].text or "").strip()
                if guid:
                    owners.setdefault(guid, ied_name)
    return owners


def _text(node: ET.Element, local: str) -> str:
    for child in node:
        if child.tag.rsplit("}", 1)[-1] == local:
            return (child.text or "").strip()
    return ""


def _application_storage(doc: SclDocument):
    """Every `GooseApplicationStorage` DIGSI wrote, in document order.

    It lives inside a `<Private>` on the `<SCL>` root -- both reference files
    put it there, spelled `Siemens_SiedigGooseApplicationStorage`. The element
    is found by its LOCAL NAME inside the private rather than by that type
    string: the underscore is the odd one out among two dozen Siemens private
    types, so it is the part of this least worth depending on.
    """
    for elements in doc.privates.values():
        for private in elements:
            yield from iter_local(private, "GooseApplicationStorage")


def read_goose_applications(
        source: SclDocument | Path | str) -> list[GooseApplication]:
    """The GOOSE applications, with their datasets resolved to IEDs.

    Empty when the file has no `GooseApplicationStorage` -- an SCL from
    another tool simply has none, which is not an error.
    """
    doc = _document(source)
    storages = list(_application_storage(doc))
    if not storages:
        return []

    owners = _dataset_owners(doc)
    out: list[GooseApplication] = []
    for storage in storages:
        for node in children_local(storage, "GooseApplication"):
            guids = [ds.get("guidRef", "")
                     for ds in children_local(node, "DataSet")
                     if ds.get("guidRef")]
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
