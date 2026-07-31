import pandas as pd
df=pd.read_csv(r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\district_coordinates.csv")
print(df.head(3))
print(df.info())
print(df.shape)
print(df.isnull().sum())
print(df.duplicated().sum())
df["State"] = df["State"].str.strip()
df["District"] = df["District"].str.strip()
df["State"] = df["State"].str.title()
df["District"] = df["District"].str.title()
print(df.dtypes)
print(df[df["District"] == "Ganjam"])
print(sorted(df["State"].unique()))

STATE_MAPPING = {
    "Orissa": "Odisha",
    "Uttaranchal": "Uttarakhand",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu"
}

df["State"] = df["State"].replace(STATE_MAPPING)