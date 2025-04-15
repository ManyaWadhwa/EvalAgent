import requests
import os
from bs4 import BeautifulSoup
import praw
import pandas
import json
import re

from criteria_aggregation import query_focused_summary, summarize_all_query_outputs
from run_model import get_response
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


def get_google_search_list(google_response):
    response_data = []
    for i, item in enumerate(google_response.get("items", []), start=1):
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet")
        print(f"{i}. {title}\nURL: {link}\nSnippet: {snippet}\n")
        response_data.append({
            "name": title,
            "url": link,
            "snippet": snippet
        })
    return response_data

def google_search(query, api_key, cse_id, num_results, start):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": api_key,
        "cx": cse_id,
        "num": num_results,  # Number of results you want to retrieve,
        "start": start
    }
    response = requests.get(url, params=params)
    response = response.json()
    response_data = get_google_search_list(response)
    return response_data

def google_search_n(query, api_key, cse_id, num_results=5):
    counts = int(num_results / 10)
    start = 1
    results = []
    for i in range(counts):
        print("Iteration: ", i)
        search = google_search(query, api_key, cse_id, 10, start)
        results.extend(search)
        start += 10
    remaining = num_results - len(results)
    if remaining > 0:
        search = google_search(query, api_key, cse_id, remaining, start)
        results.extend(search)
    return results

def get_reddit_data(url, top=10):
    if 'reddit_client_id' in os.environ:
        client_id = os.environ['reddit_client_id']
        client_secret = os.environ['reddit_client_secret']
        user_agent = os.environ['reddit_user_agent']
        reddit = praw.Reddit(client_id=client_id,
                         client_secret=client_secret,
                         user_agent=user_agent)
    else:
        reddit = None
    if not reddit:
        return ""

    submission = reddit.submission(url=url)
    top_comments = []
    for top_comment in submission.comments[:top]:
        if isinstance(top_comment, praw.models.Comment):
            top_comments.append(top_comment.body)

    selected_top_comments = []
    count = 0
    for i, comment in enumerate(top_comments, start=1):
        if comment not in ['[removed]', '[deleted]']:
            selected_top_comments.append(f"Response {count + 1}:\n {comment}\n---\n")
            count += 1
    print(len(selected_top_comments))
    return "\n".join(selected_top_comments)

def get_website_content(url):
    # Send a GET request
    try:
        print("Reading: ", url)
        if "reddit" in url:
            print("Getting reddit data...")
            content = get_reddit_data(url)
            return content
        else:
            response = requests.get(url, timeout=40)
            print(response.status_code)
            # Check if request was successful
            if response.status_code == 200:
                # Parse content
                soup = BeautifulSoup(response.content, "html.parser")
                # Find headings and paragraphs in order
                raw_content = []
                for elem in soup.find_all(['h1', 'h2', 'h3', 'p','li']):
                    raw_content.append(elem.get_text().strip())
                seen = set()
                content = []
                for item in raw_content:
                    if item not in seen:
                        seen.add(item)
                        content.append(item)
                # Optional: Filter out very short or noisy lines

                def clean_text(text):
                    text = re.sub(r'\s+', ' ', text)  # collapse multiple spaces/newlines
                    text = re.sub(r'[\u200b\u200e\u202a-\u202e]', '', text)  # remove invisible/control chars
                    text = re.sub(r'\xa0', ' ', text)  # replace non-breaking space
                    text = re.sub(r'�', '', text)  # remove replacement characters
                    return text.strip()

                content = [clean_text(line) for line in content]

                # Optional: filter noise (same as before)
                content = [
                    line for line in content
                    if len(line.split()) > 3 and not any(noise in line.lower() for noise in [
                        'cookie', 'accept', 'subscribe', 'sign up', 'advertisement',
                        'privacy policy', 'terms of service', 'share this', 'read more'
                    ])
                ]
                # content = list(set(content))
                return "\n".join(content)
            else:
                return ""
    except Exception as e:
        print(e)
        return ""


def url_filter(instruction, url, title, content, aggregator_model):
    ## regex filtering
    if re.search(r'\d+', title) or re.search(r'\d+', url):
        return 0
    if "ultimate" in title.lower() or 'best' in title.lower():
        return 0
    ## GPT prompting
    prompt = f""" ## URL: {url}

## Title: {title}

## Article:
{content}

-------------------------------------------------------------
Does the web content provide any advice that will help me write a response to the following instruction: 
Instruction: "{instruction}"

2 - yes and it provides specific advice that will help me write a response to the instruction  
1 - yes but it only provides general advice that will help me write a response to the instruction
0 - no, it doesn't help at all 

Only give the numerical response and description.
"""
    response = get_response(prompt=prompt, model_name=aggregator_model)
    response = response.split("-")[0].strip()
    try:
        return int(response)
    except:
        print(response)
        print("Cannot convert to int for some reason!!")
    return 0

def search_only_rating(url, content, aggregator_model):
    criteria = """Score: 1 - Very Poor
Expertise: Content appears unprofessional or amateurish, with little evidence of expertise.
Reliability: The domain is untrustworthy or unknown, such as suspicious .com sites, clickbait domains, or personal blogs with no credentials.
Clarity: Information is vague, confusing, or contradictory, with no actionable advice.
Marketing: The content is overtly promotional, focused primarily on selling a product or service rather than providing useful information.

Score: 2 - Poor
Expertise: Some effort to appear knowledgeable, but lacks depth or substantiation (e.g., no citations, shallow explanations).
Reliability: Domain is not widely recognized, or the platform has a mixed reputation.
Clarity: Advice is somewhat unclear or too generic to be useful.
Marketing: There is a noticeable marketing agenda, but it does not entirely overshadow the content.

Score: 3 - Fair
Expertise: Content demonstrates moderate expertise, though it may lack nuance or depth. Basic credibility is evident.
Reliability: The domain is moderately reputable (e.g., a well-known .com site, or an .org/.edu/.gov site with minor credibility concerns).
Clarity: Information is reasonably clear and somewhat actionable, though not highly detailed or specific.
Marketing: Some promotional elements are present but do not dominate the content.

Score: 4 - Good
Expertise: Content is well-researched and written by someone with clear expertise or authority in the field.
Reliability: The domain is highly reputable, such as a trusted .edu, .gov, or widely respected .com/.org site.
Clarity: Advice is clear, specific, and actionable, with practical steps or examples.
Marketing: Minimal promotional content; the focus is on providing value to the reader.

Score: 5 - Excellent
Expertise: Content reflects deep expertise, with authoritative writing, detailed explanations, and citations or references to credible sources.
Reliability: The domain is extremely trustworthy, such as a government, academic, or highly esteemed organization.
Clarity: Advice is exceptionally clear, highly specific, and immediately actionable, tailored to the reader’s needs.
Marketing: No marketing agenda is evident, or if present, it is subtle and does not detract from the quality of the information.
"""

    prompt = f"""URL: {url}

Content in the URL: 
{content}

#####
Rate the goodness of the above URL and content based on the following criteria:
{criteria}

Only return the score number at the end.
"""
    response = get_response(prompt = prompt, model_name=aggregator_model)
    try:
        return int(response)
    except:
        print(response)
        return 0

def web_search_filtering(instruction, web_search_results, aggregator_model):
    for instance in web_search_results:
        instance['content'] = instance['content'].strip()
        if len(instance['content']) == 0:
            instance['link_instruction_rating'] = 0
            instance['link_rating'] = 0
            instance['keep'] = False
        else:
            link_instruction_rating = url_filter(instruction=instruction,
                          url = instance['url'],
                          title=instance['name'],
                          content=instance['content'],
                          aggregator_model=aggregator_model)
            instance['link_instruction_rating'] = link_instruction_rating

            link_rating = search_only_rating(instance['url'], instance['content'], aggregator_model)
            instance['link_rating'] = link_rating
            keep = False
            if link_instruction_rating > 0 and link_rating > 2: #
                keep = True
            instance['keep'] = keep

    web_search_results_pd = pandas.DataFrame(web_search_results)
    web_search_results_pd = web_search_results_pd.sort_values(['link_instruction_rating','link_rating'],ascending=False)
    filtered_results = json.loads(web_search_results_pd.to_json(orient='records'))
    return filtered_results

def get_search(instruction, query, aggregation_model, num_results = 5):
    # num_results = num_results * 3  ## so there are three chances of extracting information
    search_id = os.environ['GOOGLE_SEARCH_API_KEY']
    cse_id = os.environ['CSE_ID']
    print('search_id: ', search_id)
    web_results = google_search_n(query=query,
                                  api_key= search_id,
                                  cse_id= cse_id,
                                  num_results= 30) ## overgenerate results
    # get website content and for any website that doesn't get scraped, we can discard the URL.
    valid_web_results = []
    for r in web_results:
        content = get_website_content(r['url']).strip()
        # if len(content)==0:
        #     continue
        r['content'] = content.strip()
        valid_web_results.append(r)
    content = [r['content'] for r in valid_web_results]
    print("Num valid results out of 30 retrieved: ", len(content))
    web_results = web_search_filtering(instruction, valid_web_results, aggregation_model)
    filtered_web_results = [r for r in web_results if r['keep']][:num_results]
    content = [r['content'] for r in filtered_web_results]
    # content = [r['content'] for r in web_results if r['keep']][:num_results] ## keeping only a subset of all the valid ones in case they are better!
    print("Post filtering number of results: ", len(content))
    return content, filtered_web_results, web_results

def get_search_criteria(instruction, queries, aggregation_model, answer_model, num_results=5):
    search_results = {}
    for query in queries:
        web_content, filtered_web_results, all_web_results = get_search(instruction= instruction,
                                                                    query = query,
                                                                    aggregation_model = aggregation_model,
                                                                    num_results=num_results)
        search_results[query] = {
            "selected_web_content":web_content,
            "filtered_web_results":filtered_web_results,
            "all_web_results":all_web_results,
        }

    for query in search_results:
        assert len(search_results[query]['selected_web_content'])==len(search_results[query]['filtered_web_results'])
        selected_content = search_results[query]['selected_web_content']
        selected_content_answers = []
        filtered_web_results = search_results[query]['filtered_web_results']
        for i, web_result in enumerate(filtered_web_results):
            c = web_result['content']
            if len(c)==0:
                continue
            summary = query_focused_summary(article = c,
                                            query = query,
                                            instruction = instruction,
                                            answer_model = answer_model)
            summary = summary.strip()
            web_result['query_answer'] = summary
            search_results[query]['filtered_web_results'][i] = web_result
            selected_content_answers.append(summary)
        search_results[query]["selected_content_answers"] = selected_content_answers

    query_specific_criteria = {}
    for query in search_results:
        filtered_web_results = search_results[query]['filtered_web_results']
        assert len(filtered_web_results)==len(search_results[query]['selected_content_answers'])
        selected_content_answers = [f['query_answer'] for f in filtered_web_results]
        selected_content_answers = list(filter(None, selected_content_answers))
        if len(selected_content_answers)==0:
            query_summary = ""
        else:
            query_summary = summarize_all_query_outputs(summaries = selected_content_answers,
                                                    instruction = instruction,
                                                    query = query,
                                                    aggregation_model =  aggregation_model)
            query_specific_criteria[query] = query_summary

    if len(query_specific_criteria)==0:
        valid  = False
    else:
        valid = True
    # valid = False
    # if any([query_specific_criteria[q] for q in query_specific_criteria]):
    #     valid = True
    return query_specific_criteria, search_results, valid