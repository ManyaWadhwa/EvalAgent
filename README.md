# EvalAgent

EvalAgent is a framework designed to generate evaluation criteria from instructional web-documents. 

<img src="images/Eval_Agents_Overview.png" width="90%" height="75%">

## Overview 

We propose **EvalAgent**, aimed at extracting evaluation criteria from instructional web documents. Our framework comprises several key components. At a high level, given a user promopt, we first generate search queries that can be easily answered using instructional web documents. After retrieving such documents, we generate answers for the the search queries. We then combine these answers to define our evaluation criteria. 


## 🛠️ Installation 
To setup EvalAgent clone the repo and install the required dependencies 

`
pip install -r requirements.txt
`

Along with the environment setup we need to following to run EvalAgent:
1. Model API keys you want to use for running query generation, answering and criteria aggregation 
2. Search setup - for retrieving URLs

If you want to generate criteria _without_ searching, you can follow the setup under Direct LLM but if you are interested in running our search-based criteria generation follow the setup under Search based criteria. 


### Direct LLM  
If generating criteria without search, you only need to provide the API key for query generation and aggregation steps. In this case we use OpenAI but you can also provide Anthropic APIs / any models hosted on vLLM.

`
export OPENAI_API_KEY=<your OpenAI key here>
`

### Search

Export any LLM model API keys:

`
export OPENAI_API_KEY=<your OpenAI key here>
`

Our search is backed by Google Search API. The setup instructions can be found [here](https://github.com/ManyaWadhwa/EvalAgent/blob/main/google_setup.md). 

An alternate to Google API is to user [Serper](https://serper.dev/).

[optional setup] 
Reddit has a lot of instructional posts, so we use `praw` to scrap we also set up reddit scraping. You can find the setup instructions [here](https://github.com/ManyaWadhwa/EvalAgent/blob/main/reddit_setup.md). This setup is optional, if the environment variables are not setup you won't get an error, we just won't include that URL.

## Running EvalAgent

Once you have gone through the setup above make sure you have the following variables populated in `environment_variables.sh`
```
## OpenAI if you using their models; else set up anthropic keys if needed
export OPENAI_API_KEY=
## Google search credentials 
export GOOGLE_SEARCH_API_KEY=
export CSE_ID=
## OPTIONAL reddit credentials
export reddit_client_id=
export reddit_client_secret=
export reddit_user_agent=
export reddit_username=
export reddit_password=
```

To run non-search based criteria generation you can run the following: 

```
python get_aspects.py --input_file sample_data.jsonl --output_file sample_data_criteria.jsonl --query_generator <model_name> --answer_model <model_name> --aggregator_model <model_name>
```

To run search based criteria generation you can run the following:
```
python get_aspects.py --input_file sample_data.jsonl --output_file sample_data_criteria.jsonl --query_generator <model_name> --answer_model <model_name> --aggregator_model <model_name> --search
```

By default <model_name> is setup to be: ```gpt-4o-mini-2024-07-18```

## Visualization 

We also have a flask-based UI where you can load the jsonl output from the search-based criteria generation.