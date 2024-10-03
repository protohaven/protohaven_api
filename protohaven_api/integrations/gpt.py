"""Functions invoking LLMs and passing prompts"""
from openai import OpenAI

from protohaven_api.config import get_config


def _act_on_content(directive, content):
    """Invoke GPT on sequential content and return the result"""
    client = OpenAI(api_key=get_config()["openai"]["api_key"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": directive}]
        + [{"role": "user", "content": c} for c in content],
    )
    return response.choices[0].message.content


def summarize_message_history(msgs):
    """Summarize history of chat messages"""
    return _act_on_content(
        "You are a newsletter writer trying to summarize the following series of chat \
        messages sent via Discord. Use simple words, be casual and straightforward, \
        and limit to 2-3 topics at maximum. This is a section that will be appended \
        to a broader discussion about recent discord conversations. Do not mention \
        users by name, and don't lead in or out; just jump straight into the content.",
        msgs,
    )


def summary_summarizer(summaries):
    """Summarizes a list of summaries using GPT."""
    return _act_on_content(
        "You are a newsletter writer trying to cut down and summarize the following \
        list of summaries of discord channels. Use simple words, be casual and \
        straightforward, and limit to 4-6 topics at maximum. Markdown formatting \
        Ois permitted.",
        summaries,
    )
