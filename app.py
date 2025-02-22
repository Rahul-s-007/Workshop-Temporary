import streamlit as st

from openai import OpenAI

import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ReAct_prompt_template = """
You run in a loop of Thought, Action, PAUSE, Action_Response.
At the end of the loop you output an Answer.

Use Thought to understand the question you have been asked.
Use Action to run one of the actions available to you - then return PAUSE.
Action_Response will be the result of running those actions.

Thought and Action should occur in the same turn.

If you have multiple actions to run, you can run them in consecutive turns.

Your available actions are:
{tool_descriptions}
"""

example_session_prompt = """
# Example session:

Question: what is the response time category for something.com?
Thought: I should check the response time for the web page first.
Action:

{{
  "function_name": "get_response_time",
  "function_params": {{
    "url": "something.com"
  }}
}}

PAUSE

You will be called again with this:

Action_Response: 5

Thought: I should now output the response time ranking.

Action:

{{
  "function_name": "get_response_time_category",
  "function_params": {{
    "response_time": 5
  }}
}}

PAUSE

You will be called again with this:

Action_Response: Fast

You then output:

Answer: The response time category for something.com is Fast.
"""

system_prompt_template = ReAct_prompt_template + example_session_prompt



# Get Response Time
from ping3 import ping

def get_response_time(url):
    response_time = ping(url, unit='ms') # 's' for seconds and 'ms' for milliseconds
    if response_time is None:
        return -1
    else:
        return response_time


# Get Response Time Category
def get_response_time_category(response_time):
    if response_time <= 10:
        return "Fast"
    if response_time > 10:
        return "Slow"

# Get City Weather
import requests

def get_weather(city):
    url = f"https://wttr.in/{city}?format=%C+%t+%h+%w"
    response = requests.get(url)

    if response.status_code == 200:
        weather_data = response.text.strip().split()
        return weather_data
    else:
        return ["Error: Unable to fetch weather data"]

# Ask User Question
def ask_user_question(question):
    return question

tools = [
    {
        "function_name": "get_response_time",
        "function_call": get_response_time,
        "function_params": [
            {   "param_name": "url",
                "type": str
            }
        ],
        "example_input": "google.com",
        "return_type": int,
        "description": "Returns the response time of a website in ms, returns -1 if the website is unreachable"
    },

    {
        "function_name": "get_response_time_category",
        "function_call": get_response_time_category,
        "function_params": [
            {   "param_name": "response_time",
                "type": int
            }
        ],
        "example_input": "5",
        "return_type": str,
        "description": "Returns the category based upon the response time of a website"
    },

    {
        "function_name": "get_weather",
        "function_call": get_weather,
        "function_params": [
            {   "param_name": "city",
                "type": str
            }
        ],
        "example_input": "New York",
        "return_type": list,
        "description": "Returns the weather information of a particular 'city' which includes Condition, Temperature, Humidity, Wind Speed",
    },
    {
        "function_name": "ask_user_question",
        "function_call": ask_user_question,
        "function_params": [
            {   "param_name": "question",
                "type": str
            }
        ],
        "example_input": "Where are you going?",
        "return_type": str,
        "description": "Ask user a question to get information inorder to answer the question asked by the user",
    }
]


def get_tool_descriptions(tools):

    tool_descriptions = ""

    for tool in tools:
      tool_descriptions += "\n"
      tool_descriptions += tool['function_name'] + ":"
      tool_descriptions += "\nDescription: " + tool["description"]
      tool_descriptions += "\nParameters:"
      for param in tool["function_params"]:
        tool_descriptions += "\n\t" + param["param_name"] + ": " + str(param["type"])
      tool_descriptions += "\n\tReturn type: " + str(tool["return_type"])
      tool_descriptions += "\ne.g. " + tool["function_name"] + ": " + tool["example_input"]
      tool_descriptions += "\n"

    return tool_descriptions

tool_descriptions=get_tool_descriptions(tools)
print(tool_descriptions)

system_prompt = system_prompt_template.format(tool_descriptions=tool_descriptions)


# Get LLM Response:
def generate_text_with_conversation(messages, model = "gpt-3.5-turbo"):
    response = client.chat.completions.create(
        model=model,
        messages=messages
        )
    return response.choices[0].message.content

available_actions = {
    tool["function_name"]: tool["function_call"] for tool in tools
}

import re
import json

def extract_json(text_response):
    pattern = r'\{.*?\}'
    matches = re.finditer(pattern, text_response, re.DOTALL)
    json_objects = []

    for match in matches:
        json_str = extend_search_new(text_response, match.span())
        try:
            json_obj = json.loads(json_str)
            json_objects.append(json_obj)
        except json.JSONDecodeError:
            continue

    return json_objects if json_objects else None

def extend_search_new(text, span):
    start, end = span
    nest_count = 1  # Starts with 1 since we know '{' is at the start position
    for i in range(end, len(text)):
        if text[i] == '{':
            nest_count += 1
        elif text[i] == '}':
            nest_count -= 1
            if nest_count == 0:
                return text[start:i+1]
    return text[start:end]

st.title("AI Chatbot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.turn_count = 1
    st.session_state.max_turns = 10

    st.session_state.messages.append({"role": "system", "content": system_prompt})

# Display chat history
for message in st.session_state.messages:
    if message["role"] == "system":
        pass
    else:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Type your message..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    while st.session_state.turn_count < st.session_state.max_turns:
        response = generate_text_with_conversation(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

        json_function = extract_json(response)
        if json_function:
            function_name = json_function[0]['function_name']
            function_params = json_function[0]['function_params']

            if function_name not in available_actions:
                st.error(f"Unknown action: {function_name}: {function_params}")
                break

            action_function = available_actions[function_name]
            result = action_function(**function_params)

            if function_name == "ask_user_question":
                st.session_state.messages.append({"role": "assistant", "content": result})

                with st.chat_message("assistant"):
                    st.markdown(result)

                break

            else:
                function_result_message = f"Action_Response: {result}"
                st.session_state.messages.append({"role": "user", "content": function_result_message})

                with st.chat_message("user"):
                    st.markdown(function_result_message)
        else:
            break

        st.session_state.turn_count += 1