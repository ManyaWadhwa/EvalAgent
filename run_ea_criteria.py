import argparse
import json
import os
import pandas
from run_model import get_response
import ast
from utils import edit_string_to_not_have_filler_text
from get_search_results import get_search_criteria
from criteria_aggregation import combine_query_lists, post_query_summarization_and_filtering

def get_query(instruction: str, query_model: str) -> list[str]:
    """

    :param instruction:
    :param query_model:
    :return:
    """
    evaluation_query_prompt = """Instruction:
'{instruction}'

What should I google so I learn useful advice on writing a great response to the above instruction? Give a JSON response with three most important google queries as keys. The queries should be in the form  of "how to" or "what are" etc and the value is what we want to learn from the query. The queries should focus on seeking actionable writing advice instead of focusing on abstract knowledge concepts.  
"""
    prompt_to_run = evaluation_query_prompt.format(**{"instruction": instruction})
    response = get_response(model_name = query_model, prompt= prompt_to_run)
    if '```' in response:
        response = response.split("```")[1].replace("json", "").strip()
    try:
        queries = ast.literal_eval(response)
        return queries
    except Exception as e:
        raise ValueError(e)
        # return []


def get_llm_criteria(queries, answer_model):
    llm_query_responses = {}
    for i, query in enumerate(queries):
        query_prompt = f"{query}\n\nGive a list where each line corresponds to one point."
        response = get_response(prompt=query_prompt, model_name=answer_model)
        response = response.replace("**", "").strip()
        filtered_response = edit_string_to_not_have_filler_text(response)
        filtered_response = "\n".join(list(filter(None, [f.strip() for f in filtered_response.split("\n")])))
        llm_query_responses[query] = filtered_response
    return llm_query_responses


def get_aspects(input_file, output_file, search, query_model, aggregator_model, answer_model):
    data = []
    if input_file.endswith("xlsx"):
        data = pandas.read_excel(input_file)
    elif input_file.endswith("jsonl"):
        data = pandas.read_json(input_file, lines=True)
    else:
        raise ValueError("input file extension not valid, not in [xlsx, jsonl]")
    print(data)
    print(f"Num instances: ", len(data))
    data = data[:5]
    with open(output_file, "w") as f_:
        for i, d in data.iterrows():
            print(f"Running instance {i}..")
            d = d.to_dict()
            instruction = d["instruction"]
            queries = get_query(instruction=instruction, query_model=query_model)
            print(f"Generated queries: {len(queries)}")
            d['queries'] = queries
            if search:
                # run search
                print('Running search..')
                criteria, search_results, search_success = get_search_criteria(instruction = instruction,
                                                  queries = queries,
                                                  aggregation_model=aggregator_model,
                                                  answer_model=answer_model)
                d['search_results'] = {}
                for k in search_results:
                    d['search_results'][k] = search_results[k]
                d['search_success'] = search_success

            if not search or not search_success:
                print("Get Query Responses from LLM..")
                criteria = get_llm_criteria(queries, answer_model)

            print("Aggregating..")
            summaries = [criteria[q] for q in criteria]

            d['query_responses'] = criteria

            raw_combined_criteria = combine_query_lists(summaries=summaries,
                                                    aggregation_model=aggregator_model)

            combined_criteria = post_query_summarization_and_filtering(instruction = instruction,
                                                                       criteria = raw_combined_criteria,
                                                                       aggregation_model=aggregator_model)
            d['criteria'] = combined_criteria['criteria']
            d['raw_criteria'] = {
                "pre_rewriting_criteria" : raw_combined_criteria,
                "pre_filtering_criteria": combined_criteria['pre_filtering_criteria'],
                "filter_raw_response":combined_criteria['filtering_criteria'],
            }
            f_.write(json.dumps(d))
            f_.write("\n")
            print("----")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file",
                        default="sample_data.jsonl",
                        help="input jsonl or xlsx with 'instruction' column")

    parser.add_argument("--output_file",
                        default=None,
                        help="output file with instruction, queries, URLs and corresponding generated criteria")

    parser.add_argument("--search",
                        action="store_true",
                        default=False,
                        help="if true uses google search to run criteria generation else uses LLM"
                        )
    parser.add_argument("--query_model",
                        default="gpt-4o-mini-2024-07-18",
                        help="model used for query generation")

    parser.add_argument("--aggregator_model",
                        default="gpt-4o-mini-2024-07-18",
                        help="model used for aggregating and summarizing query-specific information")

    parser.add_argument("--answer_model",
                        default="gpt-4o-mini-2024-07-18",
                        help="model used for answering queries; if search is false")

    args = parser.parse_args()
    input_file = args.input_file
    output_file = args.output_file
    search = args.search
    query_model = args.query_model
    aggregator_model = args.aggregator_model
    answer_model = args.answer_model

    if search:
        try:
            assert 'GOOGLE_SEARCH_API_KEY' in os.environ
        except:
            raise ValueError("GOOGLE_SEARCH_API_KEY not found in environment variables")
        try:
            assert 'CSE_ID' in os.environ
        except:
            raise ValueError("CSE_ID not found in environment variables")

    get_aspects(input_file, output_file, search, query_model, aggregator_model, answer_model)