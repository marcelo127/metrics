from io import BytesIO
import pandas as pd
import pydicom

from Aperture_complexity_metrics import extract_beam_data_from_dataset, compute_metrics


def process_rp_bytes(file_bytes, filename=None, beam_names=None):
    """Process a single RT Plan given as bytes and return a metrics dict.

    Returns a tuple (metrics_dict, summary_df) where summary_df is a pandas
    DataFrame with one row per beam found in the file.
    """
    bio = BytesIO(file_bytes)
    rp = pydicom.dcmread(bio)
    beam_data = extract_beam_data_from_dataset(rp, beam_names=beam_names)
    metrics = compute_metrics(beam_data)

    df = metrics_to_dataframe(metrics, rp)
    return metrics, df


def metrics_to_dataframe(metrics_dict, rp=None):
    # Extract PatientID (DICOM tag 0010,0020) from the DICOM dataset
    plan_id = getattr(rp, 'PatientID', '') if rp else ''
    
    rows = []
    for beam_name, m in metrics_dict.items():
        row = {}
        # Use PatientID from DICOM as Plan ID
        row["Plan ID"] = plan_id
        row["No of MUs"] = m.get("MU", None)
        row["Beam Area(BA)"] = m.get("BA_mm2", None)
        row["Beam Modulation(BM)"] = m.get("BM", None)
        row["Mean Field Area(MFA)"] = m.get("MFA_mm2", None)
        row["Mean Asymmetry Distance(MAD)"] = m.get("MAD_mm", None)
        row["Modulation Complexity Score(MCS)"] = m.get("MCS", None)
        row["Edge Metrics"] = m.get("EdgeMetric", None)
        row["Union of Aperture Area(UAA)"] = m.get("union_area_mm2", None)
        row["Average Leaf Pair Opening(ALPO)"] = m.get("AverageLP", None)
        row["Dynamic complexity score-Modulation Index(DCMI)"] = m.get("DCMI", None)
        rows.append(row)

    if len(rows) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # enforce column order matching the provided header
    cols = [
        "Plan ID",
        "No of MUs",
        "Beam Area(BA)",
        "Beam Modulation(BM)",
        "Mean Field Area(MFA)",
        "Mean Asymmetry Distance(MAD)",
        "Modulation Complexity Score(MCS)",
        "Edge Metrics",
        "Union of Aperture Area(UAA)",
        "Average Leaf Pair Opening(ALPO)",
        "Dynamic complexity score-Modulation Index(DCMI)",
    ]
    # include any extra columns at the end
    for c in df.columns:
        if c not in cols:
            cols.append(c)
    return df[cols]


def aggregate_dfs(dfs):
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)
