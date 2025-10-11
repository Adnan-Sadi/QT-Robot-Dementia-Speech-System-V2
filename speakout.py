#!/usr/bin/env python3
import sys
import threading #new
import random
import rospy
from qt_robot_interface.srv import speech_say, speech_sayRequest, speech_config, speech_configRequest,behavior_talk_text, behavior_talk_textRequest, emotion_show, emotion_showRequest
from qt_robot_interface import srv
from qt_gesture_controller.srv import *

# Initialize global service proxy variables
speech_say_service = None
speech_config_service = None
behavior_talkText_service = None
emotion_show_service = None # New for emotion
gesture_play_service = None
def initialize_ros_node():
    """
    Initializes the ROS node and the service proxies.
    This should be called once at the start of your application.
    """
    global speech_say_service, speech_config_service,behavior_talkText_service, emotion_show_service, gesture_play_service # new added for emotion and gesture
    
    if speech_say_service is not None:
        rospy.loginfo("ROS node and service already initialized.") 
        return

    try:
        rospy.init_node('qt_gemini_tts_client', anonymous=True)
        rospy.loginfo("ROS node 'qt_gemini_tts_client' started!")

        rospy.loginfo("Waiting for the speech services to become available...")
        rospy.wait_for_service('/qt_robot/speech/say')
        rospy.wait_for_service('/qt_robot/speech/config')
        rospy.wait_for_service('/qt_robot/behavior/talkText') # NEW
        rospy.wait_for_service('/qt_robot/emotion/show') # New for emotion
        rospy.wait_for_service('/qt_robot/gesture/play')
        speech_say_service = rospy.ServiceProxy('/qt_robot/speech/say', speech_say)
        speech_config_service = rospy.ServiceProxy('/qt_robot/speech/config', speech_config)
        behavior_talkText_service = rospy.ServiceProxy('/qt_robot/behavior/talkText', srv.behavior_talk_text) # NEW
        emotion_show_service = rospy.ServiceProxy('/qt_robot/emotion/show', srv.emotion_show) # New for emotion
        gesture_play_service = rospy.ServiceProxy('/qt_robot/gesture/play', gesture_play)
        
        rospy.loginfo("Speech services are available!")
        
    except rospy.ROSException as e:
        rospy.logerr(f"Failed to initialize ROS node or service proxy: {e}")
        sys.exit(1)

def gesture_for_mood(mood: str) -> str:
    
    mapping = {
    "happy": random.choices(['approval', 'QT/point_front', 'QT/swipe_left', 'QT/swipe_right'])[0],
    "sad": 'QT/sad', 
    "surprised":'QT/surprise', 
    "angry": 'QT/angry', 
    "scared":'QT/peekaboo', 
    "neutral": random.choices(['QT/neutral', 'QT/show_left', 'QT/show_right'])[0],
    }
    
    return mapping.get(mood, 'QT/neutral')

# New for gesture generation    
def _play_gesture_async(name: str):
    if gesture_play_service is None:
        rospy.logerr("Gestire service is not initialized.")
        return
    try:
        ges_resp = gesture_play_service(name, 0)
        
        if ges_resp.status:
            rospy.loginfo(f"Gesture service call was successful.{name}")
            gesture_play_service("QT/neutral", 0) # reset QT afterwards
        else:
            rospy.logwarn("Gesture service call failed.")
    except Exception as e:
        rospy.logwarn(f"Gesture Play Failed: {e}")

# New for gesture generation    
def _play_emotion_async(name: str):
    if emotion_show_service is None:
        rospy.logerr("Emotion service is not initialized.")
        return
    try:
        emo_resp = emotion_show_service(name)
        
        if  emo_resp.status:
            rospy.loginfo(f"Emotion service call was successful.{name}")
        else:
            rospy.logwarn("Emotion service call failed.")
    except Exception as e:
        rospy.logwarn(f"Emotion Show Failed: {e}")

def say_text_with_service(text: str, emotion: str):
    """
    Calls the QTrobot's speech service to make the robot speak.
    
    Args:
        text (str): The text message for the robot to speak.
    """
    global behavior_talkText_service, emotion_show_service, gesture_play_service
    if behavior_talkText_service is None:
        rospy.logerr("Speech service is not initialized. Call initialize_ros_node() first.")
        return
    #req = speech_sayRequest()
    #req.message = text
    req = srv.behavior_talk_textRequest() # Changed from speech_sayRequest
    req.message = text
    
    gesture_name = gesture_for_mood(emotion)
    emotion_name = f"QT/{emotion}"
    
    if gesture_name:
        threading.Thread(target=_play_gesture_async, args=(gesture_name,), daemon=True).start()
        
    if emotion_name:
        threading.Thread(target=_play_emotion_async, args=(emotion_name,), daemon=True).start()

    try:
        rospy.loginfo(f"Calling speech service with message: '{text}'")
        #resp = speech_say_service(req)
        
        # New for emotion    
        #emo_resp = emotion_show_service(emo_req)
        
        #if emo_resp.status:
            #rospy.loginfo("Emotion service call was successful.")
        #else:
            #rospy.logwarn("Emotion service call failed.")


        resp = behavior_talkText_service(req)
        
        if resp.status:
            rospy.loginfo("Speech service call was successful.")
        else:
            rospy.logwarn("Speech service call failed.")
         
    except rospy.ServiceException as e:
        rospy.logerr(f"Speech service call failed: {e}")


def configure_speech_speed(speed: int):
    """
    Configures the speech speed of the robot.
    
    Args:
        speed (int): The new speech speed as a percentage (e.g., 100).
    """
    if speech_config_service is None:
        rospy.logerr("Speech config service is not initialized.")
        return
    
    req = speech_configRequest()
    req.language = "" # Keep the default language
    req.pitch = 0     # Keep the default pitch
    req.speed = speed
    
    try:
        rospy.loginfo(f"Setting speech speed to {speed}...")
        resp = speech_config_service(req)
        
        if resp.status:
            rospy.loginfo(f"Speech speed set successfully to {speed}.")
        else:
            rospy.logwarn(f"Failed to set speech speed.")
    
    except rospy.ServiceException as e:
        rospy.logerr(f"Speech config service call failed: {e}")


if __name__ == '__main__':
    initialize_ros_node()

    # Set the speaking speed to a faster rate (e.g., 150%)
    configure_speech_speed(110)
    
    say_text_with_service("Hello. I am speaking at a faster speed now.")
    
    # You can set it back to normal speed later if needed
    # configure_speech_speed(100)
    # say_text_with_service("Now I am speaking at a normal speed again.")
    
    rospy.spin()

