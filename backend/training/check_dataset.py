import pandas as pd
df=pd.read_csv(r"C:\Users\kandu\OneDrive\Desktop\CivicFlow-AI\dataset\department_dataset.csv")

print("Columns:")
print(df.columns)

print("\n unique departments", df["department"].unique())

print("\nDepartment Counts:")
print(df["department"].value_counts())

print("\nDuplicate Rows:")
print(df.duplicated().sum())

print("\nMissing Values:")
print(df.isnull().sum())




