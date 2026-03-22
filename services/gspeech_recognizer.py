import time
import random
import rospy
from qt_robot_interface import srv
from services.audio_stream import MicrophoneStream
from config.settings import settings


class GSpeechRecognizer:
    """Handles Google Cloud streaming speech recognition."""

    def __init__(self, audio_rate, language, model, use_enhanced_model, aqueue):
        self.audio_rate = audio_rate
        self.language = language
        self.model = model
        self.use_enhanced_model = use_enhanced_model
        self.aqueue = aqueue
        self.client = None

    def recognize(self, timeout, options, language, clear_queue=False):
        # importing google speech client here to avoid unnecessary import and potential issues on QTrobot if not using gspeech as STT backend
        from google.cloud import speech

        # clear queue (keep the last second)
        if clear_queue:
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
            speech_context = speech.SpeechContext(phrases=answer_context) if len(answer_context) else None
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
                language_code=str(language.strip()),
                enable_automatic_punctuation=True,
            )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
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
                if timeout > 0:
                    responses = self.client.streaming_recognize(streaming_config, requests, timeout=timeout)
                else:
                    responses = self.client.streaming_recognize(streaming_config, requests)
                output = self._validate_response(responses, answer_context, start_time, timeout)
            except:
                output = ""
                print("exception")

        return output

    """
        looping over google responses
    """
    def _validate_response(self, responses, context, start_time, timeout):
        transcript = ""
        listening_emotion_played = False
        listening_emotion_list = settings.EMOTION_LISTENING
        EMOTION_LISTENING = random.choices(listening_emotion_list)[0] # Example: A simple blink or nod to show attention

        # Get the emotion service proxy (assuming it's available or set up here/globally)
        emotion_show_service = rospy.ServiceProxy('/qt_robot/emotion/show', srv.emotion_show)
        emo_req = srv.emotion_showRequest()

        for response in responses:
            # Check for the end of the stream or empty results
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript

            # --- NEW: Immediate Feedback Emotion Logic ---
            if not result.is_final and not listening_emotion_played and transcript.strip():
                # First time we see a non-empty, non-final transcript, play the listening emotion
                emo_req.name = EMOTION_LISTENING
                emotion_show_service(emo_req)
                print(f"Robot started listening emotion: {EMOTION_LISTENING}")
                listening_emotion_played = True

            # If we get a FINAL result, break and return it
            if result.is_final:
                print(f"Transcript: {transcript}")
                return transcript

            # If context is provided (for command/option matching), check against interim results
            if context:
                for option in context:
                    if option == transcript.lower().strip():
                        print(f"Transcript: {transcript}")
                        return transcript

        print(f"Transcript: {transcript}")
        return transcript