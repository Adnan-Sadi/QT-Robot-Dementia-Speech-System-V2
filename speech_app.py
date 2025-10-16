#!/usr/bin/env python3
import os
import queue
import time
import rospy
import sys

from google.cloud import speech

from qt_gesture_controller.srv import * # for gesture
from qt_robot_interface.srv import emotion_show, emotion_showRequest # for emotion
from qt_robot_interface import srv
import threading #new

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(script_dir, '/home/qtrobot/catkin_ws/src/dss_backend_connected')
    if module_dir not in sys.path:
        sys.path.append(module_dir)

    from src.speakout import initialize_ros_node, say_text_with_service, configure_speech_speed, _play_gesture_async
    # from src.vader_emotion import classify_emotion, zero_shot_classifier # new for emotion and gesture
    from src.backend_ws_client import BackendBridge

except ImportError as e:
    print(f"Error importing from module: {e}")


    
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
   
        
        print(f"audio rate:{self.audio_rate}, default language:{self.language}, model:{self.model}, use_enhanced_model:{self.use_enhanced_model}")

        # start recognize service
        self.speech_recognize_service = rospy.Service('/qt_robot/speech/recognize', speech_recognize, self.callback_recognize) # RENAMED LOCAL VAR
        rospy.Subscriber('/qt_respeaker_app/channel0', AudioData, self.callback_audio_stream)
        
        self.backend = BackendBridge()
        self.backend.start()

        # Service client for calling /qt_robot/speech/recognize
        rospy.wait_for_service('/qt_robot/speech/recognize')
        self.speech_recognize_client = rospy.ServiceProxy('/qt_robot/speech/recognize', speech_recognize)


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
        get_emotion = True
        if transcript:
            try:
                # --- Timing Point: Start LLM call ---
                llm_start_time = time.perf_counter()
                
                #backend returns both resposne and the emotion
                if get_emotion:
                    reply, emotion = self.backend.send_transcript_and_wait(transcript, timeout=25.0, get_emotion=get_emotion)
                else:
                    reply = self.backend.send_transcript_and_wait(transcript, timeout=25.0)
                
                # --- Timing Point: End LLM call ---
                llm_end_time = time.perf_counter()
                #emotion = classify_emotion(reply) # new for emotion and gesture
                print(f"Cognibot: {reply}")
                if get_emotion:
                    print(f"Emotion: {emotion}")
                print(f"Response Time: {llm_end_time-llm_start_time:.3f}s")
                    
                # --- Timing Point: Start ROS TTS call ---
                tts_start_time = time.time()
                if get_emotion:
                    say_text_with_service(reply, emotion.lower())
                else: 
                    say_text_with_service(reply, "neutral")
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
    
if __name__ == "__main__":
    initialize_ros_node()
    configure_speech_speed(110)
    
    gspeech = QTrobotGoogleSpeech() 
    
    # ... (gesture and emotion setup, same as before) ...
    rospy.wait_for_service('/qt_robot/gesture/play')
    gesture_play_service = rospy.ServiceProxy('/qt_robot/gesture/play', gesture_play) 
    threading.Thread(target=_play_gesture_async, args=("QT/happy",), daemon=True).start()
    
    rospy.wait_for_service('/qt_robot/emotion/show') 
    emotion_show_service = rospy.ServiceProxy('/qt_robot/emotion/show', srv.emotion_show)
    emo_req = srv.emotion_showRequest()
    emo_req.name = f"QT/yawn"
    emotion_show_service(emo_req)

    # Start the recognize service call in a new thread 
    
    def start_recognition_loop():
        """Function to be run in a separate thread to start the blocking service call."""
        rospy.loginfo("Starting QT Speech Recognition loop in a background thread...")
        req = speech_recognizeRequest() 
        try:
            # This call will block until ROS is shut down or an error occurs.
            gspeech.speech_recognize_client(req)
        except rospy.ServiceException as e:
            # Expect a ServiceException upon Ctrl+C/ROS shutdown.
            rospy.loginfo(f"Speech recognition service client terminated: {e}")
        except Exception as e:
            rospy.logerr(f"Unexpected error in recognition thread: {e}")

    # Start the thread with daemon=True so it doesn't prevent the main app from exiting
    # once the main thread (rospy.spin()) is terminated.
    threading.Thread(target=start_recognition_loop, daemon=True).start()
    
    # ------------------------------------------------------------------
             
    rospy.loginfo("QT Speech App is Ready! Press Ctrl+C to shut down.")
    rospy.on_shutdown(lambda: gspeech.backend.stop())
    
    # The main thread now runs rospy.spin(), which can handle the Ctrl+C signal.
    rospy.spin() 
    
    rospy.loginfo("QT Speech App Shutdown")
