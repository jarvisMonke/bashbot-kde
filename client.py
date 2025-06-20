import os
import re
import json
import subprocess
import yaml
from jinja2 import Template
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def load_prompts(filepath="prompts.yaml"):
    with open(filepath, "r") as f:
        return yaml.safe_load(f)


def render_prompt(template_str, **kwargs):
    template = Template(template_str)
    return template.render(**kwargs)

prompts = load_prompts()


def prompt(prompt_text: str):
    """
    Sends a prompt to the Gemini API and returns the response.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_text,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # Disable thinking for determinism
            temperature=0.0
        ),
    ) 
    return extract_json_array(response.text)


def extract_json_array(text: str):
    """
    Extracts and parses the first complete JSON array (e.g., [ ... ]) from text.
    Returns the parsed Python object (list of str/dict).
    """
    # Regex to match a JSON array
    json_array_pattern = re.compile(r'\[\s*(?:.|\s)*?\s*\]', re.DOTALL)

    match = json_array_pattern.search(text)
    if not match:
        raise json.JSONDecodeError("No JSON array found", text, 0)

    candidate = match.group()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Failed to parse JSON array: {e}", candidate, 0)

user_prompt = input("Enter your request: ")

"""User request: Create a directory called 'test_dir' in my home folder and list its contents."""


def execute_stepwise_commands(response_json):
    for idx, item in enumerate(response_json):
        if isinstance(item, str):
            # First item is the friendly message
            print(f"\n🤖 LLM: {item}")
        elif isinstance(item, dict):
            description = item.get("description", f"Step {idx}")
            command = item.get("bash_command")

            print(f"\n➡️ {description}")
            print(f"📟 Running: {command}")

            result = subprocess.run(command, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ Command succeeded")
                print(result.stdout)
            else:
                print("❌ Command failed")
                print(f"Exit code: {result.returncode}")
                print(f"Error: {result.stderr.strip()}")

                system_prompt_failure = render_prompt(
                    prompts["system_prompt_failure"],
                    failed_command=f"{command}",
                    stderr_output=f"{result.stderr.strip()}"
                )
                execute_stepwise_commands(prompt(system_prompt_failure))


# Render initial system prompt (no variables)
system_prompt_initial = render_prompt(prompts["system_prompt_initial"])

response_json = prompt(f"{system_prompt_initial}{user_prompt}")
execute_stepwise_commands(response_json)

"""create the file monke.js inside the dir monke which already exists"""