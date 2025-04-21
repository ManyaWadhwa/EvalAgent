from flask import Flask, render_template, request, jsonify
import json
import os
import re
import numpy
import argparse
import nltk
from nltk.corpus import stopwords
# nltk.download('stopwords')
import string

def word_overlap_similarity(a, b):
    # Define stop words and punctuation
    stop_words = set(stopwords.words('english'))
    translator = str.maketrans('', '', string.punctuation)

    # Tokenize, lowercase, remove punctuation and stopwords
    def preprocess(text):
        tokens = text.lower().translate(translator).split()
        return set(word for word in tokens if word not in stop_words)

    words_a = preprocess(a)
    words_b = preprocess(b)

    # Compute intersection and union
    intersection = words_a & words_b
    union = words_a | words_b

    # Return Jaccard similarity
    if not union:
        return 0.0
    return len(intersection) / len(union)

def get_url_supported_criteria_list(search_results, criteria):
    final_criteria = list(filter(None, [f.strip() for f in criteria.split("\n")]))
    final_criteria_list = [{"title": f, "supporting_urls": []} for f in final_criteria]

    if not search_results:
        return final_criteria_list

    for e, q in enumerate(search_results):
        # print(q)
        results = search_results[q]
        selected_content_answers = results['selected_content_answers']
        filtered_web_results = results['filtered_web_results']
        selected_content_answers = list(filter(None, [f.strip() for f in selected_content_answers]))
        if len(selected_content_answers) == 0:
            continue
        for i, f in enumerate(final_criteria):
            similarity_index = numpy.argmax([word_overlap_similarity(f, a) for a in selected_content_answers])
            final_criteria_list[i]['supporting_urls'].append({"title": filtered_web_results[similarity_index]['name'],
                                                              "url": filtered_web_results[similarity_index]['url']})
    return final_criteria_list

def remove_numbers_from_sentences(text):
    if len(text) == 0:
        return text
    # Use regex to remove numbers followed by a period and optional space at the start of lines
    cleaned_text = re.sub(r'^\d+\.\s*', '', text)
    return cleaned_text

app = Flask(__name__)
data = []
prompt_indexed_data = {}


def get_prompt_data(prompt):
    prompt = prompt.strip()
    if prompt in prompt_indexed_data:
        print("Found prompt!")
        # print(prompt_indexed_data[prompt])
    return prompt_indexed_data.get(prompt, None)


# Load data from data.jsonl
def load_data(data_path):
    if os.path.exists(data_path):
        print("loading data...")
        with open(data_path, 'r') as file:
            raw_data = file.readlines()
            print("Num instances: ", len(raw_data))
            for line in raw_data:
                if line.strip():  # Skip empty lines
                    line_json = json.loads(line)
                    # process this in the desired format
                    search_status = line_json.get("search_results", None)
                    if search_status is not None:
                        search_results = line_json['search_results']
                        queries = {}
                        for q in search_results:
                            query = q
                            results = search_results[q]
                            filtered_results = results['filtered_web_results']
                            meta_data = [{"title": f['name'], 'url': f['url'], "snippet": f['snippet']} for f in
                                         filtered_results]
                            queries[query] = meta_data
                        aspects_with_url = get_url_supported_criteria_list(search_results, line_json['ea_criteria'])
                        processed_line = {"prompt": line_json['instruction'],
                                          'aspects': aspects_with_url,
                                          'query': queries}
                    else:
                        search_results = None
                        aspects_with_url = get_url_supported_criteria_list(search_results, line_json['ea_criteria'])
                        queries = {q:[] for q in line_json['query_responses']}
                        processed_line = {"prompt": line_json['instruction'],
                                          'aspects': aspects_with_url,
                                          'query': queries}
                    data.append(processed_line)
                    prompt_indexed_data[processed_line['prompt'].strip().replace("\n","")] = processed_line
    print("Num instances: ", len(data))
    return data


# Get all available prompts for the dropdown
def get_available_prompts():
    prompts = list(prompt_indexed_data.keys())
    # Add a default prompt if no data exists
    if not prompts:
        prompts = ["Analyze the search intent behind these queries and identify common themes in the search results."]
    # Ensure we have a blank/default option at the top
    if "Select a prompt..." not in prompts:
        prompts.insert(0, "Select a prompt...")
    return prompts


@app.route('/')
def index():
    # Load data from JSONL file
    # Get all available prompts for the dropdown
    available_prompts = get_available_prompts()

    # Initial state - no data loaded yet
    return render_template(
        'index.html',
        prompt="",
        available_prompts=available_prompts,
        queries={},
        query_count=0,
        url_count=0,
        aspects=[],
        aspect_count=0,
        has_data=False
    )


@app.route('/analyze', methods=['POST'])
def analyze():
    # Get the selected prompt from the form
    selected_prompt = request.form.get('prompt', '').strip()

    # Check if an actual prompt was selected
    if not selected_prompt or selected_prompt == "Select a prompt...":
        # No valid selection, return to initial state
        return render_template(
            'index.html',
            prompt="",
            available_prompts=get_available_prompts(),
            queries={},
            query_count=0,
            url_count=0,
            aspects=[],
            aspect_count=0,
            has_data=False
        )

    # Get the data associated with the selected prompt
    analysis_data = get_prompt_data(selected_prompt)

    if not analysis_data:
        # Failed to get data, return with the prompt but no results
        return render_template(
            'index.html',
            prompt=selected_prompt,
            available_prompts=get_available_prompts(),
            queries={},
            query_count=0,
            url_count=0,
            aspects=[],
            aspect_count=0,
            has_data=False
        )

    # Extract data for the template
    queries = analysis_data.get("query", {})
    query_count = len(queries)
    url_count = sum(len(urls) for urls in queries.values())

    aspects = analysis_data.get("aspects", [])
    aspect_count = len(aspects)

    return render_template(
        'index.html',
        prompt=selected_prompt,
        available_prompts=get_available_prompts(),
        queries=queries,
        query_count=query_count,
        url_count=url_count,
        aspects=aspects,
        aspect_count=aspect_count,
        has_data=True
    )


@app.route('/api/data')
def get_data():
    # API endpoint to fetch all data
    return jsonify(load_data())


@app.route('/api/data/<int:index>')
def get_data_by_index(index):
    # API endpoint to fetch specific data entry
    data = load_data()
    if 0 <= index < len(data):
        return jsonify(data[index])
    return jsonify({"error": "Index out of range"}), 404


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Flask app with a specific data file')
    parser.add_argument('--data', type=str, default='sample_with_criteria.jsonl',
                        help='Path to the JSONL data file (default: sample_with_criteria.jsonl)')
    args = parser.parse_args()

    # Load data with the specified file
    load_data(data_path = args.data)
    app.run(debug=True, port=5001)
