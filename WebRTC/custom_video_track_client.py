import pickle
import time, sys
import cv2, os, socket
import numpy as np
from av import VideoFrame
from aiortc import MediaStreamTrack
from util import PreTxUtility
from util.initializer import initialize_setting

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
        self.start = time.time()

        self.args = initialize_setting()
        #Throughput statistics
        self.bytes_received = 0
        self.throughput_in_mbit = 1
        # self.tx1 = self.get_bytes('tx')
        self.rx1 = self.get_bytes('rx')

        parentDir = os.path.dirname(os.path.realpath(__file__))
        psnr_log_path = os.path.join(parentDir, '..', 'inout_data', 'webrtc_psnr.log')
        self.log_psnr_file = open(psnr_log_path, 'w')

    def computePSNRbyPTS(self, compressed_frame, frame_pts):
        # Loading images (original image and compressed image)
        success, original_1920_1080 = self.reader_1920_1080.read()
        if self.last_pts - frame_pts > 3000:
            #next frame fits better
            success, original_1920_1080 = self.reader_1920_1080.read()
            # log frame_no, PSNR
            self.log_psnr_file.write(str(self.frame_no) + '\t' + str(1) + '\n')
            self.log_psnr_file.flush()
            self.frame_no += 1


        if success:
            original = original_1920_1080
            framepsnr = cv2.PSNR(original, compressed_frame)
            # cv2.imshow('original', original)
            # self.show_user_event( compressed_frame, vp8_disp_data)
            cv2.imshow('compressed', compressed_frame)
            cv2.waitKey(1)
        else:
            framepsnr = 1

        # log frame_no, PSNR
        self.log_psnr_file.write(str(self.frame_no) + '\t' + str(framepsnr) + '\n')
        self.log_psnr_file.flush()


    def get_bytes(self, t):
        with open('/sys/class/net/' + self.args.client_if + '/statistics/' + t + '_bytes', 'r') as f:
            data = f.read();
            return int(data)


    def __send(self, socket, message, address):
        if sys.version_info[0] > 2 and isinstance(message, str):
            message = bytes(message, 'utf-8')

        socket.sendto(message, address)

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
            self.computePSNRbyPTS(image, frame.pts)
            self.disp_logger.info("{},{},{},{},{}".format(self.frame_no, (time.time()-start)*1000, frame.time_base, frame.pts, time.time()*1000))
            self.frame_no += 1
            self.last_pts = frame.pts

            #Compute WebRTC throughput
            self.bytes_received += sys.getsizeof(frame)
            if time.time() - self.start > 1:
                self.throughput_in_mbit = self.bytes_received * 8/1024/1024
                self.bytes_received = 0
                self.start = time.time()
                rx2 = self.get_bytes('rx')
                self.throughput_in_mbit = round((rx2 - self.rx1) *8 / 1024.0, 4)
                self.rx1 = rx2
            self.bw_logger.info(
                "{},{},{}".format(round(time.time()), self.frame_no, self.throughput_in_mbit))

            # cv2.imshow("frame",image)
            # cv2.waitKey(1)
            return new_frame


        except Exception as ex:
            print(ex)
            cv2.destroyAllWindows()
            pass

        self.frame_no += 1

        return frame