### Part 1: Install Python Dependencies on ROS

Open a terminal and create a virtual environment for the required dependencies.

1.  Activate you virtual environ from your environment directory. For example:
    ```bash
    source ~/catkin_ws/src/dementia_speech_system/src/venv_py310/bin/activate
    ```

The script will now be running and ready to receive commands.

-----

### Part 2: Run the Main ROS Node

Open a terminal and start the main Python script. This will launch the speech-to-text service and wait for a request.

1.  Navigate to your project's source directory:
    ```bash
    cd /home/qtrobot/catkin_ws/src/qt_gspeech_app/src/
    ```
2.  Run the Python script:
    ```bash
    python speech_app.py
    ```

The script will now be running and ready to receive commands.

-----

### Part 3: Start the Conversation

Open a **second terminal** to initiate the conversation.

1.  Use the `rosservice call` command to send a one-time request to the speech recognition service:
    ```bash
    rosservice call /qt_robot/speech/recognize "{}"
    ```
2.  After you run this command, the robot will begin listening for your voice. It will then enter a conversational loop, where it will listen, respond, and then automatically listen for the next utterance.


Based on our conversation and the code you've provided, here is a detailed breakdown of the three key files that make your conversational AI work.

---

### `speech_app.py`

This is the central application that orchestrates the entire conversational experience. It acts as a **ROS service server** and the main process that stays active to handle incoming requests. Its primary functions are:

* **Service Provision**: It advertises the `/qt_robot/speech/recognize` service. This is the entry point that other programs (or a manual `rosservice call`) use to initiate a conversation with the robot.
* **Audio Handling**: It subscribes to a topic (`/qt_respeaker_app/channel0`) to continuously receive audio data from the microphone. This data is buffered in an internal queue until a recognition request is made.
* **Gemini and TTS Integration**: When the `/qt_robot/speech/recognize` service is called, this script takes the transcribed text, sends it to the `talk_to_gemini.py` module to get a response, and then sends that response to the `speakout.py` module to make the robot speak.
* **Conversational Loop**: The `callback_recognize` function is designed to call itself recursively. This creates a loop where the robot listens, responds, and then automatically starts listening again, allowing for a continuous, back-and-forth conversation.

### `backend_ws_client.py`
This file contains the codes for connecting QT to our google cloud backend. It uses the aiohttp library to connect to the backend websocket url and start a new conversation.

* **Backend Client**: Uses the `username` and `password` to connect to the backend and fetch the access token. It then opens a websocket connections, sends transcriptions, and asynchronously listens for model responses. Each transcription request creates an asyncio.Future, a placeholder for a response that hasn’t arrived yet. When the backend sends an "llm_response" message, the listener resolves the matching future, instantly unblocking the waiting coroutine. This ensures every request gets exactly one response in order.

* **BackendBridge**: The `BackendBridge` runs the asynchronous client in a background thread and exposes simple, synchronous methods that can be called within synchronous code. It spins its own event loop, connects the backend client, and defines a callable `send_transcript_and_wait()` which is used in `speech_app.py` to send a transcript and wait for a reply.

### `speakout.py`

This file is a specialized **ROS service client** and a utility module for the robot's speech. Its purpose is to abstract away the low-level ROS communication details for text-to-speech.

* **Node Initialization**: The `initialize_ros_node` function is critical. It sets up a ROS node and creates a connection (`rospy.ServiceProxy`) to the robot's built-in speech services. This connection allows other parts of your code to call these services as if they were simple Python functions.
* **Service Proxies**: It defines three key services: `speech_say_service` (for basic text-to-speech), `speech_config_service` (for configuring speech parameters), and `behavior_talkText_service` (which is used for lip-syncing).
* **Simplified API**: The `say_text_with_service` function provides a clean API for making the robot speak. It handles creating the ROS request message and making the service call. By using the `behavior_talkText_service`, it automatically enables lip-sync. 
