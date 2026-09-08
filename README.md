# Siemenslib

Read what DIGSI writes into an SCL file **beside** the standard.

```bash
pip install siemenslib
```

```python
from py61850.scl import SclDocument
from siemenslib import digsi

doc = SclDocument.parse("station.scd")      # parsed once, asked three times

for ied in digsi.read_ieds(doc):
    print(ied.name, ied.device, ied.digsi_name, ied.application_template)
# QPC2_TR1_AL11 7SJ85 AL11_UPC1 7SJ85_Non_Directional_OC
# QPC1_TR1_UPC1 7UT85 TR1_UPC1  7UT8x_2WindTransformer_Basic

for app in digsi.read_goose_applications(doc):
    print(app.name, app.app_id, app.ied_names)
# 138 kV  0001 ['QPC1_LT1_UPC1', 'QPC1_LT2_UPC1', ...]
# 34,5 kV 0002 ['QPC2_TR1_AL11', 'QPC2_TR1_AL12', ...]
```

Every reader also takes a plain path and parses a document for itself. Pass
one `SclDocument` when you ask more than one question about the same file: on
the 13.5 MB mixed-vendor reference station that is 400 ms instead of 917.

| module | what it reads |
|---|---|
| `siemenslib.digsi` | the `Siemens-*` privates and the `siedig` namespace in an SCD/ICD: SIPROTEC product codes, application templates, DIGSI names and revisions, and the GOOSE applications |

## Why this exists

An SCD from the Siemens IEC 61850 System Configurator is ordinary SCL with a
second layer folded into it. The reference station — 14 IEDs — carries **2,473**
`<Private type="Siemens-*">` elements, and no vendor-neutral reader looks at
one of them. They hold what a commissioning engineer actually asks about a
SIPROTEC: which device it is, which application template it was built from,
what DIGSI calls it, and when it last changed.

The GOOSE applications are the part that earns the library. DIGSI groups
datasets into named applications — "138 kV", "34,5 kV" — and the grouping is
by GUID:

```xml
<Private type="Siemens_SiedigGooseApplicationStorage">    <!-- on <SCL> -->
  <siedig:GooseApplication name="138 kV">
    <siedig:DataSet guidRef="1f741f02..." />        <!-- an opaque hex string -->

<IED name="QPC1_TR1_UPC1"> … <LN0> <DataSet>
    <Private type="Siemens-GUID">1f741f02...</Private>    <!-- lives over here -->
```

Walking that link turns a list of hex strings into the IEDs that publish in
each application. On the reference station all 14 datasets resolve, and the two
applications split cleanly by voltage level.

## What this does not do

**It does not read the standard half of IEC 61850, and it parses no XML at
all.** An SCD's IEDs, GOOSE control blocks, addressing and data model are
ordinary SCL, and [py61850](https://github.com/GuilhermeMarini/py61850)'s
`scl` package reads them for any vendor, as an IEC 61850-6 object model. A
second reader for one standard format would be two things to keep right
instead of one. This library is for what is Siemens' *own*, and it reads it
off py61850's model nodes.

The seam that makes that possible is standard SCL, not an arrangement made
for Siemens: `Private` elements hang off every node, keyed by `type`, and a
vendor library reads its own. The sibling
[SELlib](https://github.com/GuilhermeMarini/sellib) reads SEL's half of the
very same files the same way — the mixed-vendor reference station is a DIGSI
export containing SEL relays, and both libraries read it without sharing a
line of code or opening it twice.

**It does not write.** Reading is what a commissioning job needs from these
privates; nothing here modifies a project DIGSI owns.

## Status

Alpha, and proven against two real stations: a 7 MB DIGSI export (14 IEDs, 2
GOOSE applications, 14 dataset GUIDs) and a 13.5 MB mixed-vendor one (14 IEDs,
14 applications, 113 GUIDs). Every field the previous XML-walking reader
produced is reproduced exactly by the model-based one.

## Licence

AGPL-3.0-or-later.
