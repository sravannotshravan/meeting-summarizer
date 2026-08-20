import json
import requests


LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"


# -------------------------------------------------------------------
# Test meeting transcript
# -------------------------------------------------------------------

meeting = """
The team discussed the meeting summarizer project.

Sravan suggested using Whisper for speech recognition and
Qwen running locally through llama.cpp for summarization.

Rahul agreed with the approach but said the project needs
a clean frontend for uploading meeting recordings.

Rahul will prepare the frontend prototype by Friday.

Sravan will benchmark the Whisper models and test the
summarization pipeline before the next meeting on Monday.

The team decided to keep the entire AI pipeline local
so that meeting recordings do not need to be uploaded
to an external API.
"""


# -------------------------------------------------------------------
# JSON schema
# -------------------------------------------------------------------

schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string"
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task": {
                        "type": "string"
                    },
                    "assignee": {
                        "type": "string"
                    },
                    "deadline": {
                        "type": "string"
                    }
                },
                "required": [
                    "task",
                    "assignee",
                    "deadline"
                ]
            }
        }
    },
    "required": [
        "summary",
        "key_points",
        "decisions",
        "action_items"
    ]
}


# -------------------------------------------------------------------
# Request
# -------------------------------------------------------------------

payload = {
    "model": "Qwen3-8B",

    "messages": [
        {
            "role": "system",
            "content": (
                "You are a meeting analysis assistant.\n\n"
                "Extract only information explicitly supported by "
                "the meeting transcript.\n\n"
                "Do not invent people, decisions, tasks, or deadlines.\n\n"
                "If an action item's assignee is not mentioned, use "
                "\"Unknown\".\n\n"
                "If an action item's deadline is not mentioned, use "
                "\"Unknown\".\n\n"
                "Return only the requested structured output."
            )
        },
        {
            "role": "user",
            "content": (
                "Analyze the following meeting transcript.\n\n"
                + meeting
            )
        }
    ],

    # Low temperature = more deterministic extraction
    "temperature": 0.1,

    "max_tokens": 1000,

    # Qwen3: disable reasoning for this task
    "chat_template_kwargs": {
        "enable_thinking": False
    },

    # Force structured JSON output
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "meeting_summary",
            "schema": schema
        }
    }
}


# -------------------------------------------------------------------
# Send request
# -------------------------------------------------------------------

print("Sending transcript to Qwen3...")
print()

try:
    response = requests.post(
        LLAMA_URL,
        json=payload,
        timeout=300
    )

    response.raise_for_status()

except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to llama-server.")
    print()
    print("Make sure llama-server is running:")
    print()
    print(
        "~/llama.cpp/build/bin/llama-server "
        "-hf Qwen/Qwen3-8B-GGUF:Q4_K_M "
        "-ngl 99 "
        "-c 8192 "
        "--host 127.0.0.1 "
        "--port 8080"
    )
    raise SystemExit(1)

except requests.exceptions.HTTPError:
    print("ERROR: llama-server returned an HTTP error.")
    print(response.text)
    raise SystemExit(1)


# -------------------------------------------------------------------
# Parse response
# -------------------------------------------------------------------

result = response.json()

try:
    content = result["choices"][0]["message"]["content"]
except (KeyError, IndexError, TypeError):
    print("ERROR: Unexpected llama-server response:")
    print(json.dumps(result, indent=2))
    raise SystemExit(1)


if not content or not content.strip():
    print("ERROR: Model returned empty content.")
    print()
    print("Full server response:")
    print(json.dumps(result, indent=2))
    raise SystemExit(1)


# -------------------------------------------------------------------
# Parse generated JSON
# -------------------------------------------------------------------

try:
    summary = json.loads(content)

except json.JSONDecodeError:
    print("ERROR: Model returned invalid JSON.")
    print()
    print("Raw model output:")
    print(content)
    raise SystemExit(1)


# -------------------------------------------------------------------
# Validate expected fields
# -------------------------------------------------------------------

required_fields = [
    "summary",
    "key_points",
    "decisions",
    "action_items"
]

missing_fields = [
    field for field in required_fields
    if field not in summary
]

if missing_fields:
    print("ERROR: Model response is missing fields:")
    print(missing_fields)
    print()
    print("Model response:")
    print(json.dumps(summary, indent=2))
    raise SystemExit(1)


# -------------------------------------------------------------------
# Display result
# -------------------------------------------------------------------

print("=" * 60)
print("MEETING SUMMARY")
print("=" * 60)
print()

print(summary["summary"])
print()

print("KEY POINTS")
print("-" * 60)

for point in summary["key_points"]:
    print(f"• {point}")

print()

print("DECISIONS")
print("-" * 60)

for decision in summary["decisions"]:
    print(f"• {decision}")

print()

print("ACTION ITEMS")
print("-" * 60)

for item in summary["action_items"]:
    print(f"• Task:     {item['task']}")
    print(f"  Assignee: {item['assignee']}")
    print(f"  Deadline: {item['deadline']}")
    print()

print("=" * 60)

# Also save the structured result for later testing
output_file = "test_summary.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"Saved structured result to: {output_file}")
