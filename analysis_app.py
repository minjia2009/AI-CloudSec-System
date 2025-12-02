import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# 1. 加载数据
df = pd.read_csv("data/statement.csv.bak")

st.title("💳 Transaction Analysis Dashboard")

# 2. 显示数据表
st.subheader("Raw Data")
st.dataframe(df.head(20))

# 3. 可视化：金额分布
st.subheader("Transaction Amount Distribution")
fig, ax = plt.subplots()
df["Transaction Amount"].hist(bins=50, ax=ax)
st.pyplot(fig)

# 4. 简单检测：大额交易
threshold = st.slider("Set anomaly threshold", 100, 1000, 500)
anomalies = df[df["Transaction Amount"].abs() > threshold]

st.subheader("⚠️ Suspicious Transactions")
st.dataframe(anomalies)

# 5. 可选：加载特征重要性（如果有）
try:
    feat_imp = pd.read_csv("models/feature_importance_rf.csv")
    st.subheader("Feature Importance")
    st.bar_chart(feat_imp.set_index("feature")["importance"])
except:
    st.info("No feature importance file found.")

