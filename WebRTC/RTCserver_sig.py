import argparse, asyncio, logging, socket, time,b64coder, struct, os

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from custom_videoRTC_server import CustomVideoRTCServer

pcs = set()

async def run(pc, signaling, client_socket):

    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)


    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            print("Audio Track {} received".format(track.kind))
        elif track.kind == "video":
            print("Video Track {} received".format(track.kind))
            # local_track = CustomVideoTrackRTCServer(track)
            # pc.addTrack(local_track)

    # send offer receive answer
    await exchange_offer_answer(client_socket, pc)

    # connect signaling
    await signaling.connect()


    @pc.on("datachannel")
    def on_datachannel(channel):
        print("channel(%s) %s" % (channel.label, "created by remote party"))

        @channel.on("message")
        def on_message(message):
            print("channel(%s) %s" % (channel.label, message))

            if isinstance(message, str) and message.startswith("ping"):
                # print("Pong- diff ts:{:.6f} ms".format((time.time() - float(message[5:])) * 1000))
                # reply
                reply = "pong" + message[4:]+",%f" % time.time() #current_stamp()
                channel.send(reply)
            elif isinstance(message, str) and message.startswith("pang"):
                ts_list = message[5:].split(",")
                # print("Pang- diff ts:{:.6f} ms".format((time.time() - float(ts_list[2])) * 1000))
                elapsed_ms = (time.time() - float(ts_list[1])) * 1000 #current_stamp()
                rtt_logger.info("{},{:.3f},{}".format(round(time.time()), elapsed_ms,message[5:]))

    # consume signaling
    await consume_signaling(signaling)


async def consume_signaling(signaling):
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
            print("ICE {} is established ".format(obj))
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

def send_answer(servsocket,pc):
    answer_json_obj = {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}
    print("answer >>> {}".format(answer_json_obj))
    b64encoded = b64coder.json_b64encode(answer_json_obj)
    answer_size = struct.pack("L", len(b64encoded))
    client_socket.sendall(answer_size + b64encoded)


def receive_offer(servsocket):
    metadata_size = struct.calcsize("L")
    offer_size_metadata = servsocket.recv(metadata_size)
    offer_size = struct.unpack("L", offer_size_metadata)
    server_offer_json = recvall(servsocket, offer_size[0])
    offer = b64coder.b64decode(server_offer_json)
    print(" offer <<< {}".format(offer))

    return offer

async def exchange_offer_answer(client_socket, pc):

    #receive & set offer
    offer = receive_offer(client_socket)
    offer_sdp = RTCSessionDescription(offer["sdp"], offer["type"])
    if isinstance(offer_sdp, RTCSessionDescription):
        await pc.setRemoteDescription(offer_sdp)

    #create & send answer
    answer = await pc.createAnswer()
    await  pc.setLocalDescription(answer)
    send_answer(client_socket, pc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video stream from the command line")
    # parser.add_argument("role", choices=["offer", "answer"])
    #record to for computing PSNR (original vs received)
    parser.add_argument("--record-to", help="Write received media to a file.")
    parser.add_argument("--verbose", "-v", action="count")
    add_signaling_arguments(parser)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # create signaling and peer connection
    signaling = create_signaling(args)
    pc = RTCPeerConnection()
    #  create media source (e.g., Open webcam on Linux, or video or share screen)
    # player = MediaPlayer('/dev/video0', format='v4l2', options={
    #     'video_size': '1280x720'
    # })
    # player = MediaPlayer('foo.mp4')

    # configure render logger
    CurrDir = os.path.dirname(os.path.realpath(__file__))
    Logs_Dir = os.path.join(CurrDir, '..', 'inout_data')
    # configure performance logger
    render_log_url = os.path.join(Logs_Dir, "render.rtc.sr.log")
    with open(render_log_url, 'w'):
        pass
    render_logger = logging.getLogger('render_Logger')
    hdlr_1 = logging.FileHandler(render_log_url)
    render_logger.setLevel(logging.INFO)
    render_logger.addHandler(hdlr_1)
    render_logger.info("frame_no,delay,timebase,pts,ts")

    # configure user RTT  logger
    rtt_log_url = os.path.join(Logs_Dir, "rtt.rtc.sr.log")
    with open(rtt_log_url, 'w'):
        pass
    rtt_logger = logging.getLogger('RTT_Logger')
    hdlr_2 = logging.FileHandler(rtt_log_url)
    rtt_logger.setLevel(logging.INFO)
    rtt_logger.addHandler(hdlr_2)
    rtt_logger.info("seconds,delay,client_ping_ts,server_pong_ts,client_pang_ts")


    # create media source ( 0: webcam, 1: video, 2: youtube, otherwise: screen sharing)
    screenshare = CustomVideoRTCServer(render_logger=render_logger, source=1)
    pc.addTrack(screenshare)
    # pc.addTransceiver(trackOrKind='video', direction='sendonly')

    # create media sink
    if args.record_to:
        recorder = MediaRecorder(args.record_to)
    else:
        recorder = MediaBlackhole()

    # init TCP socket to the client
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(('', 9999))
    serversocket.listen(5)

    (client_socket, address) = serversocket.accept()
    print("client socket: {} - {}".format(client_socket, address))

    # run event loop
    loop = asyncio.get_event_loop()
    try:

        loop.run_until_complete( run(pc=pc, signaling=signaling, client_socket=client_socket))

        # loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())
        try:
            loop.run_until_complete(recorder.stop())
        except:
            pass