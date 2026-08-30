"""DEPRECATED — superseded by app.services.llm, which does provider failover
against NVIDIA (primary) and OpenRouter (fallback).

Its only remaining importer is the equally dead app.services.ai_agent. The model
ids hardcoded below are no longer served: google/gemini-2.5-flash returns HTTP
402 "requires more credits" and gemini-1.5-flash returns HTTP 404 "No endpoints
found". Removal is tracked as I-21; see docs/MODEL_SELECTION.md.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import anthropic
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class BaseAIProvider(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

class AnthropicProvider(BaseAIProvider):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

    @property
    def name(self) -> str:
        return "Anthropic (Claude)"

    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        if not self.client:
            raise ValueError("Anthropic API key not set")
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        return response.content[0].text

class GoogleProvider(BaseAIProvider):
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None

    @property
    def name(self) -> str:
        return "Google (Gemini)"

    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        if not self.model:
            raise ValueError("Google API key not set")
        
        # Convert messages to Gemini format
        # Gemini expects a list of parts, we'll simplify
        prompt_parts = [system_prompt]
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            prompt_parts.append(f"{role.capitalize()}: {msg['content']}")
        
        response = self.model.generate_content("\n".join(prompt_parts))
        return response.text

class GroqProvider(BaseAIProvider):
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

    @property
    def name(self) -> str:
        return "Groq (Llama 3)"

    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        if not self.client:
            raise ValueError("Groq API key not set")
        
        # Groq uses OpenAI-compatible format
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        completion = self.client.chat.completions.create(
            model="llama3-70b-8192",
            messages=full_messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content

class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    @property
    def name(self) -> str:
        return "OpenAI (GPT-4o-mini)"

    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        if not self.client:
            raise ValueError("OpenAI API key not set")
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full_messages,
            max_tokens=1024,
        )
        return response.choices[0].message.content

class OpenRouterProvider(BaseAIProvider):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        ) if settings.OPENROUTER_API_KEY else None

    @property
    def name(self) -> str:
        return "OpenRouter"

    def generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        if not self.client:
            raise ValueError("OpenRouter API key not set")
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=full_messages,
            max_tokens=1024,
            timeout=15.0
        )
        return response.choices[0].message.content
