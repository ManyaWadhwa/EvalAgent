import ast
from utils import remove_numbers_from_sentences, edit_string_to_not_have_filler_text
from run_model import get_response

def summarize_two_query_summaries(summ1, summ2, instruction, query, aggregation_model):
    prompt = f"""## Instruction:
{instruction}

## In order to evaluate a response to the above instruction, I looked up different expert advice on '{query}'. I found the following two responses:
### Expert Advice 1:

{summ1}

### Expert Advice 2:

{summ2}

## Your goal is to identify new information in Advice List 2 compared to Advice List 1. Once you have identified that information, integrate it in Advice List 1 and return a combined List. Do not delete anything from Advice 1.
Include any unique and nuanced details from Advice 2, eg: any thoughts on how the structure should be, tone etc. If there are examples of what phrasing etc to use please include them under any relevant points
You MUST NOT draw any inferences on your own. 
DO NOT answer the instruction. 
You only choose to merge or combine details as needed. 
"""
    return get_response(prompt = prompt, model_name = aggregation_model)


def summarize_all_query_outputs(summaries, instruction, query, aggregation_model):
    current_summary = summaries[0]
    # Iteratively summarize the list
    for i, next_summary in enumerate(summaries[1:]):
        print(i + 1)
        current_summary = summarize_two_query_summaries(current_summary, next_summary, instruction, query, aggregation_model)

    return current_summary

def query_focused_summary(article, query, instruction, answer_model):
    summarize_prompt = f"""### Article:
{article}
--------------
Answer the following question from the article above: '{query}'. 
The question is to help me write an answer to the following instruction: '{instruction}'
ONLY answer the question and not the instruction.
I am looking for nuanced advice to the question above, include any obscure or minutes points like structuring the content, the tone, highlighting important things etc. 
If the article does not have any useful advice, then return "no answer".
"""
    response = get_response(prompt=summarize_prompt, model_name=answer_model)
    print(response)
    if "no answer" in response.lower():
        return ""
    return response


def combine_two_query_lists(summ1, summ2, aggregation_model):
    prompt = f"""
## I found the following two responses:
### Advice list 1:
{summ1}

### Advice list 2:
{summ2}

## Add any new information and details from List 2 to List 1. Don't delete anything from List 1.
## Include any unique details from List 2, eg: any thoughts on how the structure should be, tone etc
## If there are examples, please include them under any relevant points
## Summarize the information into one list of points, each point should be unique and structured such that it reflects an evaluation criterion.
"""
    return get_response(prompt = prompt, model_name = aggregation_model)

def combine_query_lists(summaries, aggregation_model):
    current_summary = summaries[0]
    # Iteratively summarize the list
    for next_summary in summaries[1:]:
        current_summary = combine_two_query_lists(current_summary, next_summary, aggregation_model)

    return current_summary


def rewrite_web_llm_constraints(instruction, tips, aggregation_model):
    prompt = f"""### Instruction:
{instruction}

### Tips/Suggestions:
{tips}

----------------
Convert the tips to constraints/conditions so they can be used for evaluating a response to the given instruction. Eg: "the response should.." 
Checklist should:
- **Be answerable by ’yes’ or ’no’**, with ’yes’ meaning that the response successfully met the corresponding requirement.
- **Be comprehensive, but concise**, meaning that all criteria directly relevant to the INSTRUCTION should be represented by the checklist, but only criteria that are very clearly relevant should be included.
- **Be precise**, meaning that checklist should avoid vague wording and evaluate specific aspects of a response, directly using the phrasing of the INSTRUCTION where appropriate.

Give a new line separated numbered list, where each line is one constraint. Ensure they are rephrased to align with the instruction and starts with 'the response should..'
"""

    response = get_response(prompt=prompt, model_name =aggregation_model)
    return response

def check_constraints(instruction, criteria, aggregation_model):
    criteria = criteria.strip()
    prompt = f"""## Instruction:
{instruction}

## Criteria for evaluating a response to the above instruction:

{criteria}

---------------

For the above criteria, which of them can be used to evaluate a response to the instruction? 
Note: the response is not interactive, we cannot evaluate if the response went through iterative revisions and there is no feedback process. If there is any criteria evaluating for these, then mark them no.
Think step by step and give a response for each criteria point, end the reasoning with "therefore, the criteria applies yes" or "therefore, the criteria does not apply no".
Return a JSON where the key is the criteria number and the value is the reasoning for whether or not the criteria applies.
"""
    response = get_response(prompt = prompt, model_name = aggregation_model)
    try:
        if '```' in response:
            response = response.split("```")[1].replace("json", "").strip()
        response_json = ast.literal_eval(response)
        filtered_criteria = []
        split_criteria = criteria.split("\n")
        assert len(response_json) == len(split_criteria)
        for i, k in enumerate(response_json):
            reasoning = response_json[k].lower().split("therefore, the criteria")[1].strip()
            if 'yes' in reasoning:
                filtered_criteria.append(split_criteria[i])
            else:
                print(split_criteria[i])
        filtered_criteria = [f"{i + 1}." + remove_numbers_from_sentences(f) for i, f in enumerate(filtered_criteria)]
        print(f"Started with: {len(split_criteria)}, filtered down to: {len(filtered_criteria)}")
        filtered_criteria = "\n".join(filtered_criteria).strip()
        return filtered_criteria, response_json
    except Exception as e:
        print(e)
        return criteria, {}

def post_query_summarization_and_filtering(instruction, criteria, aggregation_model):
    rewritten_constriants = rewrite_web_llm_constraints(instruction=instruction,
                                tips=criteria,
                                aggregation_model=aggregation_model)
    filtered_criteria, filtering_output = check_constraints(instruction, rewritten_constriants, aggregation_model)
    filtered_criteria = "\n".join(list(filter(None, [f.strip() for f in filtered_criteria.split("\n")])))
    return {
        "criteria":filtered_criteria,
        "rewritten_criteria":rewritten_constriants,
        "filtering_criteria":filtering_output,
        "pre_filtering_criteria":rewritten_constriants,
    }