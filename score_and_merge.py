from run_model import get_response
from typing import Dict, List, Tuple, Optional, Any
import json
from collections import Counter
from ui.app import remove_numbers_from_sentences


class ScorerAndMerger:
    """
    Class for scoring criteria relevance and merging/deduplicating criteria
    """

    def __init__(self, scoring_model: str):
        self.scoring_model = scoring_model
        self.scoring_prompt_template = """How relevant is the following aspect to evaluating a text only response to the following instruction? Note, that we cannot use these for evaluating iterative editing etc. so any aspect which mentions that should be rated low.

Aspect: "{criteria}"
Instruction: "{instruction}"

Think about it step by step and return a number between 0 and 10. End your response with 'therefore, the score is:'. 
0 is the lowest relevance and 10 is the most relevant/useful aspect. 
"""
    def score_criteria(self, instruction: str, criteria_string: str) -> List[Tuple[str, str, float]]:
        """
        Score each criteria item for relevance to the instruction
        Returns list of (criteria, score) tuples
        """
        scored_criteria = []
        criteria_list = list(filter(None, [remove_numbers_from_sentences(c.strip()) for c in criteria_string.split("\n")]))
        print(f"Number of criteria: {len(criteria_list)}")
        for i, criteria in enumerate(criteria_list):
            prompt = self.scoring_prompt_template.format(
                instruction=instruction,
                criteria=criteria
            )

            response = get_response(model_name=self.scoring_model, prompt=prompt)
            # Extract the numeric score from the response
            try:
                # Try to find a number in the response
                score_text = response.lower().split("therefore, the score is")[-1].strip().replace(":", "").replace(".", "").replace("*","").strip()
                score = float(score_text)
                if 1 <= score <= 10:
                    score = score
                else:
                    score = 0.0
            except Exception as e:
                print(e)
                score = 0.0
            scored_criteria.append((criteria, response, score))
        print([s for _, _, s in scored_criteria])
        return scored_criteria

    def deduplicate_criteria(self, scored_criteria: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """
        Remove duplicate or very similar criteria, keeping the higher-scored version
        """
        # Create a prompt to find duplicates
        if len(scored_criteria) <= 1:
            return scored_criteria

        dedup_prompt = """
I have the following criteria items. Identify any duplicates or very similar items and return a JSON dictionary where the keys are the indices of items to keep, and values are lists of indices that are duplicates or very similar to the key.
Only include indices in the output if they are part of a duplicate group. Keep the order of the keys same as the original criteria list.

Criteria:
"""

        for i, (criteria, _) in enumerate(scored_criteria):
            dedup_prompt += f"{i + 1}. {criteria}\n"

        dedup_prompt += "\nOutput the duplicate groups as a JSON dictionary. For example: {\"1\": [4, 7], \"2\": [5, 8]}"

        response = get_response(model_name=self.scoring_model, prompt=dedup_prompt)

        # Extract JSON dictionary from response
        try:
            # Try to find JSON in the response
            if '```' in response:
                json_text = response.split('```')[1]
                if json_text.startswith('json'):
                    json_text = json_text[4:].strip()
            else:
                json_text = response.strip()

            duplicate_groups = json.loads(json_text)

            # Convert string keys to integers
            duplicate_groups = {int(k) - 1: [int(idx) - 1 for idx in v] for k, v in duplicate_groups.items()}

            # Create a set of indices to remove
            indices_to_remove = set()
            for keep_idx, remove_indices in duplicate_groups.items():
                indices_to_remove.update(remove_indices)

            # Create deduplicated list
            deduplicated = [scored_criteria[i] for i in range(len(scored_criteria)) if i not in indices_to_remove]
            return deduplicated

        except Exception as e:
            print(f"Error deduplicating criteria: {e}")
            # If there's an error, return the original list
            return scored_criteria

    def merge_criteria(self, instruction: str,
                       llm_criteria_list1: List[Tuple[str, str, float]],
                       ea_criteria_list2: List[Tuple[str, str, float]],
                       max_criteria: int = None) -> Tuple[List[str], List[int]]:
        """
        Merge two lists of scored criteria and sort by decreasing score values.

        Args:
            instruction: The instruction text
            llm_criteria_list1: First list of (criteria, score) tuples
            ea_criteria_list2: Second list of (criteria, score) tuples
            max_criteria: Maximum number of criteria to include in final result

        Returns:
            Tuple of (merged_criteria_list, source_indicators) where:
            - merged_criteria_list is a list of criteria strings
            - source_indicators is a list of integers (1 for list1, 2 for list2)
        """
        # Create combined list with source tracking
        combined_criteria = []

        # Add criteria from list 1 with source=1
        for criteria, _, score in llm_criteria_list1:
            combined_criteria.append((criteria, score, 'llm'))

        # Add criteria from list 2 with source=2
        for criteria, _, score in ea_criteria_list2:
            combined_criteria.append((criteria, score, 'ea'))

        # Sort by score in descending order
        combined_criteria.sort(key=lambda x: x[1], reverse=True)


        if max_criteria:
            # Limit to max_criteria
            criteria = combined_criteria[:max_criteria]
        else:
            criteria = combined_criteria
        # Extract criteria and sources for return
        merged_criteria_list = [criteria for criteria, _, _ in criteria]
        source_indicators = [source for _, _, source in criteria]
        print(Counter(source_indicators))
        merged_criteria = "\n".join([f"{i+1}. {m}" for i, m in enumerate(merged_criteria_list)])
        return merged_criteria, source_indicators