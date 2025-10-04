from google import genai
from google.genai import types
import os
import sys

# Global chat history
chat_history = []

# Initialize Gemini client once
GOOGLE_API_KEY = "AIzaSyBqBKBTROMinR-t0VcbTpQztrXK5drCYbU"
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"[FATAL] Gemini API client initialization failed: {e}")
    sys.exit(1)

# System behavior
system_instruction = (
    " You are a friendly robot assistant name **QT robot** designed to chat naturally with older adults, especially those with **dementia**. Speak clearly, kindly, and keep responses short, and simple with one or two sentences — like you're having a warm, everyday conversation. Only give gentle humor, ask friendly follow-up questions, and never overload with too much information. Make the user feel relaxed, understood, and engaged. Dont add any special characters like emojils in the response"
)

def talk_to_gemini(user_message: str) -> str:
    """
    Send a message to Gemini and return the model's reply.
    This function no longer handles the TTS call directly.
    """
    if not user_message.strip():
        return "[No input received]"

    chat_history.append({"role": "user", "message": user_message})
    contents = [f"{entry['role']}: {entry['message']}" for entry in chat_history]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(system_instruction=system_instruction),
            contents="\n".join(contents)
        )
        model_reply = response.text.strip()
    
    except Exception as e:
        model_reply = f"[Gemini Error] {str(e)}"
        
    chat_history.append({"role": "model", "message": model_reply})
    
    return model_reply

if __name__ == "__main__":
    # Optional: standalone test
    # This block is for testing purposes only and assumes speakout.py functions are available
    # It would be run in a separate script or interactive session.
    # initialize_ros_node()
    reply1 = talk_to_gemini("Hello there!")
    reply2 = talk_to_gemini("Can you help me remember my grandson's name?")
    # say_text_with_service(reply1)
    # say_text_with_service(reply2)


