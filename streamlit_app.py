import streamlit as st
import pandas as pd
from io import BytesIO

from metrics_runner import process_rp_bytes, aggregate_dfs


st.set_page_config(page_title="Aperture Complexity Metrics", layout="wide")

st.title("Aperture Complexity Metrics — Batch RT Plan Processor")

st.markdown("Upload multiple RT Plan DICOM files (.dcm). The app will compute aperture-based metrics and produce an Excel summary.")

uploaded = st.file_uploader("Upload RT Plan DICOM files", accept_multiple_files=True, type=["dcm"])

if uploaded:
    max_files = len(uploaded)
    progress = st.progress(0)
    status_text = st.empty()

    dfs = []
    for i, up in enumerate(uploaded, start=1):
        status_text.text(f"Processing {i}/{max_files}: {up.name}")
        try:
            data = up.read()
            _, df = process_rp_bytes(data, filename=up.name)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            st.warning(f"Failed to process {up.name}: {e}")
        progress.progress(int(i / max_files * 100))

    progress.empty()
    status_text.empty()

    if dfs:
        summary = aggregate_dfs(dfs)
        st.success(f"Processed {len(dfs)} files. Summary has {len(summary)} rows.")
        st.dataframe(summary.head(200))

        # Prepare Excel
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Summary", index=False)
        out.seek(0)

        st.download_button("Download Excel summary", data=out.read(), file_name="aperture_metrics_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No valid metrics were extracted from the uploaded files.")
