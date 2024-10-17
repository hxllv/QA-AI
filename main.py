import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import openai
import tempfile
import json

# Tvoji podatki
email = 'xxx'
api_token = 'xxx'
base_url = 'https://celtra.atlassian.net/wiki/rest/api/'
openai.api_key = 'xxx'  # Tukaj vstavi svoj OpenAI API ključ

# Pridobi seznam strani, ki imajo "Test spec", "Product spec" ali "Tech spec" v naslovu
def get_pages_with_specs():
    cql_query = 'title~"spec" OR text~"Problem Discovery and Product Development"'
    search_url = f'{base_url}content/search?cql={cql_query}'
    response = requests.get(search_url, auth=HTTPBasicAuth(email, api_token), headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        data = response.json()
        return data['results']  # Vrne seznam strani
    else:
        print(f"Napaka pri iskanju strani: {response.status_code}")
        return []

# Pridobi vsebino posamezne strani in odstrani HTML oznake
def get_page_content(page_id):
    url = f'{base_url}content/{page_id}?expand=body.storage'
    response = requests.get(url, auth=HTTPBasicAuth(email, api_token), headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        data = response.json()
        html_content = data['body']['storage']['value']
        
        # Uporabi BeautifulSoup za odstranjevanje HTML oznak in pridobitev čistega besedila
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator="\n")  # Pridobi samo besedilo
    else:
        print(f"Napaka pri pridobivanju strani {page_id}: {response.status_code}")
        return None

# Pridobi vse strani z naslovom, ki vsebuje "Test spec", "Product spec" ali "Tech spec"
pages = get_pages_with_specs()
specs = []

for page in pages:
    page_id = page['id']
    title = page['title']
    content = f"""Vsebina strani: {title}
    {get_page_content(page_id)}
    \n\n-------------------------\n\n"""
    
    specs.append(content)

f = open("specs.txt", "fw")
f.write(''.join(specs))
f.close()

assistant = openai.beta.assistants.create(
    name="Nace's stupid test spec assistant",
    instructions="""
    You generate test specs based on a given product spec and/or tech spec. 
    Use the attached file to generate the correct format of test spec. 
    That means potential E2E tests, testing scope, security testing and performance testing.
    """,
    model="gpt-4o",
    tools=[{"type": "file_search"}],
)

# Create a vector store caled "Financial Statements"
vector_store = openai.beta.vector_stores.create(name="")
 
# Ready the files for upload to OpenAI
file_streams = [open("specs.txt", 'rb')]
 
# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
file_batch = openai.beta.vector_stores.file_batches.upload_and_poll(
  vector_store_id=vector_store.id, files=file_streams
)

assistant = openai.beta.assistants.update(
  assistant_id=assistant.id,
  tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
)

new_spec = get_page_content(817234085)

tp1 = tempfile.NamedTemporaryFile(suffix='.txt')
tp1.write(bytes(new_spec, 'utf-8'))
tp1.flush()

# Upload the user provided file to OpenAI
message_file = openai.files.create(
  file=open(tp1.name, "rb"), purpose="assistants"
)
 
# Create a thread and attach the file to the message
thread = openai.beta.threads.create(
  messages=[
    {
      "role": "user",
      "content": "hello.",
    }
  ]
)
 
# The thread now has a vector store with that file in its tool resources.

# Use the create and poll SDK helper to create a run and poll the status of
# the run until it's in a terminal state.

run = openai.beta.threads.runs.create_and_poll(
    thread_id=thread.id, assistant_id=assistant.id
)

messages = list(openai.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

message_content = messages[0].content[0].text
annotations = message_content.annotations
citations = []
for index, annotation in enumerate(annotations):
    message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
    if file_citation := getattr(annotation, "file_citation", None):
        cited_file = openai.files.retrieve(file_citation.file_id)
        citations.append(f"[{index}] {cited_file.filename}")

print(message_content.value)
print("\n".join(citations))