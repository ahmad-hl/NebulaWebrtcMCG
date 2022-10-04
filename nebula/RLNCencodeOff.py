import math, time
from datetime import datetime
import numpy as np
from multiprocessing import Process
from queue import Queue
from util.initializer import initialize_setting
from util import PreTxUtility
from messages.FRTPpacket import FRTPpacket
from util.senderSock import SenderSock
import kodo
import threading, socket
import pickle
from statistics import mean

#ffmpeg -i output.mkv -c:v libvpx -r 30 -s hd1080 -b:v 10000k  output.mp4
class RLNCencodeOffProcess(Process):
    def __init__(self, rtt_queue, user_event_queue,  logger=None, MTPlogger = None, BWlogger = None, is_localhost=False):
        super(RLNCencodeOffProcess, self).__init__()
        self.args = initialize_setting()

        self.snderSock = SenderSock(is_localhost)

        self.rtt_queue = rtt_queue
        self.user_event_queue = user_event_queue

        # *** Performance Logging ****
        if logger:
            self.logger = logger
        if MTPlogger:
            self.MTPlogger = MTPlogger
        if BWlogger:
            self.BWlogger = BWlogger

        self.sync_ack_queue = Queue(maxsize=1)
        self.bw_list = []


    def parameter_tune(self, frame_no, qlevel, currRTT, bw, readers, bitrates):
        readers_len = len(readers)

        if frame_no % 10 == 0:

            # Tune source rate
            ruleRTT = max(currRTT, 0.4)
            ruleRTT = 1- min(ruleRTT, 0.7)

            print("currRTT = {}, ruleRTT = {}".format(currRTT, ruleRTT))
            for ind in range(readers_len):
                if ( (bitrates[ind] )  >  bw * ruleRTT ) and (ind>0): # 70% of bw +redundancyRatek
                    qlevel = ind-1
                    break
                else:
                    qlevel = ind

        frame = readers[qlevel].get_next_frame()
        sourcerate = bitrates[qlevel]
        for i in range(readers_len):
            if i != qlevel:
                readers[i].get_next_frame()

        return frame, qlevel, sourcerate

    def run(self):

        # Thread to receive Performance parameters from client
        clParamsThrd = ClientParamsReceiverThread(self.sync_ack_queue)
        clParamsThrd.start()

        # MTP latency Receiver and Compute Thread
        self.mtppReceiverThread = MTPReceiverThread(self.MTPlogger)
        self.mtppReceiverThread.daemon = True
        self.mtppReceiverThread.start()

        start = time.time()
        rttList = [0.05]
        now = datetime.now()
        second_no = int('%i%i' % (now.minute, now.second))
        frame_no = 0
        fps = 30

        readers, bitrates = PreTxUtility.get_readers()
        qualityLevel = 8
        clientBw = 200000 #bitrates[qualityLevel]
        numframes = readers[0].nFrames

        symbol_size = self.args.symbol_size

        while frame_no < numframes:
            time.sleep(1/fps)

            currRTT = mean(rttList)
            if frame_no % 10 == 0:
                try:
                    recievedRTT  = self.rtt_queue.get_nowait()
                    rttList.append(recievedRTT)
                    currRTT = np.mean(rttList)
                    if len(rttList)>5:
                        rttList.pop(0)
                    # print(' Current RTT is UPDATED to {}'.format(currRTT))
                except Exception as exp:
                    # print(' Current RTT {}, no elements.., exception {}'.format(currRTT, exp))
                    pass


            #read and dump
            frame,qualityLevel,sourceRate = self.parameter_tune(frame_no, qualityLevel,currRTT, clientBw, readers, bitrates)
            # frame = reader.get_next_frame()

            itemstart = time.time()
            if time.time() - start > 1:
                start = time.time()
                now = datetime.now()
                second_no = int('%i%i' % (now.minute, now.second))


            # compute symbols based on frame and symbol_size
            data_in = bytearray(frame.framedata)

            symbols = float(len(data_in)) / symbol_size
            symbols = int(math.ceil(symbols))

            # setup kodo encoder & send settings to server side
            encoder = kodo.RLNCEncoder(
                field=kodo.field.binary8,
                symbols=symbols,
                symbol_size=symbol_size)
            encoder.set_symbols_storage(data_in)

            packet_number = 0

            # No FEC
            total_packets = symbols
            # total_packets = max(symbols + 1, 0) #math.ceil(symbols * (1 + clientPLR))


            # Get network parameters from client
            try:
                netparams = self.sync_ack_queue.get_nowait()
                if netparams.plr == netparams.plr:
                    clientPLR = netparams.plr  # np.max(clientPLRlist)

                if netparams.bw == netparams.bw:
                    clientBw = netparams.bw  # PreTxUtility.average_bw_list(min(netparams.bw, 8000))  # np.mean(clientBWlist) - np.std(clientBWlist)

            except Exception:
                pass

            while packet_number < total_packets:
                packet_number += 1
                packet = encoder.produce_payload()
                curr_timestamp = time.time()
                frtpPkt = FRTPpacket(packet_number, frame_no, symbols, curr_timestamp, payload=packet)
                self.snderSock.sendFRTPpacket(frtpPkt)

            time_end = time.time()
            req_time = (time_end - itemstart) * 1000
            # process rlnc encode, frame number, time (ms)
            self.logger.info("rlncenc, {}, {}".format(frame_no, req_time))
            # station, frame no, timestamp
            self.MTPlogger.info("send, {}, {}".format(frame_no, time_end ))

            seconds = math.ceil(time.mktime(datetime.today().timetuple()))
            if sourceRate:
                self.BWlogger.info("{}, {}, {}, {}, {}".format(second_no, frame_no, seconds, clientBw, sourceRate))

            frame_no += 1

class ClientParamsReceiverThread(threading.Thread):

    def __init__(self, sync_ack_queue):
        super(ClientParamsReceiverThread, self).__init__()
        self.sync_ack_queue = sync_ack_queue
        self.args = initialize_setting()
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.control_socket.bind((self.args.server_ip, self.args.server_control_port))
        print('feedback socket info {} , {}'.format(self.args.server_ip, self.args.server_control_port))

    def stop(self):
        self.control_socket.close()

    def update_queue(self, netparams):
        # Refresh queue data
        try:
            if self.sync_ack_queue.full():
                try:
                    self.sync_ack_queue.get_nowait()
                except:
                    pass

            self.sync_ack_queue.put(netparams)
        except:
            pass

    def run(self):
        while True:
            # receive Client's Network Parameters
            obj = self.control_socket.recv(1024)
            netparams = pickle.loads(obj)
            self.update_queue(netparams)

            try:
                print("Client Network Parameters: bw {:.0f}, plr {:.4f}!".format(netparams.bw,netparams.plr))
            except:
                print('exceptiopn')
                pass

#Motion-to-photon receiving Thread
class MTPReceiverThread(threading.Thread):

    def __init__(self, MTPlogger = None):
        super(MTPReceiverThread, self).__init__()
        self.MTPlogger = MTPlogger

        args = initialize_setting()
        self.mtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mtp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.mtp_socket.bind((args.server_ip, args.server_mtp_port))
        print('Established server MTP socket {} , {} ..'.format(args.server_ip, args.server_mtp_port))

    def run(self):
        mtp_list = []

        while True:
            # Receive an frame MTP latency response packet
            obj, address = self.mtp_socket.recvfrom(1024)
            mtpPacket = pickle.loads(obj)

            # compute the difference as mtp
            mtp = time.time() - mtpPacket.sent_ts
            mtp_list.append(mtp)
            seconds = math.ceil(time.mktime(datetime.today().timetuple()))
            if self.MTPlogger:
                self.MTPlogger.info("{}, {}, {}, {}".format(seconds, mtpPacket.frame_no, mtp, mtpPacket.psnr))
            print("motion-to-photon latency {} and psnr {} of frame {}".format(mtp * 1000, mtpPacket.psnr, mtpPacket.frame_no))
