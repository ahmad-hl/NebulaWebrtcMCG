import time, ctypes, pickle, socket
import numpy as np
from util import yuv2
from multiprocessing import Process
from util.wrapper import Decoder, VPXFRAMEDATA
from messages.vp8dec_display_data import VP8Dec2DisplayData
import cv2, os
from util import PreTxUtility
from util.initializer import initialize_setting

class VP8decodeProcess(Process):
    def __init__(self,in_queue, out_queue, logger=None, event_logger=None):
        super(VP8decodeProcess, self).__init__()
        self.in_queue = in_queue
        self.out_queue = out_queue

        if logger:
            self.logger = logger
        if event_logger:
            self.event_logger = event_logger

        self.reader_1920_1080 = PreTxUtility.get_max_cv2reader()

        args = initialize_setting()
        # Init server address and socket for acknowledging frame delivery
        self.address = (args.server_ip, args.server_mtp_port)
        self.mtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

    def computePSNR(self, frame_no, compressed_frame, curr_frame_ptr, vp8_disp_data =None):

        # Loading images (original image and compressed image)
        while curr_frame_ptr <= frame_no:
            print("frame_no {}, curr frame ptr {}".format(frame_no, curr_frame_ptr))
            success, original_1920_1080 = self.reader_1920_1080.read()
            curr_frame_ptr += 1

        if success:
            original = original_1920_1080
            framepsnr = cv2.PSNR(original, compressed_frame)
            # cv2.imshow('original', original)
            # cv2.imshow('compressed', compressed_frame)
            # cv2.waitKey(1)
        else:
            framepsnr = 1

        return framepsnr

    def run(self):
        dec = Decoder()
        do_decoding = False
        ignored_Pframes = 0

        while True:

            try:
                #enqueue frame data
                obj = self.in_queue.get()

                # Start the timer
                itemstart = time.time()

                #Decode the frame using VP8
                rlnc_vp8_data = pickle.loads(obj)
                pkt = np.frombuffer(rlnc_vp8_data.data_out, dtype=np.uint8)

                if ~do_decoding and (pkt[0] & 1) == 0:              # If it is Key Frame (I-Frame), start decoding
                    do_decoding = True

                if do_decoding:
                    try:
                        # Decode the frame
                        vpdata = VPXFRAMEDATA()
                        vpdata.buf = pkt.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
                        vpdata.len = len(pkt)
                        fr = dec.decode_frame_to_buf(vpdata.buf, vpdata.len)

                        if fr.len > 0:
                            ret, frame = yuv2.read(fr.buf, fr.width, fr.height)
                            if ret:
                                #Scale and display frame
                                rescaled_frame = self.rescale_frame_1080p(frame)
                                vp8_disp_data = VP8Dec2DisplayData(rlnc_vp8_data.frame_no,  rescaled_frame, rlnc_vp8_data.frame_sent_ts)
                                obj = pickle.dumps(vp8_disp_data)
                                self.out_queue.put(obj)

                            dec.free_data(fr)
                            #log frame encoding time
                            req_time = (time.time()  - itemstart) * 1000
                            self.logger.info("vp8dec, {}, {}".format(rlnc_vp8_data.frame_no, req_time))
                    except:
                        try:
                            print('Exception in actual decoding....')
                        except:
                            pass
                        dec = Decoder()
                        pass
                else:
                    ignored_Pframes += 1
                    print("Failed to decode as first frame is P-frame: #{}".format(ignored_Pframes))

            except:
                pass


