import json
import os
from typing import Dict, Any
import argparse
from utils import load_data, load_config
from criteria_generator import CriteriaGenerator, QueryGenerator
from score_and_merge import ScorerAndMerger


class EvaluationCriteriaGenerator:
    def __init__(self, config_path: str = "criteria_gen_args.yaml"):
        self.config = load_config(path=config_path)
        print(self.config)
        # input and output files
        self.input_file = self.config['input_file']
        self.output_file = self.config['output_file']
        # which mode -- llm criteria: yes or no | ea criteria: yes or no
        self.llm = self.config['llm']
        self.llm_n = self.config['n']
        self.ea = self.config['ea']
        # search or not
        self.search_enabled = self.config['search']
        # score or not
        self.score = self.config['score']
        self.query_model = self.config['query_model']
        self.aggregator_model = self.config['aggregator_model']
        self.answer_model = self.config['answer_model']
        self.scoring_model = self.config['scoring_model']
        # setup the functions for other generations
        self.query_generator = QueryGenerator(query_model=self.query_model)
        self.criteria_generator = CriteriaGenerator(
            answer_model=self.answer_model,
            aggregator_model=self.aggregator_model,
            search_enabled=self.search_enabled
        )
        self.score_merger = ScorerAndMerger(scoring_model=self.scoring_model)
        self._validate_environment()

    def _validate_environment(self):
        """Validate environment variables for search functionality"""
        if self.search_enabled:
            if 'GOOGLE_SEARCH_API_KEY' not in os.environ:
                raise ValueError("GOOGLE_SEARCH_API_KEY not found in environment variables")
            if 'CSE_ID' not in os.environ:
                raise ValueError("CSE_ID not found in environment variables")

    def get_ea_criteria(self, instruction: str, instance_data: Dict[str, Any]):
        queries = self.query_generator.generate_queries(instruction)
        print(f"Generated {len(queries)} queries")
        instance_data['queries'] = queries

        # Generate criteria
        criteria, search_results, search_success = self.criteria_generator.generate_criteria(
            instruction=instruction,
            queries=queries
        )

        if self.search_enabled:
            instance_data['search_results'] = search_results
            instance_data['search_success'] = search_success

        instance_data['query_responses'] = criteria

        # Aggregate and filter criteria
        aggregated_criteria = self.criteria_generator.aggregate_criteria(
            instruction=instruction,
            criteria=criteria
        )

        instance_data['ea_criteria'] = aggregated_criteria['criteria']
        instance_data['raw_ea_criteria'] = aggregated_criteria['raw_criteria']
        return instance_data

    def get_llm_criteria(self, instruction: str, instance_data: Dict[str, Any]):
        criteria = self.criteria_generator.get_llm_only_criteria(instruction = instruction,n_criteria=self.llm_n)
        instance_data['llm_criteria'] = criteria
        return instance_data

    def score_and_merge(self, instance_data: Dict[str, Any]):
        instruction = instance_data['instruction']
        ea_criteria = instance_data.get('ea_criteria', None)
        scored_ea_criteria = []
        if ea_criteria:
            print("Scoring EA Criteria..")
            scored_ea_criteria = self.score_merger.score_criteria(instruction=instruction,
                                                                  criteria_string=ea_criteria)
            instance_data['ea_criteria_scored_raw'] = [r for _,r,_ in scored_ea_criteria]
            instance_data['ea_criteria_scored'] = [s for _, _, s in scored_ea_criteria]

        llm_criteria = instance_data.get('llm_criteria', None)
        scored_llm_criteria = []
        if llm_criteria:
            print("Scoring LLM Criteria..")
            scored_llm_criteria = self.score_merger.score_criteria(instruction=instruction,
                                                                   criteria_string=llm_criteria)
            instance_data['llm_criteria_scored_raw'] = [r for _, r, _ in scored_llm_criteria]
            instance_data['llm_criteria_scored'] = [s for _, _, s in scored_llm_criteria]
        print("Merging Criteria..")
        merged_list, merged_source_indicators = self.score_merger.merge_criteria(instruction=instruction,
                                                                                 llm_criteria_list1=scored_llm_criteria,
                                                                                 ea_criteria_list2=scored_ea_criteria)
        instance_data['ea_full_criteria'] = merged_list
        instance_data['merged_source_indicators'] = merged_source_indicators
        return instance_data

    def process_instance(self, instance_data: Dict[str, Any]):
        instruction = instance_data["instruction"]
        if self.ea:
            print("Generating EA Criteria..")
            instance_data = self.get_ea_criteria(instruction=instruction, instance_data=instance_data)
        if self.llm:
            print("Generating LLM-n Criteria..")
            instance_data = self.get_llm_criteria(instruction=instruction, instance_data=instance_data)

        if self.score:
            print("Scoring and Merging Criteria..")
            instance_data = self.score_and_merge(instance_data=instance_data)
        return instance_data

    def process_data(self) -> Any:
        """Process input data and generate evaluation aspects"""
        input_data = load_data(self.input_file)
        print(f"Number of instances: {len(input_data)}")

        with open(self.output_file, "w") as output_file:
            for i, row in input_data.iterrows():
                print(f"Running instance {i}...")
                instance_data = row.to_dict()
                instance_data = self.process_instance(instance_data)
                # Write results to output file
                output_file.write(json.dumps(instance_data))
                output_file.write("\n")
                print("----")

        return input_data


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--config", type=str, default=None)
    arguments = arguments.parse_args()
    if not arguments.config:
        raise ValueError("Please provide a config file path")
    aspect_generator = EvaluationCriteriaGenerator(arguments.config)
    aspects = aspect_generator.process_data()
