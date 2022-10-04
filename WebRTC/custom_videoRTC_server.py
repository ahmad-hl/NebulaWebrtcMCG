import time, cv2
from av import VideoFrame
from vidgear.gears.asyncio.helper import reducer
from vidgear.gears import ScreenGear, CamGear
from aiortc import VideoStreamTrack


# create your own Bare-Minimum Custom Media Server
class CustomVideoRTCServer(VideoStreamTrack):
    """
    Custom Media Server using OpenCV, an inherit-class
    to aiortc's VideoStreamTrack.
    """

    def __init__(self,  render_logger=None, source=None):

        # don't forget this line!
        super().__init__()

        # Media source: live video stream on webcam at first index(i.e. 0)
        if (source != None) and (source == 0):
            options = {
                "CAP_PROP_FRAME_WIDTH": 1920,
                "CAP_PROP_FRAME_HEIGHT": 1080,
                "CAP_PROP_FPS": 30,
            }
            self.stream = CamGear(source=source, logging=True, **options).start()

        # open any valid video stream(for e.g `myvideo.avi` file)
        elif source == 1:
            self.stream = CamGear(source="../inout_data/hq4.mp4").start()
            print('source is offline video: {}, url {}'.format(source, "../inout_data/hq4.mp4"))

        # YouTube Video URL as input source and enable Stream Mode (`stream_mode = True`)
        elif source == 2:
            options = {"STREAM_RESOLUTION": "1080p"}
            self.stream = CamGear(
                source="https://youtu.be/bvetuLwJIkA", stream_mode=True, logging=True, **options).start()

        # Media source: screen sharing
        else:
            options = {"top": 0, "left": 0, "width": 1920, "height": 1080, "resolution": (1920, 1080),
                       "cap_prop_fps": 30}  # 1280 x 720, 1920 x 1080
            self.stream = ScreenGear(logging=True, **options).start()

        if render_logger:
            self.render_logger = render_logger

        # other parameters
        self.frame_no = 0
        # self.start_ts = time.time()
        # self.fps = 0

    async def recv(self):
        """
        A coroutine function that yields `av.frame.Frame`.
        """
        start = time.time()
        pts, time_base = await self.next_timestamp()

        # read video frame
        frame = self.stream.read()
        # check for frame if Nonetype
        if frame is None:
            self.terminate()

        # if time.time() - self.start_ts > 1:
            # print("FPS {} Frame {} at {} pts {}".format(self.fps, self.frame_no, time.time()*1000, pts))
            # self.fps = 0
            # self.start_ts = time.time()

        # reducer frames size if you want more performance otherwise comment this line
        # frame = await reducer(frame, percentage=50)  # reduce frame by 30%

        # contruct `av.frame.Frame` from `numpy.nd.array`
        av_frame = VideoFrame.from_ndarray(frame,  format="bgr24")
        av_frame.pts = pts
        av_frame.time_base = time_base
        # print("Frameno: {}, Timebase: {}, PTS: {}".format(self.frame_no , time_base, pts))
        self.render_logger.info("{},{},{},{},{}".format(self.frame_no, (time.time()-start) * 1000, time_base, pts, start*1000))
        self.frame_no += 1
        # self.fps += 1

        # return `av.frame.Frame`
        return av_frame

    def terminate(self):
        """
        Gracefully terminates VideoGear stream
        """
        # don't forget this function!!!

        # terminate
        if not (self.stream is None):
            self.stream.release()
            self.stream = None