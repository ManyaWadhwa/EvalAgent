import json
import os
import ast
from typing import Dict, List, Tuple, Optional, Any
from run_model import get_response
from get_search_results import get_search_criteria
from criteria_aggregation import combine_query_lists, post_query_summarization_and_filtering
from utils import edit_string_to_not_have_filler_text

class QueryGenerator:
    def __init__(self, query_model: str):
        self.query_model = query_model
        self.evaluation_query_prompt = """Instruction:
'{instruction}'

What should I google so I learn useful advice on writing a great response to the above instruction? Give a JSON response with three most important google queries as keys. The queries should be in the form  of "how to" or "what are" etc and the value is what we want to learn from the query. The queries should focus on seeking actionable writing advice instead of focusing on abstract knowledge concepts.  
"""

    def generate_queries(self, instruction: str) -> Dict[str, str]:
        """Generate search queries based on the instruction"""
        prompt_to_run = self.evaluation_query_prompt.format(instruction=instruction)
        response = get_response(model_name=self.query_model, prompt=prompt_to_run)

        if '```' in response:
            response = response.split("```")[1].replace("json", "").strip()

        try:
            queries = ast.literal_eval(response)
            return queries
        except Exception as e:
            raise ValueError(f"Failed to parse response as dictionary: {e}")


class CriteriaGenerator:
    def __init__(self, answer_model: str,
                 aggregator_model: str,
                 search_enabled: bool = False,
                 scoring_model: Optional[bool] = False):
        self.answer_model = answer_model
        self.aggregator_model = aggregator_model
        self.search_enabled = search_enabled

    def get_llm_only_criteria(self, instruction: str, n_criteria = 10) -> str:
        """Generate criteria directly from LLM responses"""
        prompt = f"""Help judge an AI assistant’s response to an instruction by providing an evaluation checklist.

    Instruction: '{instruction}'

    ## Task Details
    Your task is to come up with an evaluation checklist list for a given Instruction.
    This evaluation checklist should be a list of questions that ask whether or not specific criteria relevant to the INSTRUCTION were met by an AI assistant’s response.
    Criteria covered by your checklist could be explicitly stated in the INSTRUCTION, or be generally sensible criteria for the problem domain.
    You should, however, try to be concise and not include unnecessary entries in your checklist.
    Checklist should:
    - **Be answerable by ’yes’ or ’no’**, with ’yes’ meaning that the response successfully met the corresponding requirement.
    - **Be comprehensive, but concise**, meaning that all criteria directly relevant to the INSTRUCTION should be represented by the checklist, but only criteria that are very clearly relevant should be included.
    - **Be precise**, meaning that checklist should avoid vague wording and evaluate specific aspects of a response, directly using the phrasing of the INSTRUCTION where appropriate.

    Give a list where each line corresponds to one factor. The factors should start with 'the response should'. Return {n_criteria} factors.
    """
        criteria = get_response(prompt=prompt, model_name=self.answer_model)
        criteria = "\n".join(list(filter(None, [c.strip() for c in criteria.split("\n")])))
        return criteria

    def get_llm_query_criteria(self, queries: Dict[str, str]) -> Dict[str, str]:
        """Generate criteria directly from LLM responses"""
        llm_query_responses = {}
        for query in queries:
            query_prompt = f"{query}\n\nGive a list where each line corresponds to one point."
            response = get_response(prompt=query_prompt, model_name=self.answer_model)
            response = response.replace("**", "").strip()
            filtered_response = edit_string_to_not_have_filler_text(response)
            filtered_response = "\n".join(list(filter(None, [f.strip() for f in filtered_response.split("\n")])))
            llm_query_responses[query] = filtered_response
        return llm_query_responses

    def generate_criteria(self, instruction: str, queries: Dict[str, str]) -> Tuple[
        Dict[str, str], Dict[str, Any], bool]:
        """Generate criteria using either search or LLM"""
        search_results = {}
        search_success = False

        if self.search_enabled:
            # Run search
            print('Running search...')
            criteria, search_results, search_success = get_search_criteria(
                instruction=instruction,
                queries=queries,
                aggregation_model=self.aggregator_model,
                answer_model=self.answer_model
            )

        if not self.search_enabled or not search_success:
            print("Getting query responses from LLM...")
            criteria = self.get_llm_query_criteria(queries)

        return criteria, search_results, search_success

    def aggregate_criteria(self, instruction: str, criteria: Dict[str, str]) -> Dict[str, Any]:
        """Aggregate and filter criteria"""
        print("Aggregating criteria...")
        summaries = [criteria[q] for q in criteria]

        raw_combined_criteria = combine_query_lists(
            summaries=summaries,
            aggregation_model=self.aggregator_model
        )

        combined_criteria = post_query_summarization_and_filtering(
            instruction=instruction,
            criteria=raw_combined_criteria,
            aggregation_model=self.aggregator_model
        )

        result = {
            'criteria': combined_criteria['criteria'],
            'raw_criteria': {
                "pre_rewriting_criteria": raw_combined_criteria,
                "pre_filtering_criteria": combined_criteria['pre_filtering_criteria'],
                "filter_raw_response": combined_criteria['filtering_criteria'],
            }
        }

        return result
