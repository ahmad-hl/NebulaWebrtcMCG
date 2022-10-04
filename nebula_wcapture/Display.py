import cv2, time, pickle, socket, sys
from multiprocessing import Process
import os, csv,shutil
from util import PreTxUtility
from util.initializer import initialize_setting
from messages.MTPpacket import MTPpacket
from messages.vp8dec_display_data import VP8Dec2DisplayData

class DisplayProcess(Process):
    def __init__(self,in_queue, logger=None, fpslogger=None):
        super(DisplayProcess, self).__init__()
        self.in_queue = in_queue

        args = initialize_setting()
        # Init server address and socket for acknowledging frame delivery
        self.address = (args.server_ip, args.server_mtp_port)
        self.mtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if logger:
            self.logger = logger
        if fpslogger:
            self.fpslogger = fpslogger


    def __send(self, socket, message, address):
        # Convert str message to bytes on Python 3+
        if sys.version_info[0] > 2 and isinstance(message, str):
            message = bytes(message, 'utf-8')

        socket.sendto(message, address)

    def rescale_frame_1080p(self, frame):
        width = 1920
        height = 1080
        dim = (width, height)
        if frame.shape[1]< width:
            # print('DISPLAY: Frame {} is reshaped'.format(frame_no))
            return cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)
        else:
            # print('DISPLAY: Frame {} original'.format(frame_no))
            return frame

    def run(self):
        curr_frame_ptr = 0
        #init readers
        self.reader_1920_1080 = PreTxUtility.get_max_cv2reader()
        while True:
            # try:
            obj = self.in_queue.get()
            vp8_disp_data = pickle.loads(obj)

            itemstart = time.time()

            # framepsnr = self.computePSNR(vp8_disp_data.frame_no, vp8_disp_data.frame, curr_frame_ptr, vp8_disp_data)
            cv2.imshow('compressed', vp8_disp_data.frame)
            cv2.waitKey(1)
            # Send an MTP latency, PSNR response packet upon frame playback at client
            mtpPacket = MTPpacket(vp8_disp_data.frame_no, vp8_disp_data.frame_sent_ts, 1)
            obj = pickle.dumps(mtpPacket)
            self.__send(self.mtp_socket, obj, self.address)


            req_time = (time.time() - itemstart) * 1000
            self.logger.info("display, {}, {}".format(vp8_disp_data.frame_no, req_time))
            # self.fpslogger.info("{},{},{}".format(second, vp8_disp_data.frame_no, req_time))






