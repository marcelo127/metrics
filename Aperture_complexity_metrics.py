"""
Aperture-based complexity metric extraction from an RT Plan (DICOM) using pydicom.

Implements the metrics defined in:
Saroj et al., "Analysis of aperture-based complexity metrics for IMRT",
Journal of Medical Physics, Vol 50, Issue 1, Jan-Mar 2025.

Metrics computed per VMAT beam (arc):
  - Beam Area (BA)                    Eq. 1
  - Beam Modulation (BM)              Eq. 2
  - Mean Field Area (MFA)             Eq. 3
  - Mean Asymmetry Distance (MAD)
  - Small Aperture Score (SAS) at <2, <5, <20 mm leaf-gap thresholds
  - Aperture Area Variability (AAV)   Eq. 4
  - Leaf Sequence Variability (LSV)   Eq. 5
  - Modulation Complexity Score (MCS) Eq. 6

Only the RT Plan (RP) file is required -- these are purely geometric/MU
metrics derived from MLC leaf positions, jaw positions, and control-point
meterset weights. RTSTRUCT/RTDOSE are not needed for these metrics.
"""

import pickle
import numpy as np
import pydicom


def extract_beam_data(rp_path, beam_names=None):
    """Extract per-control-point MLC/jaw/MU/gantry data for each treatment beam.

    Parameters
    ----------
    rp_path : str
        Path to the RT Plan DICOM file.
    beam_names : list[str] or None
        If given, restrict extraction to beams with these BeamName values
        (e.g. ['CW', 'CCW'] for a 2-arc VMAT plan). If None, all beams that
        have an MLCX device and more than 2 control points are used
        (this filters out simple setup/static fields).

    Returns
    -------
    dict: beam_name -> dict of extracted arrays/values
    """
    rp = pydicom.dcmread(rp_path)
    return extract_beam_data_from_dataset(rp, beam_names=beam_names)


def extract_beam_data_from_dataset(rp, beam_names=None):
    """Extract per-control-point data from an already-loaded pydicom Dataset.

    This mirrors `extract_beam_data` but accepts a Dataset (useful when
    reading DICOMs from in-memory file-like objects).
    """

    # Map beam number -> planned MU (BeamMeterset), from FractionGroupSequence
    beam_mu = {}
    for rb in rp.FractionGroupSequence[0].ReferencedBeamSequence:
        if hasattr(rb, "BeamMeterset"):
            beam_mu[int(rb.ReferencedBeamNumber)] = float(rb.BeamMeterset)

    results = {}

    for beam in rp.BeamSequence:
        device_types = [d.RTBeamLimitingDeviceType for d in beam.BeamLimitingDeviceSequence]
        if "MLCX" not in device_types and "MLCY" not in device_types:
            continue  # skip static setup fields with no MLC
        if beam_names is not None and beam.BeamName not in beam_names:
            continue
        if len(beam.ControlPointSequence) <= 2:
            continue  # skip simple open fields

        bn = beam.BeamNumber
        if bn not in beam_mu:
            continue
        mu_total = beam_mu[bn]

        mlc_type = "MLCX" if "MLCX" in device_types else "MLCY"

        leaf_boundaries = None
        for d in beam.BeamLimitingDeviceSequence:
            if d.RTBeamLimitingDeviceType == mlc_type:
                leaf_boundaries = [float(x) for x in d.LeafPositionBoundaries]
        leaf_widths = np.diff(leaf_boundaries)
        n_leaves = len(leaf_widths)

        cps = beam.ControlPointSequence
        cum_weight, mlc_positions, gantry_angles = [], [], []

        last_mlc = None
        for cp in cps:
            cum_weight.append(float(cp.CumulativeMetersetWeight))
            ga = cp.get("GantryAngle", None)
            gantry_angles.append(float(ga) if ga is not None else None)

            mlc = last_mlc
            if "BeamLimitingDevicePositionSequence" in cp:
                for d in cp.BeamLimitingDevicePositionSequence:
                    if d.RTBeamLimitingDeviceType == mlc_type:
                        pos = [float(x) for x in d.LeafJawPositions]
                        mlc = (np.array(pos[:n_leaves]), np.array(pos[n_leaves:]))
            mlc_positions.append(mlc)
            last_mlc = mlc

        cum_weight = np.array(cum_weight)
        mu_per_cp = np.diff(cum_weight) * mu_total  # MU delivered in each segment

        results[beam.BeamName] = dict(
            beam_number=bn,
            mu_total=mu_total,
            n_cp=len(cps),
            n_leaves=n_leaves,
            leaf_widths=leaf_widths,
            gantry_angles=gantry_angles,
            mlc_positions=mlc_positions,   # list of (left[n], right[n]) per CP
            mu_per_cp=mu_per_cp,           # MU per segment (length n_cp - 1)
        )

    return results


def compute_metrics(beam_data):
    """Compute BA, BM, MFA, MAD, SAS, AAV, LSV, MCS for each beam."""
    summary = {}

    for beam_name, r in beam_data.items():
        n_leaves = r["n_leaves"]
        leaf_widths = r["leaf_widths"]
        n_cp = r["n_cp"]
        mlc_positions = r["mlc_positions"]
        mu_per_cp = r["mu_per_cp"]
        mu_total = r["mu_total"]

        # Aperture area at each control point
        AA = np.zeros(n_cp)
        for i in range(n_cp):
            left, right = mlc_positions[i]
            gap = np.clip(right - left, 0, None)
            AA[i] = np.sum(gap * leaf_widths)

        seg_AA = (AA[:-1] + AA[1:]) / 2.0  # average area over each segment

        # Beam Area (Eq. 1)
        BA = np.sum(mu_per_cp * seg_AA) / mu_total

        # Union of aperture area (max gap per leaf, over the whole arc)
        max_gap_per_leaf = np.zeros(n_leaves)
        for i in range(n_cp):
            left, right = mlc_positions[i]
            gap = np.clip(right - left, 0, None)
            max_gap_per_leaf = np.maximum(max_gap_per_leaf, gap)
        union_area = np.sum(max_gap_per_leaf * leaf_widths)

        # Beam Modulation (Eq. 2)
        BM = 1 - (np.sum(mu_per_cp * seg_AA) / (mu_total * union_area)) if union_area > 0 else np.nan

        # Mean Field Area (Eq. 3) -- MU-weighted mean segment area
        MFA = np.sum(seg_AA * mu_per_cp) / mu_total

        # Small Aperture Score at given leaf-gap threshold (mm)
        def sas(threshold):
            num = 0.0
            for i in range(n_cp - 1):
                left, right = mlc_positions[i]
                gap = np.clip(right - left, 0, None)
                open_leaves = gap > 0
                if open_leaves.sum() == 0:
                    continue
                frac_small = np.sum((gap < threshold) & open_leaves) / open_leaves.sum()
                num += mu_per_cp[i] * frac_small
            return num / mu_total

        SAS2, SAS5, SAS20 = sas(2), sas(5), sas(20)

        # Mean Asymmetry Distance: MU-weighted mean |center of open leaf pairs| from CAX
        mad_num = mad_den = 0.0
        for i in range(n_cp - 1):
            left, right = mlc_positions[i]
            gap = np.clip(right - left, 0, None)
            open_leaves = gap > 0
            if open_leaves.sum() == 0:
                continue
            center = (left + right) / 2.0
            seg_mad = np.mean(np.abs(center[open_leaves]))
            mad_num += mu_per_cp[i] * seg_mad
            mad_den += mu_per_cp[i]
        MAD = mad_num / mad_den if mad_den > 0 else np.nan

        # AAV, LSV, MCS (Eq. 4, 5, 6) computed per pair of successive control points
        AAV_list, LSVL_list, LSVR_list = [], [], []
        # additional aggregators for new metrics
        edge_num = 0.0
        alpo_num = 0.0
        leaf_motion_num = 0.0
        for i in range(n_cp - 1):
            left_i, right_i = mlc_positions[i]
            left_j, right_j = mlc_positions[i + 1]
            gap_i = np.clip(right_i - left_i, 0, None)
            gap_j = np.clip(right_j - left_j, 0, None)
            max_gap = max(gap_i.max(), gap_j.max())
            if max_gap <= 0:
                AAV_list.append(0.0); LSVL_list.append(0.0); LSVR_list.append(0.0)
                continue

            AAV_list.append((gap_i.sum() + gap_j.sum()) / (2.0 * max_gap * n_leaves))

            def lsv_bank(pos_i, pos_j):
                N = n_leaves
                den = (N - 1) * max_gap
                num = den - np.sum(np.abs(pos_i - pos_j))
                return num / den if den > 0 else 0.0

            LSVL_list.append(lsv_bank(left_i, left_j))
            LSVR_list.append(lsv_bank(right_i, right_j))

            # Edge metric (irregularity per area) -- MU-weighted
            # approximate irregularity as sum of absolute differences between adjacent leaf gaps
            irregularity = np.sum(np.abs(np.diff(gap_i)))
            seg_area = (gap_i.sum() + gap_j.sum()) / 2.0
            edge_comp = irregularity / (seg_area + 1e-9)
            edge_num += mu_per_cp[i] * edge_comp

            # Average Leaf Pair Opening (ALPO): MU-weighted mean gap across open leaf pairs
            if open_leaves.sum() > 0:
                alpo_seg = np.mean(gap_i[open_leaves])
                alpo_num += mu_per_cp[i] * alpo_seg

            # Leaf motion: MU-weighted sum of absolute leaf movements (left + right)
            leaf_motion = np.sum(np.abs(left_j - left_i) + np.abs(right_j - right_i))
            leaf_motion_num += mu_per_cp[i] * leaf_motion

        AAV_arr = np.array(AAV_list)
        LSV_avg = (np.array(LSVL_list) + np.array(LSVR_list)) / 2.0
        MCS = np.sum(AAV_arr * LSV_avg * mu_per_cp) / mu_total

        # finalize additional metrics
        EdgeMetric = edge_num / mu_total if mu_total > 0 else np.nan
        AverageLP = alpo_num / mu_total if mu_total > 0 else np.nan
        # normalize leaf motion by (mu_total * union_area) to get a dimensionless factor
        norm_leaf_motion = leaf_motion_num / (mu_total * union_area + 1e-9) if mu_total > 0 else 0.0
        # Dynamic complexity (DCMI) -- combine MCS and normalized leaf motion
        DCMI = MCS * norm_leaf_motion

        summary[beam_name] = dict(
            MU=mu_total, n_cp=n_cp,
            BA_mm2=BA, BM=BM, MFA_mm2=MFA, MAD_mm=MAD,
            SAS_lt2mm=SAS2, SAS_lt5mm=SAS5, SAS_lt20mm=SAS20,
            mean_AAV=AAV_arr.mean(), mean_LSV=LSV_avg.mean(),
            MCS=MCS, union_area_mm2=union_area,
            EdgeMetric=EdgeMetric, AverageLP=AverageLP, DCMI=DCMI,
        )

    return summary


if __name__ == "__main__":
    RP_PATH = "user-data/uploads/RP.1.2.246.352.221.5202300246109785764.5200892249185658008.dcm"

    beam_data = extract_beam_data(RP_PATH, beam_names=["CW", "CCW"])
    metrics = compute_metrics(beam_data)

    for name, m in metrics.items():
        print(f"\n=== Beam: {name} ===")
        for k, v in m.items():
            print(f"  {k:15s}: {v:.4f}" if isinstance(v, float) else f"  {k:15s}: {v}")