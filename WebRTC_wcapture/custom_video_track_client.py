import time, sys
import cv2, os
import numpy as np
from av import VideoFrame
from aiortc import MediaStreamTrack
from util import PreTxUtility


ROOT = os.path.dirname(__file__)

class CustomVideoTrackRTClient(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"

    def __init__(self, track, disp_logger=None, bw_logger=None):
        super().__init__()  # don't forget this!
        self.track = track
        self.frame_no = 0
        self.last_pts = 0
        self.disp_logger = disp_logger
        self.bw_logger = bw_logger
        # init readers
        self.reader_1920_1080 = PreTxUtility.get_max_cv2reader()
        self.framepsnr_dict = {}
        self.start = time.time()

        #Throughput statistics
        self.bytes_received = 0
        self.throughput_in_mbit = 1

    async def recv(self):
        frame = await self.track.recv()
        try:
            start =time.time()
            img = frame.to_ndarray(format="bgr24")
            rows, cols, _ = img.shape
            image = np.array(img)

            # rebuild a VideoFrame, preserving timing information
            new_frame = VideoFrame.from_ndarray( image, format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            print("recv: Video Frame Conversion {} received".format(self.frame_no))

            #Compute PSNR by presentation time (pts)
            self.disp_logger.info("{},{},{},{}".format(self.frame_no, (time.time()-start)*1000, frame.time_base, frame.pts))
            self.frame_no += 1
            self.last_pts = frame.pts

            #Compute WebRTC throughput
            self.bytes_received += sys.getsizeof(frame)
            if time.time() - self.start > 1:
                self.throughput_in_mbit = self.bytes_received * 8/1024/1024
                self.bytes_received = 0
                self.start = time.time()
            self.bw_logger.info(
                "{},{},{}".format(round(time.time()), self.frame_no, self.throughput_in_mbit))

            cv2.imshow("WebRTC",image)
            cv2.waitKey(1)
            return new_frame


        except Exception as ex:
            print(ex)
            cv2.destroyAllWindows()
            pass

        self.frame_no += 1

        return frame