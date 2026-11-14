import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


class GeminiService:

    def __init__(self):

        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

    def generate(self, prompt):

        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        return response.text