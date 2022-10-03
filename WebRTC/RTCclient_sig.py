import argparse, asyncio, logging, time, cv2, os, socket, json
from custom_video_track_client import CustomVideoTrackRTClient
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from aiortc import RTCIceCandidate, MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from multiprocessing import Manager
import b64coder
import struct
from util.initializer import initialize_setting

pcs = set()

async def run(pc, recorder, signaling, servsocket, disp_logger, rtt_logger, bw_logger):
    pcs.add(pc)
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is {}".format(pc.connectionState))
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            print("Audio Track %s received", track.kind)
        elif track.kind == "video":
            print("RUN: Video Track {} received".format(track.kind))
            local_track = CustomVideoTrackRTClient(track, disp_logger, bw_logger)
            pc.addTrack(local_track)
            if recorder != None:
                recorder.addTrack(local_track)

        @track.on("ended")
        async def on_ended():
            print("Track %s ended", track.kind)
            if recorder != None:
                await recorder.stop()

    # Data Channel for user interaction
    channel = pc.createDataChannel("RTT")
    print("channel(%s) %s" % (channel.label, "created by local party"))

    async def send_pings():
        while True:
            print("channel(%s) %s" % (channel.label, "ping %f" % time.time()))
            channel.send("ping %f" % time.time())
            await asyncio.sleep(1)

    @channel.on("open")
    def on_open():
        asyncio.ensure_future(send_pings())

    @channel.on("message")
    def on_message(message):
        print("channel(%s) %s" % (channel.label, message))

        if isinstance(message, str) and message.startswith("pong"):
            ts_list = message[5:].split(",")
            elapsed_ms = (time.time() - float(ts_list[0])) * 1000
            rtt_logger.info("{},{:.3f},{}".format(round(time.time()),elapsed_ms,message[5:]))
            # pang reply
            reply = "pang %s" % message[5:]+ ",%f" % time.time()
            channel.send(reply)


    #Exchange offer answer
    await exchange_offer_answer(pc, servsocket)

    if recorder != None:
        await recorder.start()

    # connect signaling
    await signaling.connect()

    # Consume signaling for webrtc streaming
    await consume_signaling(signaling)

async def consume_signaling( signaling ):
    while True:
        obj = await signaling.receive()
        if isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
            print("ICE {} is established in Client".format(obj))
        elif obj is BYE:
            print("Exiting")
            break

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def send_offer(servsocket,pc):
    offer_json_obj = {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}
    print("offer >>> {}".format(offer_json_obj))
    b64encoded = b64coder.json_b64encode(offer_json_obj)
    offer_size = struct.pack("L",len(b64encoded))
    servsocket.sendall( offer_size + b64encoded)

def receive_answer(servsocket):
    metadata_size = struct.calcsize("L")
    answer_size_metadata = servsocket.recv(metadata_size)
    answer_size = struct.unpack("L", answer_size_metadata)
    # print(" Answer Size: {}, {}".format(answer_size, answer_size[0]))
    server_answer_json = recvall(servsocket, answer_size[0])
    answer = b64coder.b64decode(server_answer_json)
    print(" answer <<< {}".format(answer))

    return answer

async def exchange_offer_answer(pc, servsocket):
    #create & send offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    send_offer(servsocket, pc)

    #receive & set answer
    answer = receive_answer(servsocket)
    answer_sdp = RTCSessionDescription(answer["sdp"], answer["type"])
    if isinstance(answer_sdp, RTCSessionDescription):
        await pc.setRemoteDescription(answer_sdp)


async def clean_pcs():
    pcs.discard(pc)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video stream from the command line")
    # parser.add_argument("role", choices=["offer", "answer"])
    # parser.add_argument("--play-from", help="Read the media from a file and sent it.")
    parser.add_argument("--server-ip", help="Server IP")
    parser.add_argument("--server-port", help="Server Port")
    parser.add_argument("--record-to", help="Write received media to a file.")
    parser.add_argument("--verbose", "-v", action="count")
    add_signaling_arguments(parser)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # create signaling and peer connection
    signaling = create_signaling(args)
    pc = RTCPeerConnection()

    # create media source
    # Open webcam on Linux.
    # player = MediaPlayer('/dev/video0', format='v4l2', options={
    #     'video_size': '1920x1080'
    # })
    player = MediaPlayer('../inout_data/hq4.mp4')
    # pc = RTCPeerConnection()
    pc.addTrack(player.video)

    # create media sink
    if args.record_to:
        recorder = MediaRecorder(args.record_to)
    else:
        recorder = MediaBlackhole()
        # recorder = MediaRecorder('../inout_data/aiortc{0}.mp4'.format(round(time.time())))

    # init TCP socket to the client
    settings = initialize_setting()
    if args.server_port:
        server_port = args.server_port
    else:
        server_port = 9999

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((settings.server_ip, server_port))

    manager = Manager()
    events_queue = manager.Queue(maxsize=1)

    # configure user display delay logger
    currDir = os.path.dirname(os.path.realpath(__file__))
    Log_PATH = os.path.join(os.path.abspath(currDir),'..', 'inout_data')
    disp_log_url = os.path.join(Log_PATH, "display.rtc.log")
    rtt_log_url = os.path.join(Log_PATH, "rtt.rtc.cl.log")
    ifbw_log_url = os.path.join(Log_PATH, "ifbw.rtc.cl.log")
    with open(disp_log_url, 'w'):
        pass
    disp_logger = logging.getLogger('Display_Logger')
    hdlr_1 = logging.FileHandler(disp_log_url)
    disp_logger.setLevel(logging.INFO)
    disp_logger.addHandler(hdlr_1)
    disp_logger.info("frame_no,delay,timebase,pts,ts")

    # configure user RTT  logger
    with open(rtt_log_url, 'w'):
        pass
    rtt_logger = logging.getLogger('RTT_Logger')
    hdlr_2 = logging.FileHandler(rtt_log_url)
    rtt_logger.setLevel(logging.INFO)
    rtt_logger.addHandler(hdlr_2)
    rtt_logger.info("seconds,delay,client_ping_ts,server_pong_ts")

    # configure bw logger
    with open(ifbw_log_url, 'w'):
        pass
    ifbw_logger = logging.getLogger('BW_Logger')
    hdlr_3 = logging.FileHandler(ifbw_log_url)
    ifbw_logger.setLevel(logging.INFO)
    ifbw_logger.addHandler(hdlr_3)
    ifbw_logger.info("seconds,frame_no,bw")

    # run event loop
    try:

        loop = asyncio.get_event_loop()
        loop.run_until_complete( run(pc=pc, recorder=recorder,
                signaling=signaling, servsocket=sock, disp_logger=disp_logger, rtt_logger=rtt_logger, bw_logger=ifbw_logger))

    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())
        loop.run_until_complete(clean_pcs())
        try:
            if recorder != None:
                loop.run_until_complete(recorder.stop())
        except:
            pass

