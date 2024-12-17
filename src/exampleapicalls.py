# Anthropic Claude with web access and unrestricted Python execution

# TODO: trim front of context if it gets too big
#       context-free self-critique to validate any citations with web search/browsing
#       get images (and files in general?) back from code execution somehow
#       comment and clean up
#       persist python environment and interpreter state across execution tool calls
#       OpenRouter?

import streamlit as st # type: ignore
import anthropic # type: ignore

import requests # type: ignore
import urllib.parse
from bs4 import BeautifulSoup # type: ignore
import os
import subprocess
import sys
import tempfile

# Header information
st.title("Anthropic Claude with web access and unrestricted Python execution")
st.markdown("Chat with the Claude 3 API with tool use for "
            "DuckDuckGo web search, webpage content extraction, "
            "and Python code execution with automatic module "
            "installation and full Python execution.")

# API Key handling
if "api_key" not in st.session_state:
  st.session_state.api_key = os.environ.get("ANTHROPIC_API_KEY")

if not st.session_state.api_key:
  api_key = st.text_input("Enter your Anthropic API key:", type="password")
  if api_key:
    st.session_state.api_key = api_key
  else:
    st.warning("Please enter an API key to continue.")
    st.stop()

# Initialize the Anthropic client
client = anthropic.Anthropic(api_key=st.session_state.api_key)

# Model selection and configuration section
col1, col2, col3 = st.columns([1, 2, 2])
with col1:
  st.write("Model:")
with col2:
  model_choice = st.selectbox(
    "Model",
    [
      "claude-3-5-sonnet-latest",
      "claude-3-haiku-20240307",
      "claude-3-opus-latest",
      "Other (specify →)"
    ],
    key="model_choice", label_visibility="collapsed",
  )
with col3:
  custom_model = st.text_input(
    "Custom model name",
    value=st.session_state.get("custom_model", "claude-3-5-haiku-latest"),
    disabled=(model_choice != "Other (specify →)"),
    key="custom_model", label_visibility="collapsed"
  )
# Set the model to be used in API calls
model = custom_model if model_choice == "Other (specify →)" else model_choice

# Define the tools schema
tools = [{
    "name": "web_search",
    "description": "Search the web using DuckDuckGo",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to send to DuckDuckGo"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }
}, {
    "name": "read_webpage",
    "description": "Read and extract text content from a webpage",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to read"
            }
        },
        "required": ["url"]
    }
}, {
    "name": "execute_code",
    "description":
    "Execute Python code in a local virtual environment sandbox",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute"
            }
        },
        "required": ["code"]
    }
}]

def search_duckduckgo(query: str, num_results: int = 5) -> list:
  """Search DuckDuckGo and return results with clean, decoded URLs."""
  encoded_query = urllib.parse.quote(query)
  url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
  headers = {
      'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  }

  response = requests.get(url, headers=headers)
  soup = BeautifulSoup(response.text, 'html.parser')

  results = []
  for result in soup.find_all('div', class_='result')[:num_results]:
    title_elem = result.find('a', class_='result__a')
    link = title_elem.get('href') if title_elem else None
    title = title_elem.text if title_elem else None
    snippet = result.find('a', class_='result__snippet')
    description = snippet.text if snippet else None

    if title and link:
      # Decode the DuckDuckGo redirect URL
      if 'duckduckgo.com/l/?uddg=' in link:
        # Extract the encoded URL and decode it
        canonical_url = urllib.parse.unquote(link.split('uddg=')[1])
        # Remove the DuckDuckGo tracking parameter
        if '&rut=' in canonical_url:
          canonical_url = canonical_url.split('&rut=')[0]
      else:
        canonical_url = link

      results.append({
          "title": title,
          "url": canonical_url,
          "description": description
      })

  return results

def read_webpage(url: str) -> str:
  """Read and extract text content from a webpage."""
  try:
    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "header", "footer"]):
      element.decompose()

    # Get text and maintain links with their href URLs
    for a_tag in soup.find_all('a'):
      href = a_tag.get('href')
      if href:
        a_tag.replace_with(f"[ {a_tag.text} ]( {href} )")

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)

    return text[:300000]  # Truncate to avoid token limits
  except Exception as e:
    return f"Error reading webpage: {str(e)}"

def execute_code(code: str) -> str:
  """Execute Python code in a local virtual environment sandbox."""
  try:
    with tempfile.TemporaryDirectory() as temp_dir:
      logs = []

      # Set up a virtual environment in the temporary directory
      venv_dir = os.path.join(temp_dir, "venv")
      subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
      logs.append("Virtual environment set up.")

      # Path to the Python executable and pip in the virtual environment
      python_executable = os.path.join(venv_dir, "bin", "python")
      pip_executable = os.path.join(venv_dir, "bin", "pip")

      # Write the user's code to a temporary file
      code_file = os.path.join(temp_dir, "script.py")
      with open(code_file, "w") as f:
        f.write(code)

      try:
        # Attempt to execute the code using the virtual environment's Python
        result = subprocess.run([python_executable, code_file],
                                capture_output=True, text=True, check=True)
        logs.append("Python code executed successfully.")
        logs.append(f"Execution output:\n\n{result.stdout}")
      except subprocess.CalledProcessError as e:
        error_message = e.stderr
        # Check for ModuleNotFoundError and extract the package name
        if "ModuleNotFoundError" in error_message:
          # Extract the name of the missing module
          missing_module = extract_missing_module(error_message)
          if missing_module:
            # Attempt to install the missing module
            try:
              logs.append(f"Installing missing module: {missing_module}...")
              subprocess.run([pip_executable, "install", missing_module,
                              "--no-user"],
                             check=True)
              logs.append(f"Module {missing_module} installed successfully.")

              # Retry executing the code after installing the missing module
              #logs.append("Retrying code execution...")
              result = subprocess.run([python_executable, code_file],
                                      capture_output=True,
                                      text=True, check=True)
              logs.append("Python code executed successfully.")
              logs.append(f"Execution output:\n\n{result.stdout}")
            except subprocess.CalledProcessError:
              logs.append(f"Error installing package: {missing_module}")
          else:
            logs.append(
                f"Error: Unable to extract module name from error: {error_message}"
            )
        else:
          # Log the error message if it is not related to missing modules
          logs.append(f"Error executing code: {error_message}")

      return "\n".join(logs)

  except Exception as e:
    return f"Unexpected error: {str(e)}"

def extract_missing_module(error_message: str):
  """Extract the missing module name from a ModuleNotFoundError message."""
  try:
    # Example error message: "ModuleNotFoundError: No module named 'somepackage'"
    if "No module named" in error_message:
      start = error_message.find("'") + 1
      end = error_message.find("'", start)
      return error_message[start:end]
  except Exception:
    return None
  return None

# Initialize chat history
if "messages" not in st.session_state:
  st.session_state.messages = []
if "display_messages" not in st.session_state:
  st.session_state.display_messages = []

# Display chat history (only showing messages marked for display)
for message in st.session_state.display_messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# Chat input section
prompt = st.chat_input("What would you like to know?")

# Response section
if prompt:
  # Add user message to both lists
  st.session_state.messages.append({"role": "user", "content": prompt})
  st.session_state.display_messages.append({"role": "user", "content": prompt})
  with st.chat_message("user"):
    st.markdown(prompt)

  # Get Claude's response
  with st.chat_message("assistant"):
    try:
      iteration_count = 0
      max_iterations = 5
      messages = st.session_state.messages[:]
      # Use a local copy to avoid modifying session state during tool use

      while iteration_count < max_iterations:
        iteration_count += 1
        response = client.messages.create(
          model=model,
          max_tokens=4096,
          temperature=0,
          messages=messages,  # Full context including hidden messages
          tools=tools if iteration_count < (max_iterations - 1) else []
          # Remove tools in final iteration
        )

        # Handle initial response if any
        for content_item in response.content:
          if content_item.type == "text":
            st.markdown(content_item.text)
            messages.append({"role": "assistant", "content": content_item.text})
            st.session_state.display_messages.append(
              {"role": "assistant", "content": content_item.text})

          elif content_item.type == "tool_use":
            if content_item.name == "web_search":
              # Execute search
              results = search_duckduckgo(
                content_item.input.get("query"),
                content_item.input.get("num_results", 5)
              )

              # Format search results for display
              search_block = ["🔍 **Search Results**",
                      f"Query: {content_item.input.get('query')}"]

              for idx, result in enumerate(results, 1):
                search_block.extend([
                  f"{idx}. **{result['title']}**",
                  f"   URL: {result['url']}",
                  f"   {result.get('description', '')}"
                ])

              search_results_text = "\n".join(search_block)
              st.markdown(search_results_text)
              # Append tool output as an informational context
              messages.append({
                "role": "user",  # Using user role to provide search result context
                "content": search_results_text
              })
              st.session_state.display_messages.append(
                {"role": "assistant", "content": search_results_text})

            elif content_item.name == "read_webpage":
              # Get webpage content first
              url = content_item.input.get("url")
              content = read_webpage(url)

              # Format webpage content for display
              webpage_block = [
                "📄 **Webpage Content**",
                f"Reading: {url}",
                "Extracted content:",
                content[:500] + "..."
              ]

              webpage_text = "\n".join(webpage_block)
              st.markdown(webpage_text)
              # Append tool output as an informational context
              messages.append({
                "role": "user",  # User role to provide webpage content context
                "content": f"Content from {url}: {content}"
              })
              st.session_state.display_messages.append(
                {"role": "assistant", "content": webpage_text})

            elif content_item.name == "execute_code":
              # Get code content to execute
              code = content_item.input.get("code")
              if code:
                # Check if the code has already been executed in this session
                last_executed_code = st.session_state.get("last_executed_code", None)
                if last_executed_code == code:
                  # Inform the model that the code was already executed
                  messages.append({
                    "role": "user",  # Using user role to inform context
                    "content": "The specified code has already been executed."
                  })
                else:
                  # Show the code that will be executed
                  code_display = f"```python\n{code}\n```"
                  st.markdown(f"💻 **Code to be Executed:**\n{code_display}")
                  st.session_state.display_messages.append(
                    {"role": "assistant",
                     "content": f"💻 **Code to be Executed:**\n{code_display}"})

                  # Execute the code in a local virtual environment sandbox
                  execution_result = execute_code(code)

                  # Format code execution result for display
                  code_execution_block = [
                    "💻 **Code Execution Result**",
                    f"```\n{execution_result}\n```"
                  ]

                  code_execution_text = "\n".join(code_execution_block)
                  st.markdown(code_execution_text)
                  # Append tool output as an informational context
                  messages.append({
                    "role": "user",  # Using user role to provide code execution context
                    "content": code_execution_text
                  })
                  st.session_state.display_messages.append(
                    {"role": "assistant", "content": code_execution_text})

                  # Store the executed code to prevent re-execution
                  st.session_state.last_executed_code = code

        # If no tool use was requested, break the loop
        if not any(item.type == "tool_use" for item in response.content):
          break

      # Update session state messages with new content
      st.session_state.messages.extend(messages[len(st.session_state.messages):])

    except Exception as e:
      st.error(f"An error occurred: {str(e)}")
      if "invalid_api_key" in str(e).lower():
        st.session_state.api_key = None
        st.rerun()