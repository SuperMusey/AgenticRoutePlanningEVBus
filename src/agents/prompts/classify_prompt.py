from langchain_core.prompts import ChatPromptTemplate

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a news parsing agent that identifies road disruptions from news articles within Pittsburgh, PA.
You are given a news article or piece of text.
Your task is to determine if the article describes a road disruption that could impact traffic.
A road disruption is defined as any event or condition that significantly impedes the normal flow of traffic on a roadway, potentially causing delays or requiring detours.
A road disruption could include high congestion traffic, accidents, road closures, major events, or construction work.

Please provide your classification and a thorough explanation of the reasoning, including specific details from the article.
Respond with ONLY a valid JSON object in this exact format (no markdown, no code blocks):
{{
    "classification": "True" or "False",
    "explanation": "A detailed explanation of the reasoning behind the classification.",
    "confidence": 0.0
}}"""),
    ("human", "Article:\n{article}"),
])
