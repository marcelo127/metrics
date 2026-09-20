# Aperture Complexity Metrics

## Plain-language overview

This project is a small web application for examining the *geometric complexity* of radiotherapy treatment plans. A user uploads one or more RT Plan DICOM (`.dcm`) files and receives an Excel workbook of measurements for the treatment beams found in those plans.

In a modern radiotherapy machine, many narrow metal leaves, called a multi-leaf collimator (MLC), move while radiation is delivered. Together, the leaves form an opening, or **aperture**, that shapes the radiation beam. A plan with openings that are small, irregular, off-centre, or changing rapidly can be more complex to deliver. This application turns that motion and shape information into numerical metrics that can be reviewed, compared, or used in a wider quality-assurance workflow.

The application exists to make these calculations repeatable and convenient. Instead of manually extracting leaf positions and monitor units from every plan, a user can upload a batch of plans and download a single spreadsheet.

> **Important clinical boundary:** These measurements describe plan geometry and programmed delivery weights only. They do not calculate dose, verify delivery, assess patient safety, or decide whether a plan is clinically acceptable. They should be interpreted by appropriately qualified clinical staff and used alongside the organisation's established validation and quality-assurance processes.

## Who this is for

The application is intended for people working with radiotherapy plans, such as medical physicists, dosimetrists, researchers, and quality-assurance teams. It can also be used by someone without programming experience: its normal workflow is upload files, review the table, and download Excel.

Developers and analysts can use the calculation module directly from Python when they need to integrate the metrics into another workflow.

## Key terms

| Term | Meaning in this project |
| --- | --- |
| **RT Plan DICOM** | A standard medical-imaging file that stores the planned treatment-beam settings. The application accepts files with the `.dcm` extension. |
| **Beam** | One planned radiation delivery field or arc. The metrics are calculated separately for each eligible beam. |
| **VMAT arc** | A beam delivered while the machine gantry rotates and the MLC leaves can move. The program is principally aimed at this type of dynamic beam. |
| **Control point** | A snapshot in the plan that specifies machine positions at a point during a beam. Consecutive control points define a delivery segment. |
| **Segment** | The portion of delivery between two adjacent control points. Its contribution is weighted by its monitor units. |
| **Monitor unit (MU)** | A machine delivery quantity. More MU assigned to a segment means that segment has more influence on the MU-weighted metrics. |
| **Aperture / leaf gap** | The opening between the two MLC leaf banks for a leaf pair. The program treats negative gaps as closed. |
| **mm and mm²** | Millimetres and square millimetres. They are used for lengths and areas, respectively. |

## What happens when a plan is uploaded

The complete journey through the application is:

1. The user selects one or more RT Plan DICOM files in the browser.
2. The Streamlit user interface reads each selected file in memory. It does not deliberately write uploads to a project folder.
3. `pydicom` reads the DICOM content.
4. The extraction code finds eligible MLC-equipped, dynamic beams and gathers their leaf boundaries, leaf positions at each control point, cumulative delivery weights, and planned MU.
5. The calculation code derives aperture areas and the complexity metrics for every eligible beam.
6. The processing bridge turns the results into a table, combines the tables from all uploaded files, and presents the first 200 rows in the browser.
7. The interface creates an Excel file named `aperture_metrics_summary.xlsx`, containing a `Summary` worksheet for download.

The following diagram shows the responsibility of each source file:

```text
RT Plan DICOM file(s)
        |
        v
streamlit_app.py                Browser screen: upload, progress, display, download
        |
        v
metrics_runner.py               Read uploaded bytes and form spreadsheet rows
        |
        v
Aperture_complexity_metrics.py  Extract beam data and calculate metrics
        |
        v
Summary worksheet in Excel
```

## What the software includes and excludes

### Included plan information

For each eligible beam, the calculation uses:

- planned beam MU from the first fraction group;
- MLC leaf-pair boundaries, which determine leaf widths;
- MLC leaf positions at each control point; and
- cumulative meterset weights, which determine the MU assigned to each segment.

The program carries forward the most recently stated MLC positions when a control point does not repeat them, as permitted by the DICOM representation of unchanged settings.

### Beam eligibility rules

A beam is included only when all of the following are true:

- it has an `MLCX` or `MLCY` MLC limiting device;
- it has more than two control points; and
- its beam number has a planned `BeamMeterset` value in the first fraction group.

These rules deliberately exclude simple setup or static fields. The direct Python extraction function can additionally be given a list of beam names to include; the web interface currently processes all eligible beams.

### Not used by the current calculation

This implementation does not read or calculate from RT Structure Set (`RTSTRUCT`) files, dose (`RTDOSE`) files, imaging data, patient anatomy, delivered treatment logs, or jaw positions. It does not estimate clinical dose or outcome. Although a gantry angle is collected while extracting data, it is not used in the current metric formulas.

## How the calculations work

For every control point, the program finds the opening of each leaf pair:

```text
leaf gap = right-bank position - left-bank position
```

A negative opening is replaced with zero. Each open gap is multiplied by that leaf pair's width; adding those products produces aperture area. For a segment, the program uses the average of the areas at its two bounding control points. Segment values are then weighted by the MU delivered in that segment, which means parts of the beam with more planned delivery affect the result more strongly.

Several metrics are based on the same foundation but highlight different characteristics. Values should generally be compared only across plans, machines, and workflows for which their definitions and configuration are consistent.

## Metrics in the output

| Spreadsheet column | What it represents | Unit | Reading it in plain language |
| --- | --- | --- | --- |
| Plan ID | The DICOM `PatientID` field. Despite the label, this is not necessarily a separate plan identifier. | — | Identifies the source value stored in the uploaded file. Treat it as sensitive information when applicable. |
| No of MUs (MU) | Planned total monitor units for the beam. | MU | The planned delivery quantity for that beam. |
| Beam Area (BA) | MU-weighted mean aperture area across segments. | mm² | The average open beam area, giving more weight to segments that deliver more MU. |
| Beam Modulation (BM) | `1 − BA / union aperture area`. | dimensionless | Describes how much the beam's average opening differs from its full combined footprint. |
| Mean Field Area (MFA) | MU-weighted mean segment area. | mm² | In this implementation it is calculated the same way as BA, so the two columns will have the same value. |
| Mean Asymmetry Distance (MAD) | MU-weighted average distance of open leaf-pair centres from the central beam axis. | mm | Indicates how far the openings tend to sit from the centre. |
| Modulation Complexity Score (MCS) | MU-weighted combination of aperture-area variability and leaf-sequence variability. | dimensionless | A shape-and-smoothness score derived from neighbouring control points. Its interpretation should be calibrated locally. |
| Edge Metric M | MU-weighted ratio of exposed aperture edge to aperture area, using configurable end and side weights. | 1/mm when the constants are dimensionless | Gives more influence to edges relative to open area. |
| Edge Penalty P | Edge Metric M multiplied by the configurable scaling factor `C`. | 1/mm when `C` is dimensionless | A scaled version of M, useful when a chosen local convention requires it. |
| Union of Aperture Area (UAA) | Area formed by the maximum observed opening of every leaf pair over the whole beam. | mm² | The overall combined footprint of all apertures in the arc. |
| Average Leaf Pair Opening (ALPO) | MU-weighted average opening across open leaf pairs. | mm | Typical opening size of leaves that are open. |
| Dynamic complexity score-Modulation Index (DCMI) | MCS multiplied by MU-weighted leaf motion normalised by union aperture area. | dimensionless | Combines an aperture-complexity score with a normalised measure of leaf movement. |
| Dynamic Aperture Entropy (ADE) | Normalised entropy of aperture changes multiplied by the MU-weighted mean normalised change. | dimensionless | Captures both how varied the changes are and how large they are overall. |

The calculation function also returns, but the web spreadsheet does not currently export, the following intermediate values:

- `SAS_lt2mm`, `SAS_lt5mm`, and `SAS_lt20mm`: small-aperture scores, measuring the MU-weighted share of open leaf pairs below the stated gap threshold.
- `mean_AAV`: average aperture-area variability term.
- `mean_LSV`: average leaf-sequence variability term.
- `DynamicEntropy`: the normalised entropy component used by ADE.
- `DynamicApertureChange`: the MU-weighted aperture-change component used by ADE.

### Edge metric configuration

The left sidebar exposes three numbers that control the edge calculation:

```text
M = sum over segments of [Wi × (C1 × xi + C2 × yi) / Ai] / total MU
P = C × M
```

Here, `Wi` is the segment MU, `Ai` is segment aperture area, `xi` is exposed leaf-end length, and `yi` is exposed leaf-side length. `C1` weights leaf ends, `C2` weights leaf sides, and `C` scales M to form P. All three default to `1.0`.

Change these values only when there is a documented local reason to do so. Different values make results unsuitable for direct comparison with results produced using the defaults.

### Dynamic Aperture Entropy in more detail

For each pair of control points, the application measures the average absolute change in leaf gaps and divides it by the largest leaf opening seen in the beam. It places these normalised changes into five equally sized bins, calculates a normalised Shannon entropy for their distribution, and multiplies that by the MU-weighted mean normalised change. The result is ADE.

In everyday terms, ADE becomes sensitive both to *how much* the aperture changes and to whether those changes are spread across a variety of sizes.

## Using the web application

### Before you start

You need a supported Python installation and permission to run a local web application. The supplied dependencies are Streamlit, pandas, openpyxl, xlsxwriter, pydicom, and NumPy.

### First-time setup on Windows PowerShell

From the project folder, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation for this session, the project includes this optional command:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

This changes the policy only for the current PowerShell process. Follow your organisation's security guidance before using it.

### Start the application

With the virtual environment active, run:

```powershell
streamlit run streamlit_app.py
```

Streamlit will print a local address and normally open the app in a browser. Keep the PowerShell window open while using the application; stop it with `Ctrl+C` when finished.

### Process files

1. Set `C1`, `C2`, and `C` in the sidebar if required; otherwise leave each at `1.0`.
2. Choose one or more RT Plan DICOM files with **Upload RT Plan DICOM files**.
3. Wait for the progress indicator to finish. A warning appears beside any file that could not be processed.
4. Review the preview table. It shows up to 200 rows, while the Excel download contains the full collected summary.
5. Select **Download Excel summary** to save `aperture_metrics_summary.xlsx`.

The success message's “processed files” count is the number of uploads that produced at least one metric row; it is not necessarily the number of files selected. The spreadsheet contains one row per eligible beam, not necessarily one row per uploaded file. The current export does not include the DICOM file name or beam name, so retain that relationship outside the workbook if it matters for traceability.

## Working with the code

### Source-file guide

| File | Responsibility |
| --- | --- |
| `streamlit_app.py` | Builds the browser interface; accepts uploads, exposes edge settings, shows results, and writes the Excel download. |
| `metrics_runner.py` | Reads an in-memory uploaded DICOM file, calls extraction and calculation functions, maps metric keys to friendly spreadsheet headings, and concatenates results. |
| `Aperture_complexity_metrics.py` | Contains the DICOM extraction logic and all metric formulas. It also includes a small command-line example in its `__main__` block. |
| `requirements.txt` | Lists the Python packages needed to run the application. |
| `metric_Execution_cmd_commands.txt` | Contains convenience PowerShell commands for creating/activating an environment and starting the app. |

### Reusing the calculation module in Python

For a plan already saved to disk, a programmer can use the core module directly:

```python
from Aperture_complexity_metrics import extract_beam_data, compute_metrics

beam_data = extract_beam_data("path/to/rtplan.dcm")
metrics_by_beam = compute_metrics(beam_data)
```

`metrics_by_beam` is a dictionary: each key is a beam name and each value is another dictionary of metric names and values. To include only named beams, supply `beam_names`, for example `beam_names=["CW", "CCW"]`.

For bytes from an upload, service, or database instead of a path, use `process_rp_bytes` in `metrics_runner.py`. It returns both the detailed dictionary and a pandas table ready for export.

## Data handling and privacy

The browser workflow processes uploads in memory during the current app session. It reads the DICOM `PatientID` and places it in the downloadable spreadsheet's `Plan ID` column. RT Plan files and patient identifiers may be sensitive health information. Use only approved systems, access controls, storage locations, and data-sharing procedures. Do not assume that in-memory processing removes the need for local privacy, security, or retention controls.

## Known limitations and practical checks

- The program expects a conventional RT Plan structure containing `FractionGroupSequence`, `BeamSequence`, beam-limiting-device data, and control points. Missing or non-standard data can produce a warning or error.
- Only the first fraction group is used to find planned beam MU.
- MLC position data must be available at the first control point for a beam to be usable; later omitted positions are carried forward.
- A beam with no MLC, two or fewer control points, or no matching planned MU is silently left out rather than reported as a separate excluded result.
- The code chooses `MLCX` when both `MLCX` and `MLCY` appear; it does not combine two MLC devices.
- No automatic validation against a treatment delivery log or independently calculated reference result is performed.
- Numeric results can be `NaN` when an aperture has no usable area or a denominator is zero. Review such values before downstream analysis.
- The source calculates small-aperture and intermediate values, but the current web export intentionally includes only the columns listed in the metrics table above.
- The tool is designed for batches of relatively small uploads. Larger files or heavy simultaneous use may require different storage and deployment arrangements.

For a reliable operational workflow, test representative plans (including expected exclusions and edge cases) against independently reviewed reference results before relying on the exported metrics.

## Reference behind the implemented metric set

The calculation module identifies its main source as Saroj et al., “Analysis of aperture-based complexity metrics for IMRT,” *Journal of Medical Physics*, volume 50, issue 1 (January–March 2025). The code implements a project-specific selection and interpretation of metrics; consult the paper and locally approved methodology when using the values for research or clinical quality assurance.

