# Aperture Complexity Metrics — Streamlit UI

This small app provides a single-page Streamlit UI to upload multiple RT Plan DICOM files (.dcm), compute aperture-based complexity metrics, and download an Excel summary.

Quick start

1. Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the Streamlit app:

```powershell
streamlit run streamlit_app.py
```

Usage

- Upload multiple `.dcm` RT Plan files using the file picker.
- The app will process files sequentially and provide a downloadable `aperture_metrics_summary.xlsx` workbook containing a `Summary` sheet.

Edge metric

The edge metric follows the supplied formula:

`M = sum(Wi * (C1*xi + C2*yi) / Ai)` and `P = C * M`

`Ai` is aperture area in mm^2, `xi` is exposed leaf-end length in mm, `yi` is exposed leaf-side length in mm, and `Wi` is the MU-delivered segment weight. `C1`, `C2`, and `C` are configurable in the Streamlit sidebar and default to 1.0. The exported `M` and `P` values have units of 1/mm when the constants are dimensionless.

Output units

- MU: monitor units
- BA, MFA, and UAA: mm^2
- MAD and ALPO: mm
- Edge M and P: 1/mm
- BM, MCS, and DCMI: dimensionless

Notes

- The app processes files in-memory and is designed for many small files (user indicated ~<5 MB each). For very large uploads or heavy concurrency, adjust to use temporary storage.
- Additional metrics (Edge metrics, DCMI/VCM) can be added to the processing pipeline; please confirm which to prioritize.
