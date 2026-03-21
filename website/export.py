from datasets import load_dataset
import json

ds = load_dataset("HabibaAbderrahim/Tunisian-Proverbs-with-Image-Associations-A-Cultural-and-Linguistic-Dataset")

df = ds["train"].to_pandas()[[
    "tunisan_proverb",
    "context",
    "proverb_arabic_explaination",
    "image_path_1",
    "image_path_2",
    "image_path_3",
    "image_path_4"
]]

df = df.dropna(subset=["tunisan_proverb"])
df["proverb_arabic_explaination"] = df["proverb_arabic_explaination"].fillna("لا يوجد شرح متاح")
df["context"] = df["context"].fillna("غير محدد")

# Extract just the URL string from the image object
def extract_url(val):
    if isinstance(val, dict) and val.get("path"):
        return val["path"]
    return ""

df["image_path_1"] = df["image_path_1"].apply(extract_url)
df["image_path_2"] = df["image_path_2"].apply(extract_url)
df["image_path_3"] = df["image_path_3"].apply(extract_url)
df["image_path_4"] = df["image_path_4"].apply(extract_url)

records = df.to_dict(orient="records")
with open("proverbs.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"Done! Exported {len(records)} proverbs")