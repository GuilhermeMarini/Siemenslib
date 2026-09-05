"""The Siemens-private half of an SCL file, as DIGSI writes it.

The standard half -- IEDs, GOOSE control blocks, addressing, the data model --
is not read here and never will be: that is ordinary IEC 61850 and `sellib.scl`
reads it for any vendor. What this covers is what DIGSI adds beside it, under
its own namespaces and `Private type="Siemens-*"` elements, which no
vendor-neutral reader looks at.

The fixture is synthetic and small. The reference station is a 7 MB SCD with 14
IEDs and 2,473 Siemens `Private` elements; it is a customer file and lives in
no repository, so the real-file test is opt-in behind SIEMENSLIB_SCD_FIXTURE.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from siemenslib import digsi

_SCD = """<?xml version="1.0" encoding="utf-8"?>
<SCL xmlns="http://www.iec.ch/61850/2003/SCL"
     xmlns:siedig="http://www.siemens.com/energy/2011/11/Siedig">
  <Private type="Siemens-FolderPath">SE EXEMPLO\\TR01 138 kV\\QPC1</Private>
  <Communication>
    <SubNetwork name="Default_subnet">
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


# -- against a real station, when there is one ------------------------------

def test_a_real_station_reads():
    path = os.environ.get("SIEMENSLIB_SCD_FIXTURE", "")
    if not path or not Path(path).is_file():
        pytest.skip("no SCD to hand; set SIEMENSLIB_SCD_FIXTURE")
    p = Path(path)
    assert digsi.is_digsi(p)
    ieds = digsi.read_ieds(p)
    assert ieds and all(i.name for i in ieds)
    apps = digsi.read_goose_applications(p)
    assert apps
    assert any(a.ied_names for a in apps)
