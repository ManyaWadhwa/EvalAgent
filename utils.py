import re
import pandas
import yaml
import os

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_data(path):
    if path.endswith("jsonl"):
        data = pandas.read_json(path, lines=True)
    elif path.endswith("xlsx"):
        data = pandas.read_excel(path)
    else:
        raise ValueError("Unsupported file type. Please use either a JSONL or XLSX file. TBA: HF support..")
    return data


def remove_numbers_from_sentences(text):
    if len(text) == 0:
        return text
    # Use regex to remove numbers followed by a period and optional space at the start of lines
    cleaned_text = re.sub(r'^\d+\.\s*', '', text)
    return cleaned_text

def edit_string_to_not_have_filler_text(text):
    pattern = r'^\d{1,2}\.'  # ^\d{1,2}\.
    found = False
    import copy
    before = copy.deepcopy(text)
    attempts = 5
    current_attempt = 0
    while not found and current_attempt < attempts:
        to_check = before.strip().split("\n")[0].strip() if isinstance(before, str) else before[0].strip()
        # print(to_check)
        match = re.match(pattern, to_check)
        if match:
            found = True
            current_attempt = attempts
            # print("keeping...")
        else:
            before = "\n".join(before.strip().split("\n")[1:]) if isinstance(before, str) else before[1:].strip()
            current_attempt += 1
            # print("not keeping...")
    found = False
    current_attempt = 0
    after = copy.deepcopy(before)
    while not found and current_attempt < attempts:
        to_check = after.strip().split("\n")[-1].strip() if isinstance(after, str) else after[-1].strip()
        # print(to_check)
        match = re.match(pattern, to_check)
        if match:
            found = True
            current_attempt = attempts
            # print("keeping...")
        else:
            after = "\n".join(after.strip().split("\n")[:-1]) if isinstance(after, str) else after[:-1].strip()
            current_attempt += 1
            # print("not keeping...")
    return after
