"""Strands AI Agent with OpenRouter backend via LiteLLM."""

import os
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

# Load environment variables from .env file
load_dotenv()


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city.

    Args:
        city: The name of the city to look up weather for.

    Returns:
        A string describing the current weather conditions.
    """
    return f"72°F and sunny in {city}"


# Configure the LiteLLM model to use OpenRouter
model = LiteLLMModel(
    model_id="openrouter/tencent/hy3-preview:free",
    client_args={
        "api_key": os.environ.get("OPENROUTER_API_KEY"),
        "api_base": "https://openrouter.ai/api/v1",
    },
)

# Create the agent with the model, system prompt, and tools
agent = Agent(
    model=model,
    system_prompt=(
        "You are a helpful assistant. Use your tools to answer questions "
        "about the world."
    ),
    tools=[get_weather],
)

if __name__ == "__main__":
    response = agent("What's the weather like in New York?")
    print(response)
