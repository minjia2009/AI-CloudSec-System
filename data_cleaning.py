import pandas as pd

# 读取原始大数据
df = pd.read_csv("data/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv")

# 去掉空值
df = df.dropna()

# 取前 500 行（避免文件太大）
df_small = df.head(500)

# 保存清洗后的结果
df_small.to_csv("data/cleaned_dataset.csv", index=False)

print("✅ Cleaned dataset saved to data/cleaned_dataset.csv")
