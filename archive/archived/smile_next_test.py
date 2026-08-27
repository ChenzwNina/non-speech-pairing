import requests
import pandas as pd
import json


DATASET = "mok0102/SMILE-Next"

# ---------------------------------------------------
# 1. Get Hugging Face auto-converted parquet URLs
# ---------------------------------------------------

api_url = f"https://huggingface.co/api/datasets/{DATASET}/parquet"

parquet_info = requests.get(api_url).json()

print("Available configs/splits:")
print(parquet_info.keys())

# Usually the config is called "default"
splits = parquet_info["default"]

print("\nSplits:")
for split, urls in splits.items():
    print(split, urls)


# ---------------------------------------------------
# 2. Read all splits
# ---------------------------------------------------

dfs = []

for split, urls in splits.items():
    for url in urls:
        print(f"Reading {split}: {url}")

        temp = pd.read_parquet(url)
        temp["split"] = split
        dfs.append(temp)

df = pd.concat(dfs, ignore_index=True)

print("\nTotal rows:", len(df))
print("\nTask distribution:")
print(df["task"].value_counts())


# ---------------------------------------------------
# 3. Keep classification samples only
# ---------------------------------------------------

clf = df[
    df["task"].astype(str).str.lower() == "classify"
].copy()

print("\nNumber of classification samples:", len(clf))


# ---------------------------------------------------
# 4. Extract ground-truth assistant answer
# ---------------------------------------------------

def extract_answer(conversations):
    """
    Expected format:
    [
        {"from": "human", "value": "..."},
        {"from": "gpt",   "value": "..."}
    ]
    """

    if conversations is None:
        return None

    # Sometimes parquet returns numpy arrays instead of lists
    try:
        turns = list(conversations)
    except Exception:
        return None

    for turn in reversed(turns):

        # turn should usually be a dict
        if isinstance(turn, dict):
            speaker = str(turn.get("from", "")).lower()

            if speaker in ["gpt", "assistant"]:
                return turn.get("value", "")

    return None


clf["answer"] = clf["conversations"].apply(extract_answer)

print("\nSome raw answers:")
print(clf["answer"].head(20).to_string(index=False))


# ---------------------------------------------------
# 5. Normalize into the three SMILE-Next classes
# ---------------------------------------------------

# ---------------------------------------------------
# 5. Extract the classified label
# ---------------------------------------------------

LABELS = [
    "Mirthful",
    "Polite",
    "Satirical"
]

def extract_label(answer):
    if answer is None:
        return "Missing"

    answer = str(answer).strip()

    # Match the three expected labels first
    for label in LABELS:
        if label.lower() in answer.lower():
            return label

    # If it doesn't match, show the actual answer
    # instead of calling it "Unknown"
    return answer


clf["label"] = clf["answer"].apply(extract_label)


# ---------------------------------------------------
# 6. Show ALL labels found
# ---------------------------------------------------

summary = (
    clf["label"]
    .value_counts()
    .rename("count")
    .to_frame()
)

summary["percentage"] = (
    summary["count"] / len(clf) * 100
)

print("\n=============================")
print("SMILE-Next classification distribution")
print("=============================")

print(summary.round(2))


LABELS = ["Mirthful", "Polite", "Satirical", "The humor type is Release", "The humor type is Hostility."]

# ---------------------------------------------------
# Extract utterances from textrep
# ---------------------------------------------------

def extract_utterances(textrep):
    if textrep is None:
        return ""

    # In case it is stored as a JSON string
    if isinstance(textrep, str):
        try:
            textrep = json.loads(textrep)
        except Exception:
            return textrep

    if not isinstance(textrep, dict):
        return str(textrep)

    utterances = []

    # textrep usually has keys "0", "1", "2", ...
    numbered_keys = [
        k for k in textrep.keys()
        if str(k).isdigit()
    ]

    numbered_keys = sorted(
        numbered_keys,
        key=lambda x: int(x)
    )

    for k in numbered_keys:
        turn = textrep[k]

        if not isinstance(turn, dict):
            continue

        utterance = (
            turn.get("utterance")
            or turn.get("Utterance")
            or ""
        )

        speaker = (
            turn.get("Speaker")
            or turn.get("speaker")
            or ""
        )

        if utterance:
            if speaker:
                utterances.append(f"{speaker}: {utterance}")
            else:
                utterances.append(utterance)

    return " | ".join(utterances)


clf["utterances"] = clf["textrep"].apply(extract_utterances)


# ---------------------------------------------------
# Sample 10 from each category
# ---------------------------------------------------

# ---------------------------------------------------
# Sample 10 examples from each category
# ---------------------------------------------------

output = {}

# ---------------------------------------------------
# Helper: extract GPT/assistant answer
# ---------------------------------------------------

def extract_answer(conversations):
    if conversations is None:
        return None

    try:
        turns = list(conversations)
    except Exception:
        return None

    for turn in reversed(turns):
        if isinstance(turn, dict):
            speaker = str(turn.get("from", "")).lower()

            if speaker in ["gpt", "assistant"]:
                return turn.get("value", "")

    return None


# ---------------------------------------------------
# 1. Classification rows
# ---------------------------------------------------

clf = df[
    df["task"].astype(str).str.lower() == "classify"
].copy()

clf["classification_answer"] = (
    clf["conversations"].apply(extract_answer)
)


# Normalize classification label
def extract_label(answer):
    if answer is None:
        return None

    answer_lower = str(answer).lower()

    for label in LABELS:
        if label.lower() in answer_lower:
            return label

    # Preserve unexpected raw answer
    return str(answer).strip()


clf["label"] = clf["classification_answer"].apply(extract_label)


# ---------------------------------------------------
# 2. Reasoning rows
# ---------------------------------------------------

reason_df = df[
    df["task"].astype(str).str.lower() == "reason"
].copy()

reason_df["reason"] = (
    reason_df["conversations"].apply(extract_answer)
)


print("Classification examples:", len(clf))
print("Reasoning examples:", len(reason_df))


# ---------------------------------------------------
# 3. Build ID -> reason lookup
# ---------------------------------------------------

# If each id has one reason row:
reason_lookup = (
    reason_df
    .dropna(subset=["id"])
    .drop_duplicates(subset=["id"])
    .set_index("id")["reason"]
    .to_dict()
)


# ---------------------------------------------------
# 4. Sample 10 classification examples per category
# ---------------------------------------------------

output = {}

for label in LABELS:

    subset = clf[clf["label"] == label]

    sampled = subset.sample(
        n=min(10, len(subset)),
        random_state=42
    )

    examples = []

    for _, row in sampled.iterrows():

        example_id = row.get("id")

        example = {
            "id": example_id,
            "label": label,

            # classification GT
            "classification_answer": row.get(
                "classification_answer"
            ),

            # matched reasoning GT
            "reason": reason_lookup.get(
                example_id,
                None
            ),

            # multimodal textual representation
            "textrep": row.get("textrep"),
        }

        # Optional metadata
        optional_fields = [
            "video_title",
            "video_start",
            "video_end",
            "video_url_or_path",
        ]

        for field in optional_fields:

            if field not in row.index:
                continue

            value = row.get(field)

            # Handle lists/dicts safely
            if isinstance(value, (list, dict)):
                example[field] = value

            # Handle normal scalars
            elif value is not None:
                try:
                    if not pd.isna(value):
                        example[field] = value
                except Exception:
                    example[field] = value

        examples.append(example)

    output[label] = examples


# ---------------------------------------------------
# 5. Save JSON
# ---------------------------------------------------

output_path = "smile_next_10_per_category_with_reason.json"

with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2,
        default=str
    )


print(f"\nSaved to: {output_path}")