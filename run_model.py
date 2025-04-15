from litellm import completion

def get_response(model_name, prompt, system_prompt = None):
    if system_prompt:
        messages = [{"content": system_prompt, "role": "system"},
                    {"content": prompt, "role": "user"}]
    else:
        messages = [{"content": prompt, "role": "user"}]

    try:
        response = completion(model=model_name, messages=messages)
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(e)
        return ""

