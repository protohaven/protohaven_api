"""Functions invoking LLMs and passing prompts"""
from openai import OpenAI

from protohaven_api.config import get_config


def _act_on_content(directive, content):
    """Invoke GPT on sequential content and return the result"""
    client = OpenAI(api_key=get_config("openai/api_key"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": directive}]
        + [{"role": "user", "content": c} for c in content],
    )
    return response.choices[0].message.content


def summarize_message_history(msgs):
    """Summarize history of chat messages"""
    return _act_on_content(
        "Create a summary for a newsletter about Protohaven, Pittsburgh’s Premier Makerspace, \
        using highlights from Discord chats by members. The audience consists of Protohaven \
        members and subscribers, so aim to showcase activities at the shop that might \
        entice more visits. Consider including discussions about upcoming events, interesting \
        projects, or practical advice shared among members. Use simple and informal language. \
        Focus on 2-3 major topics, emphasizing recurring themes over isolated comments. \
        Integrate these insights directly into the content without introductory or concluding \
        remarks, ensuring a seamless addition to a broader discussion about Discord interactions.",
        msgs,
    )


def summary_summarizer(summaries):
    """Summarizes a list of summaries using GPT."""
    return _act_on_content(
        "As a newsletter writer, distill and summarize the provided list of Discord channel \
        summaries. Aim to cover 4-6 key topics using simple and straightforward language. \
        Apply markdown formatting appropriately for clear and effective communication. \
        Focus on retaining essential information and present it casually and straightforwardly.",
        summaries,
    )
