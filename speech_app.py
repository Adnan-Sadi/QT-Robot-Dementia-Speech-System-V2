#!/usr/bin/env python3
import os
import sys
import threading
import rospy

from qt_gesture_controller.srv import * # for gesture
from qt_robot_interface.srv import emotion_show, emotion_showRequest # for emotion
from qt_robot_interface import srv
import threading #new

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(script_dir, '/home/qtrobot/catkin_ws/src/dss_backend_connected')
    if module_dir not in sys.path:
        sys.path.append(module_dir)

    from src.speakout import initialize_ros_node, configure_speech_speed, _play_gesture_async
    # from src.vader_emotion import classify_emotion, zero_shot_classifier # new for emotion and gesture
    from services.qt_speech import QTrobotSpeech
    from config.settings import settings

    # for debugging
    #rospy.logwarn(f"CWD: {os.getcwd()}")
    #rospy.logwarn(f"ENV USERNAME raw: {repr(os.getenv('USERNAME'))}")
    #rospy.logwarn(f"settings.USERNAME: {repr(settings.USERNAME)}")
    #rospy.logwarn(f"settings.PASSWORD: {repr(settings.PASSWORD)}")
    #rospy.logwarn(f"settings.BASE_HTTP_URL: {repr(settings.BASE_HTTP_URL)}")

except ImportError as e:
    print(f"Error importing from module: {e}")


# --- Conditional STT backend imports ---
if settings.STT_ENGINE == "vosk":
    from qt_vosk_app.srv import speech_recognize, speech_recognizeRequest, speech_recognizeResponse
else:  # default: gspeech
    from qt_gspeech_app.srv import speech_recognize, speech_recognizeRequest, speech_recognizeResponse


def do_startup_movement():
    # ... (gesture and emotion setup, same as before) ...
    rospy.wait_for_service('/qt_robot/gesture/play')
    gesture_play_service = rospy.ServiceProxy('/qt_robot/gesture/play', gesture_play)
    threading.Thread(target=_play_gesture_async, args=("QT/happy",), daemon=True).start()

    rospy.wait_for_service('/qt_robot/emotion/show')
    emotion_show_service = rospy.ServiceProxy('/qt_robot/emotion/show', srv.emotion_show)
    emo_req = srv.emotion_showRequest()
    emo_req.name = f"QT/yawn"
    emotion_show_service(emo_req)


if __name__ == "__main__":
    initialize_ros_node()
    configure_speech_speed(settings.SPEECH_SPEED)

    qt_speech = QTrobotSpeech(speech_recognize, speech_recognizeResponse)

    do_startup_movement()

    # Start the recognize service call in a new thread
    def start_recognition_loop():
        rospy.loginfo("Starting QT Speech Recognition loop in a background thread...")
        req = speech_recognizeRequest()
        req.timeout = settings.DEFAULT_TIMEOUT
        req.language = settings.DEFAULT_LANGUAGE

        while not rospy.is_shutdown():
            try:
                resp = qt_speech.speech_recognize_client(req)
                transcript = getattr(resp, "transcript", "")
                qt_speech.process_transcript(transcript)
            except rospy.ServiceException as e:
                if rospy.is_shutdown():
                    break
                rospy.logwarn(f"Speech recognition service client error: {e}")
                rospy.sleep(1.0)
            except Exception as e:
                if rospy.is_shutdown():
                    break
                rospy.logerr(f"Unexpected error in recognition thread: {e}")
                rospy.sleep(1.0)

    # Start the thread with daemon=True so it doesn't prevent the main app from exiting
    # once the main thread (rospy.spin()) is terminated.
    threading.Thread(target=start_recognition_loop, daemon=True).start()

    # ------------------------------------------------------------------

    rospy.loginfo("QT Speech App is Ready! Press Ctrl+C to shut down.")
    rospy.on_shutdown(lambda: qt_speech.backend.stop())

    # The main thread now runs rospy.spin(), which can handle the Ctrl+C signal.
    rospy.spin()

    rospy.loginfo("QT Speech App Shutdown")