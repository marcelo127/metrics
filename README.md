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

Notes

- The app processes files in-memory and is designed for many small files (user indicated ~<5 MB each). For very large uploads or heavy concurrency, adjust to use temporary storage.
- Additional metrics (Edge metrics, DCMI/VCM) can be added to the processing pipeline; please confirm which to prioritize.
