import os
from google import genai

def test_connection():
    # 1. Verify Python can see the environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not found.")
        print("Please ensure you set it in this specific terminal session.")
        return

    print("✅ API Key found! Attempting to connect to Gemini...")

    try:
        # 2. Initialize the client (automatically uses the env variable)
        client = genai.Client()

        # 3. Make a simple, fast request using the Flash model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Respond with exactly: "Connection successful!" Then tell me a one-line joke about programming.'
        )
        
        # 4. Print the successful response
        print("\n--- Response from Gemini ---")
        print(response.text.strip())
        print("----------------------------")
        print("\n🎉 Everything is working perfectly. You are ready to integrate with NotebookLM!")

    except Exception as e:
        print(f"\n❌ An error occurred during the API call:\n{e}")

if __name__ == "__main__":
    test_connection()