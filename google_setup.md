To set up a custom Google Search API and obtain an API key and CSE (Custom Search Engine) ID, follow these steps:

### Step 1: Set Up Google Cloud Project
1. **Create a Google Cloud account**:  
   If you haven't already, sign up for a Google Cloud account at [https://cloud.google.com](https://cloud.google.com).
   
2. **Create a new project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - On the left sidebar, click on **Select a project**.
   - Click on **New Project** and give it a name. Click **Create**.

3. **Enable Custom Search API**:
   - In the Google Cloud Console, go to the **API & Services** section.
   - Click on **Library**.
   - Search for **Custom Search API** and click on it.
   - Click **Enable** to activate the API for your project.

### Step 2: Obtain an API Key
1. **Go to the Credentials page**:
   - In the Google Cloud Console, click on the **API & Services** section in the left sidebar.
   - Click **Credentials**.

2. **Create API key**:
   - On the Credentials page, click on **Create credentials**.
   - Select **API key** from the dropdown.
   - An API key will be generated. Copy it and add to your `environment_variables.sh`.
   
   **Note**: You can restrict the API key by clicking on the "Restrict Key" button to limit usage to specific IPs or referrers.

### Step 3: Create a Custom Search Engine (CSE)
1. **Go to the Custom Search Engine page**:
   - Open a new tab and go to [https://cse.google.com](https://cse.google.com).
   - Sign in with your Google account.

2. **Create a new Custom Search Engine**:
   - Click on **Add** to create a new search engine.
   - In the form just select `Search the entire web`. Image Search and SafeSearch can be off depending on your requirements.
   - Click **Create**.

3. **Get your CSE ID**:
   - Once the CSE is created, click on the **Control Panel** of your Custom Search Engine.
   - On the left, find the **Details** section.
   - Your **Search Engine ID** (CSE ID) will be listed here. Copy it and add to your `environment_variables.sh`.

### [OPTIONAL TO TEST IF THE API KEY WORKS] Step 4: Using the Custom Search API
- Now that you have both the **API key** and **CSE ID**, you can use them to make requests to the Custom Search API.

To test, here’s an example of how to make a search request using Python:

```python
import requests

api_key = 'YOUR_API_KEY'  # Replace with your API key
cse_id = 'YOUR_CSE_ID'  # Replace with your CSE ID
query = 'search term'  # Replace with your search term

url = f'https://www.googleapis.com/customsearch/v1?q={query}&key={api_key}&cx={cse_id}'

response = requests.get(url)
data = response.json()

for item in data['items']:
    print(item['title'], item['link'])
```

If the above steps work you can now start using it to programmatically retrieve search results.