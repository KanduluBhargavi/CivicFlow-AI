import pandas as pd
df=pd.read_csv(r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\all_india_pincode.csv")
print(df.head(1))
print(df.info())
print(df.shape)
print(df.isnull().sum())
print(df["statename"].unique())
print(df["statename"].nunique())
print(df["district"].nunique())
print(df["pincode"].duplicated().sum())

df = df.dropna(subset=["district", "statename"])
print(df.isnull().sum())

df = df[
    [
        "officename",
        "pincode",
        "district",
        "statename",
        "latitude",
        "longitude"
    ]
]
df = df.rename(columns={
    "officename": "office_name",
    "statename": "state"
})

print(df.dtypes)

df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

df = df.drop_duplicates(
    subset=[
        "office_name",
        "pincode",
        "district",
        "state"
    ]
)

df = df.reset_index(drop=True)

print(df.head())
print(df.info())
print(df.shape)

df["state"] = df["state"].str.strip().str.title()
df["district"] = df["district"].str.strip().str.title()
df["office_name"] = df["office_name"].str.strip().str.title()

print(df.duplicated().sum())

df = df.dropna(subset=["latitude", "longitude"])

district_df = (
    df.groupby(["state", "district"], as_index=False)
      .agg({
          "latitude": "mean",
          "longitude": "mean"
      })
)

print("this is ",district_df.duplicated(subset=["state", "district"]).sum())
print(district_df.head())
print(district_df.info())
print(district_df.shape)

print("\nMissing Values")
print(district_df.isnull().sum())

district_df.to_csv(
    r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\district_coordinates.csv",
    index=False
)


