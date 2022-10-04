from multiprocessing import Process, Queue
from util.initializer import initialize_setting
from messages.FRTPpacket import FRTPpacket
from util.senderSock import SenderSock
import kodo
import pickle, time, datetime, math
from util.senderSock import SenderSock
import threading, socket


class RLNCencodeProcess(Process):
    def __init__(self, in_queue,  logger=None, MTPlogger = None, Overheadlogger=None, FEClogger=None, is_localhost=False):
        super(RLNCencodeProcess, self).__init__()
        self.in_queue = in_queue
        args = initialize_setting()
        self.settings = vars(args)

        self.snderSock = SenderSock(is_localhost)

        if logger:
            self.logger = logger
        if MTPlogger:
            self.MTPlogger = MTPlogger
        if Overheadlogger:
            self.Overheadlogger = Overheadlogger
        if FEClogger:
            self.FEClogger = FEClogger

        self.sync_ack_queue = Queue(maxsize=1)


    def run(self):

        # MTP latency Receiver and Compute Thread
        self.mtppReceiverThread = MTPReceiverThread(self.MTPlogger)
        self.mtppReceiverThread.daemon = True
        self.mtppReceiverThread.start()

        clientPLR = 0
        now = datetime.datetime.now()
        start = time.time()
        second_no = int('%i%i' % (now.minute, now.second))

        while True:

            # restart the time evrey second
            itemstart = time.time()
            if time.time() - start > 1:
                start = time.time()
                now = datetime.datetime.now()
                second_no = int('%i%i' % (now.minute, now.second))

            #Get vp8 encoded frame
            obj = self.in_queue.get()
            vp8enc_rlnc_data = pickle.loads(obj)
            frame = vp8enc_rlnc_data.frame

            # compute symbols based on frame and symbol_size
            data_in = bytearray(frame)
            symbol_size = self.settings['symbol_size']
            symbols = float(len(data_in)) / symbol_size
            symbols = int(math.ceil(symbols))

            # setup kodo encoder & send settings to server side
            encoder = kodo.RLNCEncoder(
                field=kodo.field.binary8,
                symbols=symbols,
                symbol_size=symbol_size)
            encoder.set_symbols_storage(data_in)

            # to enable AFEC, uncomment the following 2 lines
            fw = 1 #0.3 * (10 - vp8enc_rlnc_data.frame_no % 10)
            total_packets = symbols #max(symbols +1, math.ceil(symbols  * (1+  clientPLR *fw  )))
            packet_number = 0
            while packet_number < total_packets:
                packet_number += 1
                packet = encoder.produce_payload()
                curr_timestamp = time.time()
                frtpPkt = FRTPpacket(packet_number, vp8enc_rlnc_data.frame_no, symbols, curr_timestamp, payload=packet)
                self.snderSock.sendFRTPpacket(frtpPkt)


            # check if client network parameters are received
            # try:
            #     netparams = self.sync_ack_queue.get_nowait()
            #     print(" Consumed Parameters".format(netparams))
            #     if netparams.plr == netparams.plr:
            #         clientPLR = netparams.plr  # np.max(clientPLRlist)
            #
            #     if netparams.bw == netparams.bw:
            #         clientBw = netparams.bw  # PreTxUtility.average_bw_list(min(netparams.bw, 8000))  # np.mean(clientBWlist) - np.std(clientBWlist)
            #
            # except Exception:
            #     pass

            time_end = time.time()
            req_time = (time_end - itemstart) *1000
            # process rlnc encode, frame number, time (ms)
            self.logger.info("rlncenc, {}, {}".format(vp8enc_rlnc_data.frame_no, req_time))
            # station, frame no, timestamp
            self.MTPlogger.info("server, {}, {}".format(vp8enc_rlnc_data.frame_no, time_end))
            # second no, n , k, PLR
            seconds = math.ceil(time.mktime(datetime.datetime.today().timetuple()))
            self.Overheadlogger.info(
                "{}, {}, {}, {}, {}, {}".format(second_no, vp8enc_rlnc_data.frame_no, seconds, packet_number, symbols, clientPLR))
            # if sourceRate:
            #     self.BWlogger.info(
            #         "{}, {}, {}, {}, {}, {}, {}, {}".format(second_no, frame_no, seconds, clientBw, sourceRate,
            #                                                     1, redundancyRate, packet_number - symbols))
            print("RLNCenc: frame {}, time {}".format(vp8enc_rlnc_data.frame_no, req_time))



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
        while True:
            # Receive an frame MTP latency response packet
            obj, address = self.mtp_socket.recvfrom(1024)
            mtpPacket = pickle.loads(obj)

            # compute the difference as mtp
            if self.MTPlogger:
                self.MTPlogger.info("{}, {}, {}, {}".format('client', mtpPacket.frame_no, mtpPacket.sent_ts, mtpPacket.psnr))
            print("sent time {} and psnr {} of frame {}".format(mtpPacket.sent_ts, mtpPacket.psnr, mtpPacket.frame_no))
