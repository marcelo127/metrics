from io import BytesIO
import pandas as pd
import pydicom

from Aperture_complexity_metrics import extract_beam_data_from_dataset, compute_metrics


def process_rp_bytes(file_bytes, filename=None, beam_names=None,
                     edge_c1=1.0, edge_c2=1.0, edge_scaling=1.0):
    """Process a single RT Plan given as bytes and return a metrics dict.

    Returns a tuple (metrics_dict, summary_df) where summary_df is a pandas
    DataFrame with one row per beam found in the file.
    """
    bio = BytesIO(file_bytes)
    try:
        rp = pydicom.dcmread(bio)
    except pydicom.errors.InvalidDicomError:
        bio.seek(0)
        rp = pydicom.dcmread(bio, force=True)
    if getattr(rp, "Modality", None) != "RTPLAN":
        raise ValueError("Uploaded DICOM is not an RT Plan (Modality must be RTPLAN).")

    beam_data = extract_beam_data_from_dataset(rp, beam_names=beam_names)
    metrics = compute_metrics(
        beam_data, edge_c1=edge_c1, edge_c2=edge_c2, edge_scaling=edge_scaling
    )

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
        row["No of MUs (MU)"] = m.get("MU", None)
        row["Beam Area(BA) (mm^2)"] = m.get("BA_mm2", None)
        row["Beam Modulation(BM) (dimensionless)"] = m.get("BM", None)
        row["Mean Field Area(MFA) (mm^2)"] = m.get("MFA_mm2", None)
        row["Mean Asymmetry Distance(MAD) (mm)"] = m.get("MAD_mm", None)
        row["Modulation Complexity Score(MCS) (dimensionless)"] = m.get("MCS", None)
        row["Edge Metric M (1/mm)"] = m.get("EdgeMetric", None)
        row["Edge Penalty P (1/mm)"] = m.get("EdgePenalty", None)
        row["Union of Aperture Area(UAA) (mm^2)"] = m.get("union_area_mm2", None)
        row["Average Leaf Pair Opening(ALPO) (mm)"] = m.get("AverageLP", None)
        row["SAS (<2 mm)"] = m.get("SAS_lt2mm", None)
        row["SAS (<5 mm)"] = m.get("SAS_lt5mm", None)
        row["SAS (<20 mm)"] = m.get("SAS_lt20mm", None)
        row["Mean Leaf Travel (MLT) (mm)"] = m.get("MeanLeafTravel_mm", None)
        row["Plan Mean Leaf Travel (MLT) (mm)"] = m.get("Plan_MLT_mm", None)
        row["Mean Dose Rate Variation ((MU/min)/degree)"] = m.get("MeanDoseRateVariation", None)
        row["Plan Average Beam Irregularity (PI)"] = m.get("Plan_PI", None)
        row["Dynamic complexity score-Modulation Index(DCMI) (dimensionless)"] = m.get("DCMI", None)
        row["Dynamic Aperture Entropy(ADE) (dimensionless)"] = m.get("ADE", None)
        rows.append(row)

    if len(rows) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # enforce column order matching the provided header
    cols = [
        "Plan ID",
        "No of MUs (MU)",
        "Beam Area(BA) (mm^2)",
        "Beam Modulation(BM) (dimensionless)",
        "Mean Field Area(MFA) (mm^2)",
        "Mean Asymmetry Distance(MAD) (mm)",
        "Modulation Complexity Score(MCS) (dimensionless)",
        "Edge Metric M (1/mm)",
        "Edge Penalty P (1/mm)",
        "Union of Aperture Area(UAA) (mm^2)",
        "Average Leaf Pair Opening(ALPO) (mm)",
        "SAS (<2 mm)",
        "SAS (<5 mm)",
        "SAS (<20 mm)",
        "Mean Leaf Travel (MLT) (mm)",
        "Plan Mean Leaf Travel (MLT) (mm)",
        "Mean Dose Rate Variation ((MU/min)/degree)",
        "Plan Average Beam Irregularity (PI)",
        "Dynamic complexity score-Modulation Index(DCMI) (dimensionless)",
        "Dynamic Aperture Entropy(ADE) (dimensionless)",
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
