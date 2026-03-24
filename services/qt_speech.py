import queue
import time
import traceback
import rospy
from audio_common_msgs.msg import AudioData
from qt_robot_interface import srv

from services.backend_client import BackendBridge
from services.gspeech_recognizer import GSpeechRecognizer
from speakout import say_text_with_service
from config.settings import settings


class QTrobotSpeech:
    """QTrobot speech recognition — supports gspeech and vosk backends."""

    def __init__(self, speech_recognize_cls, speech_recognizeResponse_cls):
        self.listening_enabled = True
        self.stt_engine = settings.STT_ENGINE
        self.speech_recognize_service = None
        self._recognizer = None

        if self.stt_engine == "gspeech":
            self._setup_gspeech(speech_recognize_cls, speech_recognizeResponse_cls)
        else:
            rospy.loginfo("STT engine: vosk. Using external /qt_robot/speech/recognize service.")

        # Initialize the backend bridge and start it
        self.backend = BackendBridge()
        self.backend.start()

        # Wait for the speech recognize service to be available
        rospy.wait_for_service('/qt_robot/speech/recognize')
        self.speech_recognize_client = rospy.ServiceProxy('/qt_robot/speech/recognize', speech_recognize_cls)

        # Set up emotion service proxies
        rospy.wait_for_service('/qt_robot/emotion/stop')
        self.emotion_stop_client = rospy.ServiceProxy('/qt_robot/emotion/stop', srv.emotion_stop)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_gspeech(self, speech_recognize_cls, speech_recognizeResponse_cls):
        self._speech_recognizeResponse = speech_recognizeResponse_cls
        self.aqueue = queue.Queue(maxsize=2000)
        self.language = rospy.get_param("/dss_backend_connected/default_language", settings.DEFAULT_LANGUAGE)

        audio_rate = rospy.get_param("/dss_backend_connected/audio_rate", settings.AUDIO_RATE)
        model = rospy.get_param("/dss_backend_connected/model", settings.SPEECH_MODEL)
        use_enhanced = rospy.get_param("/dss_backend_connected/use_enhanced_model", settings.USE_ENHANCED_MODEL)

        print(
            f"STT engine:{self.stt_engine}, "
            f"audio rate:{audio_rate}, "
            f"default language:{self.language}, "
            f"model:{model}, "
            f"use_enhanced_model:{use_enhanced}"
        )

        self._recognizer = GSpeechRecognizer(audio_rate, self.language, model, use_enhanced, self.aqueue)

        self.speech_recognize_service = rospy.Service(
            '/qt_robot/speech/recognize',
            speech_recognize_cls,
            self.callback_recognize
        )
        rospy.Subscriber('/qt_respeaker_app/channel0', AudioData, self.callback_audio_stream)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

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
        language = (req.language if req.language != '' else self.language)
        language = language.replace("_", "-")
        options = list(filter(None, req.options)) # remove the empty options

        # Manually clear the queue before recognizing
        self.aqueue.queue.clear()
        transcript = self._recognizer.recognize(timeout, options, language, clear_queue=True)

        # Set-up variables for the "thinking" emotion
        #EMOTION_THINKING = "QT/confused"
        #emotion_stop_service = self.emotion_stop_client
        #emo_req = srv.emotion_showRequest()

        return self._speech_recognizeResponse(transcript)

    # ------------------------------------------------------------------
    # Core transcript processing
    # ------------------------------------------------------------------

    def process_transcript(self, transcript: str):
        if not transcript:
            return

        try:
            llm_start_time = time.perf_counter()

            response_text, response_emotion, current_scenario, next_scenario = self.backend.send_transcript_and_wait(
                transcript,
                emotion=None,
                timeout=settings.LLM_TIMEOUT
            )

            llm_end_time = time.perf_counter()

            print(f"Cognibot: {response_text}")
            print(f"Emotion: {response_emotion}")
            if current_scenario:
                print(f"Current Scenario: {current_scenario}")
            if next_scenario:
                print(f"Next Scenario: {next_scenario}")
            print(f"Response Time: {llm_end_time-llm_start_time:.3f}s")

            emotion_to_show = response_emotion.lower() if response_emotion else "neutral"
            say_text_with_service(response_text, emotion_to_show)

            print("----------------------")

        except Exception as e:
            print(f"[ERROR] Cognibot failed to respond: {repr(e)}")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def contains_options(self, options, transcript):
        if not transcript:
            return None
        for opt in options:
            opt = opt.strip()
            # do not split the transcript if an option contains more than a word such as 'blue color'
            phrase = transcript if (len(opt.split()) > 1) else transcript.split()
            if opt and opt in phrase:
                return opt
        return None