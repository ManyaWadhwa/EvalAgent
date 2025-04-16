# EvalAgent

EvalAgent is a framework designed to generate evaluation criteria from instructional web-documents. 

![Overview of our proposed pipeline](/images/Eval_Agents_Overview.pdf)

## Overview 

## Installation 
To setup EvalAgent clone the repo and install the required dependencies 

`
pip install -r requirements.txt
`

You can run EvalAgent in two setups:
1. LLM only 
2. Search-driven results 

## Direct LLM results 

`
export OPENAI_API_KEY=<your OpenAI key here>
`

`
python get_aspects.py --input_file sample_data.jsonl --output_file sample_data_criteria.jsonl --model_name_for_query gpt-4o-mini --model_name_for_aggre
`

## Search driven results



