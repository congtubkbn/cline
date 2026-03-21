import argparse
import os
from google import genai
from google.genai import types

def generate_next_query(notebooklm_text: str) -> str:
    # Initialize the client. It automatically picks up the GEMINI_API_KEY env variable.
    client = genai.Client()
    
    # The system instruction strictly limits the AI's role to prevent conversational filler
    system_instruction = """
    You are an expert technical reviewer and analytical engine. 
    1. Deeply analyze the provided NotebookLM response for technical depth, missing nuances, and logical gaps.
    2. Formulate the single most critical follow-up question to feed back into NotebookLM to extract deeper, highly specific information from the source documents.
    3. Output ONLY the generated question. Do not include any introductory text, explanations, or quotes.
    """

    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=f"NotebookLM Response:\n{notebooklm_text}",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2, # Low temperature ensures focused, precise outputs
        ),
    )
    
    return response.text.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze NotebookLM output via Gemini API.")
    parser.add_argument("--text", "-t", type=str, required=True, help="The response text from NotebookLM")
    
    args = parser.parse_args()
    
    print("Analyzing...")
    next_query = generate_next_query(args.text)
    
    print("\n--- Generated Next Query ---")
    print(next_query)
    print("----------------------------\n")