# Server Report Packet
# SR packet

class MTPpacket:

    def __init__(self, frame_no,sent_ts, psnr=None):
        self.frame_no = frame_no
        self.sent_ts = sent_ts
        self.psnr = psnr

    def __str__(self):
        obj_name = "frame_no: {}, sent_ts: {}, psnr: {}".format(self.seq_no, self.sent_ts, self.psnr)
        return obj_name

