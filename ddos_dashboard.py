# ddos_dashboard.py
import pandas as pd
import numpy as np
import streamlit as st
import os

st.set_page_config(layout="wide", page_title="DDOS Traffic Dashboard")
st.title("🚨 DDOS Dashboard — firewall-style export (src/dst/time/bytes)")

# load CSV (adjust path if needed)
csv_path = "data/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv"
try:
    raw = pd.read_csv(csv_path)
except Exception as e:
    st.error(f"Failed to load CSV at {csv_path}: {e}")
    st.stop()

st.subheader("Raw dataset preview")
st.write(f"Rows: {len(raw):,}, Columns: {len(raw.columns)}")
st.dataframe(raw.head())

# helper to find likely column names (case-insensitive)
def find_column(df, candidates):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None

# detect common fields
src_ip_col = find_column(raw, ["Source IP","Src IP","src_ip","saddr","sip","srcip"])
dst_ip_col = find_column(raw, ["Destination IP","Dst IP","dst_ip","daddr","dip","dstip"])
dst_port_col = find_column(raw, ["Destination Port","Dst Port","dport","dstport","destination_port"])
bytes_col = find_column(raw, ["Bytes","Flow Bytes/s","Total Length","TotLen"])
time_candidates = [c for c in raw.columns if "time" in c.lower() or "timestamp" in c.lower() or "date" in c.lower()]

st.write("Detected:", {
    "src_ip": src_ip_col,
    "dst_ip": dst_ip_col,
    "dst_port": dst_port_col,
    "bytes": bytes_col,
    "time_candidates": time_candidates[:3]
})

# robust timestamp parser: try string parse, unix seconds, unix ms
def parse_ts(df, candidates):
    for c in candidates:
        try:
            s = df[c]
        except Exception:
            continue
        p = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
        if p.notna().mean() > 0.5:
            return p, c
        try:
            p2 = pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="s", errors="coerce")
            if p2.notna().mean() > 0.5:
                return p2, c
        except Exception:
            pass
        try:
            p3 = pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="ms", errors="coerce")
            if p3.notna().mean() > 0.5:
                return p3, c
        except Exception:
            pass
    return pd.Series(pd.NaT, index=df.index), None

ts_series, used_time_col = parse_ts(raw, time_candidates)
if used_time_col:
    st.success(f"Parsed time column: {used_time_col}")
else:
    st.warning("Timestamp parse failed — time-window features will be disabled.")

# safe numeric conversion
def safe_num(s):
    s2 = pd.to_numeric(s, errors="coerce")
    s2 = s2.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return s2.astype(float)

# bytes fallback
if bytes_col:
    bytes_series = safe_num(raw[bytes_col])
else:
    bytes_series = pd.Series(0.0, index=raw.index)

# build normalized frame
norm = pd.DataFrame({
    "_ts": ts_series,
    "_src_ip": raw[src_ip_col] if src_ip_col else pd.NA,
    "_dst_ip": raw[dst_ip_col] if dst_ip_col else pd.NA,
    "_dst_port": raw[dst_port_col] if dst_port_col else pd.NA,
    "_bytes": bytes_series
})

# safe totals
total_bytes = float(norm["_bytes"].replace([np.inf, -np.inf], np.nan).fillna(0.0).sum())
st.subheader("Normalized quick stats")
st.write("Total bytes:", f"{total_bytes:,.0f}")
st.write("Unique src IPs:", int(norm["_src_ip"].nunique(dropna=True)))
st.write("Unique dst ports:", int(norm["_dst_port"].nunique(dropna=True)))

st.markdown("---")
st.subheader("Top lists")
if norm["_src_ip"].notna().any():
    st.write("Top source IPs (by bytes)")
    st.dataframe(norm.groupby("_src_ip")["_bytes"].sum().sort_values(ascending=False).head(20))
else:
    st.info("No source IP column detected")

if norm["_dst_port"].notna().any():
    st.write("Top destination ports (by count)")
    st.dataframe(norm["_dst_port"].astype(str).value_counts().head(20))
else:
    st.info("No destination port column detected")

st.markdown("---")
if not norm["_ts"].isna().all():
    agg_minutes = st.slider("Aggregation window minutes", 1, 10, 1)
    label = f"{agg_minutes}T"
    tdf = norm.dropna(subset=["_ts"]).set_index("_ts")
    flows = tdf.resample(label).size().rename("flow_count")
    bytes_agg = tdf["_bytes"].resample(label).sum().rename("bytes_sum")
    summary = pd.concat([flows, bytes_agg], axis=1).fillna(0)
    st.write("Time bins (preview):")
    st.dataframe(summary.head(40))
    pct = st.slider("Percentile threshold for attack", 90, 99, 95)
    th_bytes = np.percentile(summary["bytes_sum"], pct)
    attack_bins = summary[summary["bytes_sum"] >= th_bytes]
    st.write("Detected attack bins (by bytes):")
    st.dataframe(attack_bins)
    rows = []
    for start in attack_bins.index:
        end = start + pd.Timedelta(minutes=agg_minutes)
        w = norm[(norm["_ts"] >= start) & (norm["_ts"] < end)]
        if w.empty:
            continue
        ag = w.groupby(["_src_ip", "_dst_ip", "_dst_port"]).agg(
            flow_count=("_bytes", "count"),
            total_bytes=("_bytes", "sum")
        ).reset_index()
        ag["window_start"] = start
        ag["window_end"] = end
        rows.append(ag)
    if rows:
        out = pd.concat(rows, ignore_index=True)
        os.makedirs("reports", exist_ok=True)
        out.to_csv("reports/firewall_export.csv", index=False)
        st.success("Exported reports/firewall_export.csv")
else:
    st.info("Timestamp missing — cannot build time-windowed export.")
