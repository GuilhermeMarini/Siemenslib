"""The Siemens-private half of an SCL file, as DIGSI writes it.

The standard half -- IEDs, GOOSE control blocks, addressing, the data model --
is not read here and never will be: that is ordinary IEC 61850 and
`py61850.scl` reads it for any vendor. What this covers is what DIGSI adds
beside it, under its own namespaces and `Private` elements, which no
vendor-neutral reader looks at.

The fixture is synthetic and small, and its shape is taken from the real
files rather than invented: the GOOSE application storage sits inside a
`<Private>` on the `<SCL>` root, which is where both reference stations put
it. An earlier version of this fixture hung it directly under `<SubNetwork>`,
a place 61850-6 does not allow and no DIGSI export uses; the reader only
tolerated it because it scanned the whole tree for the element.

The reference station is a 7 MB SCD with 14 IEDs and 2,473 Siemens `Private`
elements; it is a customer file and lives in no repository, so the real-file
test is opt-in behind SIEMENSLIB_SCD_FIXTURE.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from py61850.scl import SclDocument

from siemenslib import digsi

_SCD = """<?xml version="1.0" encoding="utf-8"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL"
     xmlns:siedig="http://www.siemens.com/energy/2011/11/Siedig">
  <Private type="Siemens-FolderPath">SE EXEMPLO\\TR01 138 kV\\QPC1</Private>
  <Private type="Siemens_SiedigGooseApplicationStorage">
    <siedig:GooseApplicationStorage>
      <siedig:MacAddrMin>01-0C-CD-01-00-00</siedig:MacAddrMin>
      <siedig:GooseApplication name="138 kV" desc="" profileName="PriorityLow">
        <siedig:AppId>0001</siedig:AppId>
        <siedig:MinTime unit="s" multiplier="m">10</siedig:MinTime>
        <siedig:MaxTime unit="s" multiplier="m">2000</siedig:MaxTime>
        <siedig:VLanId>000</siedig:VLanId>
        <siedig:VLanPriority>4</siedig:VLanPriority>
        <siedig:DataSet guidRef="aaaa0000" />
        <siedig:DataSet guidRef="bbbb1111" />
      </siedig:GooseApplication>
      <siedig:GooseApplication name="34,5 kV" desc="" profileName="PriorityLow">
        <siedig:AppId>0002</siedig:AppId>
        <siedig:DataSet guidRef="cccc2222" />
      </siedig:GooseApplication>
    </siedig:GooseApplicationStorage>
  </Private>
  <Private type="Siemens_SiedigFolderDetails">
    <FolderDetails><FolderInfo>
      <IED uuidRef="1f741f02" name="QPC1_TR1_UPC1"/>
      <IED uuidRef="2e852e13" name="QPC1_TR1_UPC2"/>
    </FolderInfo></FolderDetails>
  </Private>
  <Communication>
    <SubNetwork name="Default_subnet">
      <Private type="Siemens-Start-Address">10.0.0.1</Private>
    </SubNetwork>
  </Communication>
  <IED name="QPC1_TR1_UPC1" manufacturer="SIEMENS" type="SIPROTEC 5">
    <Private type="Siemens-IED-Id">abacf2e5-9d62-44b6</Private>
    <Private type="Siemens-Siprotec5-Product-Code">7SJ85-JAAA-AA0-0WWWW0</Private>
    <Private type="Siemens-Siprotec5-Application-Template">7SJ85_Non_Directional_OC</Private>
    <Private type="Siemens-s7ManagerName">AL11_UPC1</Private>
    <Private type="Siemens-ModificationCounter">38</Private>
    <Private type="Siemens-ModifiedDate">09/22/2025 17:55:56</Private>
    <Private type="Siemens-FolderPath">SE EXEMPLO\\TR01 138 kV\\QPC1</Private>
    <AccessPoint name="S1"><Server><LDevice inst="CTRL">
      <LN0 lnClass="LLN0" inst="" lnType="SIPROTEC5_1012">
        <DataSet name="DataSet">
          <Private type="Siemens-GUID">aaaa0000</Private>
        </DataSet>
        <DataSet name="DataSet2">
          <Private type="Siemens-GUID">cccc2222</Private>
        </DataSet>
      </LN0>
    </LDevice></Server></AccessPoint>
  </IED>
  <IED name="QPC1_TR1_UPC2" manufacturer="SIEMENS" type="SIPROTEC 5">
    <Private type="Siemens-s7ManagerName">AL12_UPC2</Private>
    <Private type="Siemens-Siprotec5-Product-Code">7SJ85-KBBB-AA0-0WWWW0</Private>
    <AccessPoint name="S1"><Server><LDevice inst="CTRL">
      <LN0 lnClass="LLN0" inst="" lnType="SIPROTEC5_1012">
        <DataSet name="DataSet"><Private type="Siemens-GUID">bbbb1111</Private></DataSet>
      </LN0>
    </LDevice></Server></AccessPoint>
  </IED>
  <IED name="SEL_451" manufacturer="SEL" type="SEL_451"><AccessPoint name="S1"/></IED>
</SCL>
"""

_NOT_SIEMENS = """<?xml version="1.0" encoding="utf-8"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
  <IED name="SEL_451" manufacturer="SEL"><AccessPoint name="S1"/></IED>
</SCL>
"""


def _write(tmp_path: Path, text: str = _SCD) -> Path:
    p = tmp_path / "station.scd"
    p.write_text(text, encoding="utf-8")
    return p


# -- is there anything of Siemens' in here at all ---------------------------

def test_a_digsi_file_is_recognised(tmp_path):
    assert digsi.is_digsi(_write(tmp_path)) is True


def test_an_scl_with_no_siemens_private_is_not(tmp_path):
    """Answered on the file's content, never on a filename or a manufacturer
    attribute: an SCD is a station, and a station is not one vendor."""
    assert digsi.is_digsi(_write(tmp_path, _NOT_SIEMENS)) is False


def test_the_declared_namespace_alone_is_enough(tmp_path):
    """A file may declare DIGSI's namespace and carry no private this module
    reads. It is still a DIGSI export, and saying otherwise would send a
    caller looking for another tool's reader."""
    only_ns = _NOT_SIEMENS.replace(
        '<SCL xmlns="http://www.iec.ch/61850/2003/SCL">',
        '<SCL xmlns="http://www.iec.ch/61850/2003/SCL"\n'
        '     xmlns:siedig="http://www.siemens.com/energy/2011/11/Siedig">')
    assert digsi.is_digsi(_write(tmp_path, only_ns)) is True


def test_an_ied_private_alone_is_enough(tmp_path):
    """The other direction: no DIGSI namespace declared, but a device
    described. Both halves are checked because the corpus has files that lead
    with either."""
    ied_only = _NOT_SIEMENS.replace(
        '<AccessPoint name="S1"/>',
        '<Private type="Siemens-IED-Id">abacf2e5</Private>'
        '<AccessPoint name="S1"/>')
    assert digsi.is_digsi(_write(tmp_path, ied_only)) is True


# -- the IEDs ---------------------------------------------------------------

def test_only_ieds_that_carry_siemens_private_come_back(tmp_path):
    """The reference station holds SEL IEDs beside the SIPROTECs. An IED with
    no Siemens private is not this library's to describe."""
    ieds = digsi.read_ieds(_write(tmp_path))
    assert [i.name for i in ieds] == ["QPC1_TR1_UPC1", "QPC1_TR1_UPC2"]


def test_an_ied_carries_what_digsi_knows_about_it(tmp_path):
    ied = digsi.read_ieds(_write(tmp_path))[0]
    assert ied.digsi_name == "AL11_UPC1"
    assert ied.product_code == "7SJ85-JAAA-AA0-0WWWW0"
    assert ied.application_template == "7SJ85_Non_Directional_OC"
    assert ied.ied_id == "abacf2e5-9d62-44b6"
    assert ied.modification_counter == 38
    assert ied.modified == "09/22/2025 17:55:56"
    assert ied.folder_path == "SE EXEMPLO\\TR01 138 kV\\QPC1"


def test_the_device_is_the_product_code_up_to_the_first_dash(tmp_path):
    """`7SJ85-JAAA-...` is a 7SJ85. The rest of the order code says which
    cards are fitted, which is a different question from what the relay is."""
    assert [i.device for i in digsi.read_ieds(_write(tmp_path))] == ["7SJ85", "7SJ85"]


def test_a_missing_private_is_empty_and_never_an_error(tmp_path):
    """DIGSI does not write every private for every device, and a station
    that half-answers is still worth reading."""
    ied = digsi.read_ieds(_write(tmp_path))[1]
    assert ied.application_template == ""
    assert ied.modification_counter is None
    assert ied.product_code == "7SJ85-KBBB-AA0-0WWWW0"


def test_digsis_own_ied_cross_references_are_not_devices(tmp_path):
    """DIGSI nests a bare `<IED uuidRef= name=>` inside
    `<Private><FolderDetails><FolderInfo>` for every device in the project
    tree -- 14 decoys against 14 real IEDs in the reference station, each
    ahead of the real element in document order.

    Reading IEDs as direct children of `<SCL>`, which is the only place
    61850-6 allows one, makes them structurally impossible to reach. The
    filter on "has a Siemens private" used to hide them by accident: the
    decoys carry none, so they fell out. That accident stops the moment a
    DIGSI version writes one.
    """
    ieds = digsi.read_ieds(_write(tmp_path))
    assert len(ieds) == 2
    assert all(i.ied_id or i.digsi_name for i in ieds)


# -- the GOOSE applications -------------------------------------------------

def test_the_goose_applications_are_read(tmp_path):
    apps = digsi.read_goose_applications(_write(tmp_path))
    assert [a.name for a in apps] == ["138 kV", "34,5 kV"]
    a = apps[0]
    assert (a.app_id, a.profile, a.vlan_id, a.vlan_priority) == ("0001", "PriorityLow", "000", 4)
    assert (a.min_time_ms, a.max_time_ms) == (10, 2000)
    assert a.dataset_guids == ["aaaa0000", "bbbb1111"]


def test_an_application_resolves_to_the_ieds_that_publish_in_it(tmp_path):
    """This is the whole point of reading the privates. The application names
    datasets by GUID; the GUID sits on a `DataSet` inside an IED's LN0. Without
    walking that, an application is a list of opaque hex strings."""
    apps = digsi.read_goose_applications(_write(tmp_path))
    assert apps[0].ied_names == ["QPC1_TR1_UPC1", "QPC1_TR1_UPC2"]
    assert apps[1].ied_names == ["QPC1_TR1_UPC1"]


def test_a_guid_that_belongs_to_no_dataset_is_not_invented(tmp_path):
    """An application may reference a dataset this file does not carry. It is
    reported as a guid with no IED, not silently dropped -- a station that
    references something missing is exactly what a reader wants to see."""
    scd = _SCD.replace('<siedig:DataSet guidRef="bbbb1111" />',
                       '<siedig:DataSet guidRef="dddd3333" />')
    apps = digsi.read_goose_applications(_write(tmp_path, scd))
    assert apps[0].dataset_guids == ["aaaa0000", "dddd3333"]
    assert apps[0].ied_names == ["QPC1_TR1_UPC1"]
    assert apps[0].unresolved_guids == ["dddd3333"]


def test_a_file_with_no_goose_application_storage_is_empty_not_an_error(tmp_path):
    assert digsi.read_goose_applications(_write(tmp_path, _NOT_SIEMENS)) == []


def test_the_storage_is_read_from_the_private_that_holds_it(tmp_path):
    """`Private` is SCL's vendor seam, and DIGSI writes the storage inside one
    on the `<SCL>` root -- both reference stations do, spelled
    `Siemens_SiedigGooseApplicationStorage`.

    Reading it there rather than by scanning the document is what keeps this
    library off the XML. The cost is that a storage somewhere else is not
    found, which is the boundary being stated here: an element outside a
    `Private` is outside the seam, and 61850-6 gives it nowhere else to be.
    """
    stray = _SCD.replace('<Private type="Siemens_SiedigGooseApplicationStorage">', "")
    stray = stray.replace("</siedig:GooseApplicationStorage>\n  </Private>",
                          "</siedig:GooseApplicationStorage>")
    assert digsi.read_goose_applications(_write(tmp_path, stray)) == []


def test_the_private_type_spelling_is_not_what_is_matched(tmp_path):
    """`Siemens_Siedig...` is the odd one out: every private carrying DATA
    spells the separator with a dash. The storage is found by the LOCAL NAME
    of the element inside the private, so a DIGSI version that renamed the
    type would not silently return no applications."""
    renamed = _SCD.replace("Siemens_SiedigGooseApplicationStorage",
                           "Siemens-GooseApplications")
    apps = digsi.read_goose_applications(_write(tmp_path, renamed))
    assert [a.name for a in apps] == ["138 kV", "34,5 kV"]


# -- one document, three questions ------------------------------------------

def test_a_document_answers_the_same_as_a_path(tmp_path):
    """Each reader used to parse the file again -- three parses of a 7 MB
    station to ask three questions. Passing one `SclDocument` is what a
    caller asking more than one should do; measured on the 13.5 MB
    mixed-vendor station, 917 ms against 400 ms."""
    path = _write(tmp_path)
    doc = SclDocument.parse(path)
    assert digsi.is_digsi(doc) == digsi.is_digsi(path)
    assert digsi.read_ieds(doc) == digsi.read_ieds(path)
    assert digsi.read_goose_applications(doc) == digsi.read_goose_applications(path)


def test_nothing_here_parses_xml_itself(tmp_path):
    """The claim the split rests on, made checkable.

    A document that refuses to be re-read from disk still answers every
    question, because every answer comes off model nodes py61850 already
    built. If a reader here went back to `ET.parse`, this fails.
    """
    path = _write(tmp_path)
    doc = SclDocument.parse(path)
    path.unlink()
    assert digsi.is_digsi(doc) is True
    assert len(digsi.read_ieds(doc)) == 2
    assert len(digsi.read_goose_applications(doc)) == 2


# -- against a real station, when there is one ------------------------------

def test_a_real_station_reads():
    path = os.environ.get("SIEMENSLIB_SCD_FIXTURE", "")
    if not path or not Path(path).is_file():
        pytest.skip("no SCD to hand; set SIEMENSLIB_SCD_FIXTURE")
    doc = SclDocument.parse(Path(path))
    assert digsi.is_digsi(doc)
    ieds = digsi.read_ieds(doc)
    assert ieds and all(i.name for i in ieds)
    apps = digsi.read_goose_applications(doc)
    assert apps
    assert any(a.ied_names for a in apps)


# ---------------------------------------------------------------------------
# The prolog guard
# ---------------------------------------------------------------------------

_BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE SCL [
  <!ENTITY a "AAAAAAAAAA">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL">
  <Private type="Siemens-IED-Id">&c;</Private>
</SCL>
"""


def test_a_document_that_declares_a_dtd_is_refused(tmp_path):
    """An SCD arrives from the client's integrator; "the file is trusted" is
    not true even on a substation LAN. Entities expand DURING the parse and
    there is no half-way to stop at, so the refusal has to come first.

    The refusal is `py61850.scl`'s and its edge cases are tested there -- a
    DOCTYPE behind half a megabyte of comment, in memory and streamed. This
    library used to carry a forty-line copy of it, which had already drifted
    from the other copy in the message it raised. What is asserted here is
    only that these three readers go through it.
    """
    bad = tmp_path / "laughs.scd"
    bad.write_text(_BILLION_LAUGHS, encoding="utf-8")
    for call in (digsi.is_digsi, digsi.read_ieds, digsi.read_goose_applications):
        with pytest.raises(digsi.DtdNotAllowed):
            call(bad)


def test_an_ordinary_scl_still_parses(tmp_path):
    """The guard reads the PROLOG only, so a file with no DOCTYPE is
    untouched -- SCL validates against an XSD by namespace and never uses a
    DTD."""
    good = tmp_path / "ok.scd"
    good.write_text(_SCD, encoding="utf-8")
    assert digsi.is_digsi(good) is True
    assert [i.name for i in digsi.read_ieds(good)]


def test_an_unreadable_file_raises_rather_than_answering_no(tmp_path):
    """`is_digsi` returning False for a file that could not be read would be
    the worst available answer: it looks like a verdict on the content."""
    with pytest.raises(OSError):
        digsi.is_digsi(tmp_path / "nao_existe.scd")
