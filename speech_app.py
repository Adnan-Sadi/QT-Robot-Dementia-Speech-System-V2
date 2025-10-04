#!/usr/bin/env python3
import os
import queue
import time
import rospy
import sys
from std_msgs.msg import Bool # Add this import at the top of your file

from google.cloud import speech
from google.api_core import exceptions as gexcp
from transformers import pipeline # new added for zero_shot emotion classifier

from qt_gesture_controller.srv import * # for gesture
from qt_robot_interface.srv import emotion_show, emotion_showRequest # for emotion
from qt_robot_interface import srv
import threading #new

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(script_dir, '/home/qtrobot/catkin_ws/src/dss_backend_connected')
    if module_dir not in sys.path:
        sys.path.append(module_dir)

    from src.speakout import initialize_ros_node, say_text_with_service, configure_speech_speed
    from src.vader_emotion import classify_emotion, zero_shot_classifier # new for emotion and gesture
    from src.backend_ws_client import BackendBridge

except ImportError as e:
    print(f"Error importing from module: {e}")


    
from std_msgs.msg import String
from audio_common_msgs.msg import AudioData
from qt_gspeech_app.srv import *


class MicrophoneStream(object):

    def __init__(self, buffer):
        self.stream_buff = buffer
        self.closed = True

    def __enter__(self):
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self.closed = True
        self.stream_buff.put(None)

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self.stream_buff.get()
            if chunk is None:
                return
            data = [chunk]
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self.stream_buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)



class QTrobotGoogleSpeech():
    """QTrobot speech recognition using google cloud service"""

    def __init__(self):
        self.listening_enabled = True # Keep this flag
        self.aqueue = queue.Queue(maxsize=2000) # more than one minute         
        self.audio_rate = rospy.get_param("/dss_backend_connected/audio_rate", 16000)
        self.language = rospy.get_param("/dss_backend_connected/default_language", 'en-US')
        self.model = rospy.get_param("/dss_backend_connected/model", 'default')
        self.use_enhanced_model = rospy.get_param("/dss_backend_connected/use_enhanced_model", True)
   
        self.emotion_classifier_pipeline = pipeline("zero-shot-classification", model="sileod/deberta-v3-base-tasksource-nli")
        
        print(f"audio rate:{self.audio_rate}, default language:{self.language}, model:{self.model}, use_enhanced_model:{self.use_enhanced_model}")

        # start recognize service
        self.speech_recognize = rospy.Service('/qt_robot/speech/recognize', speech_recognize, self.callback_recognize)        
        rospy.Subscriber('/qt_respeaker_app/channel0', AudioData, self.callback_audio_stream)
        
        self.backend = BackendBridge()
        self.backend.start()


    def callback_audio_stream(self, msg): 
        if self.listening_enabled:
            indata = bytes(msg.data)           
            try:
                self.aqueue.put_nowait(indata)            
            except:
                pass

    """
        ros speech recognize callback
    """
    def callback_recognize(self, req):
        print("options:", len(req.options), req.options)
        print("language:", req.language)
        print("timeout:", str(req.timeout))        
        # timeout = (req.timeout if (req.timeout != 0) else 15)
        timeout = req.timeout
        language = (req.language if (req.language != '') else self.language)
        language = language.replace("_", "-")
        options = list(filter(None, req.options)) # remove the empty options 
        # Manually clear the queue before recognizing
        self.aqueue.queue.clear()
        transcript = self.recognize_gspeech(timeout, options, language, True)
        if transcript:
            try:
                # --- Timing Point: Start LLM call ---
                llm_start_time = time.time()
                
                reply, _chunks = self.backend.send_text_blocking(transcript, collect_audio=False, timeout=25.0)
                
                # --- Timing Point: End LLM call ---
                llm_end_time = time.time()
                #emotion = classify_emotion(reply) # new for emotion and gesture
                emotion = zero_shot_classifier(self.emotion_classifier_pipeline, reply)
                print(f"🤖 Cognibot: {reply}")
                print(f"Emotion: {emotion}")
                    
                # --- Timing Point: Start ROS TTS call ---
                tts_start_time = time.time()
                say_text_with_service(reply, emotion.lower())
                # --- Timing Point: End ROS TTS call (Robot finished speaking) ---
                tts_end_time = time.time()


                print("----------------------")
            
            except Exception as e:
                print(f"[ERROR] Cognibot failed to respond: {e}")
        self.callback_recognize(speech_recognizeRequest())

        return speech_recognizeResponse(transcript)



    def contains_options(self, options, transcript):
        if not transcript:
            return None        
        for opt in options:
            opt = opt.strip()
            # do not split the transcript of an option contains more than a word such as 'blue color'
            phrase = transcript if (len(opt.split()) > 1) else transcript.split()
            if opt and opt in phrase:
                return opt
        return None


    def recognize_gspeech(self, timeout, options, language, clear_queue=False):        
        
        # clear queue (keep the last second)
        if clear_queue:                        
            # self.aqueue.queue.clear()
            # example : if audio rate is 16000 and respeaker buffersize is 512,then the last one second will be around 31 item in queue
            while self.aqueue.qsize() > int(self.audio_rate / 512 / 2):
                self.aqueue.get()


        # init google speech client
        self.client = speech.SpeechClient()

        answer_context = []
        speech_context = None
        if len(options) > 0:
            for option in options:
                if option.strip():
                    answer_context.append(option.lower().strip())
            speech_context = speech.SpeechContext(phrases = answer_context) if len(answer_context) else None
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.audio_rate,
                language_code=str(language.strip()),
                model=self.model,
                use_enhanced=self.use_enhanced_model,
                speech_contexts=[speech_context],
            )
        else:
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.audio_rate,
                model=self.model,
                use_enhanced=self.use_enhanced_model,
                language_code= str(language.strip()),
                enable_automatic_punctuation=True,
            )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False,
            enable_voice_activity_events=True, 
            )
        with MicrophoneStream(self.aqueue) as mic:
            start_time = time.time()
            audio_generator = mic.generator()
            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )
            try:
                if timeout > 0 :
                    responses = self.client.streaming_recognize(streaming_config, requests, timeout=timeout)
                else:
                    responses = self.client.streaming_recognize(streaming_config, requests)
                output = self.validate_response(responses, answer_context, start_time, timeout)
            except:
                output = ""
                print("exception")     

        print("Detected [%s]" % (output))
        return output


    """
        looping over google responses
    """
    def validate_response(self, responses, context, start_time, timeout):
        transcript = ""
        for response in responses:
            print(response)
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue
            transcript = result.alternatives[0].transcript
            print(f"Transcript: {transcript}")
            if not result.is_final:
                if context:
                    for option in context:
                        if option == transcript.lower().strip():
                            return transcript
            else:
                 return transcript
        return transcript
 
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
    
if __name__ == "__main__":
    initialize_ros_node()
    #rospy.init_node('qt_gspeech_app')  
    configure_speech_speed(110)
    
    gspeech = QTrobotGoogleSpeech() 
    rospy.wait_for_service('/qt_robot/gesture/play')
    gesture_play_service = rospy.ServiceProxy('/qt_robot/gesture/play', gesture_play) 
    threading.Thread(target=_play_gesture_async, args=("QT/happy",), daemon=True).start()
    
    rospy.wait_for_service('/qt_robot/emotion/show') # New for emotion
    emotion_show_service = rospy.ServiceProxy('/qt_robot/emotion/show', srv.emotion_show) # New for emotion
    emo_req = srv.emotion_showRequest()
    emo_req.name = f"QT/yawn" # New for emotion
    emotion_show_service(emo_req)
             
    rospy.loginfo("QT Speech App is Ready!")
    rospy.on_shutdown(lambda: gspeech.backend.stop())
    rospy.spin()
    rospy.loginfo("QT Speech App Shutdown")
