import json
import argparse
from typing import Dict, List, Any, Optional, Union, Tuple

from run_model import get_response
from utils import load_data, load_config
from evaluation_criteria_generator import EvaluationCriteriaGenerator


class Evaluator:
    """
    Class for evaluating responses against generated criteria
    Supports both pointwise (single response) and pairwise (two response) evaluation
    """

    def __init__(self, config_path: str = "evaluation_args.yaml"):
        # Load configuration
        self.config = load_config(path=config_path)
        self.input_file = self.config['input_file']
        self.output_file = self.config['output_file']
        self.evaluation_model = self.config['evaluation_model']
        self.generate_criteria = self.config['generate_criteria']
        self.criteria_column = self.config['criteria_column']
        self.criteria_generator_config = self.config.get('criteria_generator_config', None)

        # Initialize aspect generator
        self.aspect_generator = EvaluationCriteriaGenerator(config_path=self.criteria_generator_config)

        # Evaluation prompts
        self.system_prompt = "You are a teacher, evaluate a student's response to an instruction."
        self.pointwise_prompt_template = """A student is given the following instruction to answer:
{instruction}

Student's response:
{response}

-------------------------------------------
Does the response satisfy the following criteria:
{criteria}

Think step by step and end your thought with "therefore, the answer is yes" or "therefore, the answer is no". 
"""

    def get_criteria(self, instance_data: Dict[str, Any]) -> str:
        """Generate evaluation criteria for an instruction"""

        # Process the instance to generate criteria
        processed_data = self.aspect_generator.process_instance(instance_data=instance_data)
        # Extract the generated criteria
        criteria = processed_data.get(self.criteria_column,'')
        criteria_list = criteria.split('\n')
        print(f"Generated {len(criteria_list)} criteria points.")
        return criteria_list

    def _parse_pointwise_score(self, raw_response: str) -> int:
        raw_response = raw_response.lower().strip()
        parsed_response = 0
        if raw_response.lower() == "na":
            parsed_response = None
        elif "therefore, the answer is" in raw_response.lower():
            split = raw_response.lower().split("therefore, the answer is")[1]
            if "yes" in split:
                parsed_response = 1
            elif "no" in split:
                parsed_response = 0
        return parsed_response

    def evaluate_pointwise(self, instance_data, criteria: Optional[str] = None) -> Dict[str, Any]:
        # Generate criteria if not provided
        if criteria is None:
            print("Generating criteria...")
            criteria = self.get_criteria(instance_data)

        instruction = instance_data.get('instruction', None)
        response = instance_data.get('response', None)

        if instruction is None or response is None:
            print("Instruction and response are required for point wise evaluation.. skipping this instance")
            instance_data['satisfied_rate'] = 0.0
            instance_data['criteria_evaluation'] = {}
            return instance_data

        # Create evaluation prompt
        evaluation_response = {}
        satisfied_criteria = []
        for i, c in enumerate(criteria):
            print(i)
            prompt = self.pointwise_prompt_template.format(
                instruction=instruction,
                criteria=c,
                response=response
            )
            # Get evaluation from model
            evaluation = get_response(model_name=self.evaluation_model, prompt=prompt, system_prompt=self.system_prompt)
            parsed_response = self._parse_pointwise_score(evaluation)
            satisfied_criteria.append(parsed_response)

            evaluation_response[c] = {"raw": evaluation, "parsed": parsed_response}

        # Add metadata
        instance_data['criteria'] = criteria
        instance_data['satisfied_rate'] = sum(satisfied_criteria) / len(satisfied_criteria) if len(
            satisfied_criteria) > 0 else 0.0
        instance_data['criteria_evaluation'] = evaluation_response

        return instance_data

    def evaluate_instance(self, instance: Dict) -> Dict:
        """
        Evaluate a single instance from the data
        """
        # Generate criteria
        if self.generate_criteria:
            print("Generating criteria...")
            criteria = self.get_criteria(instance)
        elif self.criteria_column in instance:
            print("Using criteria from instance...")
            criteria = instance[self.criteria_column]
            if isinstance(criteria, str):
                criteria = list(filter(None, [c for c in criteria.split('\n')]))
        else:
            raise ValueError(
                "Criteria column not found in instance OR generate_criteria is set to False. Please provide criteria in the instance or set generate_criteria to True in the config file.")

        print(f"Evaluating instance with {len(criteria)} criteria points.")
        instance = self.evaluate_pointwise(instance_data=instance, criteria=criteria)
        print("Instance satisfies: ", instance['satisfied_rate'] * 100, "%")

        return instance

    def run_evaluation(self) -> None:
        """
        Run evaluation on all instances in the input file
        """
        # Load input data
        input_data = load_data(self.input_file)

        print(f"Evaluating {len(input_data)} instances...")

        # Process each instance
        with open(self.output_file, 'w') as f:
            for i, row in input_data.iterrows():
                print(f"Evaluating instance {i}...")
                instance = row.to_dict()
                # Evaluate the instance
                instance = self.evaluate_instance(instance)
                # Write results to output file
                f.write(json.dumps(instance) + '\n')
            print(f"Finished instance {i}")
            print("----")

if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--config", type=str, default=None)
    arguments = arguments.parse_args()
    if not arguments.config:
        raise ValueError("Please provide a config file path")

    evaluator = Evaluator(arguments.config)
    print(evaluator.config)
    evaluator.run_evaluation()
    print(f"Evaluation complete. Results written to {evaluator.output_file}")
