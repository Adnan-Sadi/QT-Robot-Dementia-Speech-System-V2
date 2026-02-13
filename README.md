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
    python3 -m app.main
    ```
3. You should see a simple window with start chat and stop chat buttons.


## Architecture Overview

Based on the codebase, here is a detailed breakdown of the key files that make your conversational AI work.

---

### `speech_app.py`

This is the central application that orchestrates the entire conversational experience. It acts as a **ROS service server** and the main process that stays active to handle incoming requests. Its primary functions are:

* **Service Provision**: It advertises the `/qt_robot/speech/recognize` service. This is the entry point that other programs (or a manual `rosservice call`) use to initiate a conversation with the robot.
* **Audio Handling**: It subscribes to a topic (`/qt_respeaker_app/channel0`) to continuously receive audio data from the microphone. This data is buffered in an internal queue until a recognition request is made.
* **Google Cloud Speech Integration**: Uses Google Cloud Speech-to-Text API to transcribe audio streams in real-time with support for voice activity detection and interim results.
* **Backend Integration**: When the `/qt_robot/speech/recognize` service is called, this script takes the transcribed text, sends it to the backend via [`BackendBridge`](services/backend_client.py), and then sends the response to [`speakout.py`](speakout.py) to make the robot speak.
* **Conversational Loop**: The `callback_recognize` function is designed to call itself recursively. This creates a loop where the robot listens, responds, and then automatically starts listening again, allowing for a continuous, back-and-forth conversation.
* **Emotion Feedback**: Provides immediate visual feedback by showing listening emotions when the user starts speaking, enhancing the natural interaction experience.

### `services/backend_client.py`

This file contains the code for connecting QT Robot to the cloud backend. It uses the [`aiohttp`](https://docs.aiohttp.org/) library to establish WebSocket connections and handle asynchronous communication.

#### **BackendClient**
The core asynchronous client that manages the WebSocket connection:

* **Authentication**: Uses `USERNAME` and `PASSWORD` from [`.env`](.env) to connect to the backend (configured via [`config/settings.py`](config/settings.py)) and fetch the JWT access token via POST request to `/api/token/`.
* **WebSocket Connection**: Opens a WebSocket connection to `wss://{HOST}/ws/chat/?token=<access>&source=<client>` with automatic reconnection on failure using exponential backoff (up to 30 seconds).
* **Request/Response Handling**: Each transcription request creates an `asyncio.Future`, a placeholder for a response that hasn't arrived yet. When the backend sends an "llm_response" message, the listener resolves the matching future, instantly unblocking the waiting coroutine. This ensures every request gets exactly one response in order.
* **Message Format**: 
  - Sends: `{"type": "transcription", "data": "<user_text>"}`
  - Receives: `{"type": "llm_response", "data": "<bot_reply>", "emotion": "<emotion_name>"}`

#### **BackendBridge**
A thread-safe synchronous wrapper that makes the async client usable in ROS/synchronous code:

* **Thread Management**: Runs the asynchronous [`BackendClient`](services/backend_client.py) in a background thread with its own event loop, isolated from the main ROS thread.
* **Blocking Interface**: Exposes `send_transcript_and_wait()` which blocks until the backend responds, making it simple to call from synchronous code like [`speech_app.py`](speech_app.py).
* **Lifecycle Management**: Provides `start()` and `stop()` methods to cleanly initialize and shut down the backend connection.
* **Timeout Support**: Configurable timeout for waiting on responses (default from [`settings.DEFAULT_TIMEOUT`](config/settings.py)).

### `speakout.py`

This file is a specialized **ROS service client** and a utility module for the robot's speech and gestures. Its purpose is to abstract away the low-level ROS communication details for text-to-speech and motion control.

* **Node Initialization**: The [`initialize_ros_node`](speakout.py) function is critical. It sets up a ROS node and creates connections (`rospy.ServiceProxy`) to the robot's built-in services. This connection allows other parts of your code to call these services as if they were simple Python functions.
* **Service Proxies**: It defines multiple key services:
  - `speech_say_service` (for basic text-to-speech)
  - `speech_config_service` (for configuring speech parameters like speed)
  - `behavior_talkText_service` (for text-to-speech with lip-syncing)
  - `emotion_show_service` (for displaying emotions on the robot's face)
  - `gesture_play_service` (for playing gestures/animations)
* **Gesture Mapping**: The [`gesture_for_mood`](speakout.py) function maps emotions to appropriate gestures (e.g., "happy" → approval/pointing, "sad" → sad gesture).
* **Asynchronous Execution**: Gestures and emotions are played in separate threads to avoid blocking the main speech execution.
* **Simplified API**: The [`say_text_with_service`](speakout.py) function provides a clean API for making the robot speak with synchronized lip movements and gestures. It automatically selects and plays appropriate gestures based on the detected emotion while the robot is speaking.

### Configuration Files

#### `.env`
Contains all environment-specific configuration:
- Backend connection details (URL, credentials, WebSocket path)
- Audio settings (sample rate, language, model selection)
- Timeout values for LLM responses
- Speech speed and emotion configurations

#### `config/settings.py`
Loads and validates configuration from [`.env`](.env), providing a centralized [`Settings`](config/settings.py) class that's imported throughout the application via `from config.settings import settings`.