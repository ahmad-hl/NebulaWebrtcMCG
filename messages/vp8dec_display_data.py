class VP8Dec2DisplayData:
    def __init__(self, frame_no, frame, frame_sent_ts=None):
        self.frame_no = frame_no
        self.frame_sent_ts = frame_sent_ts
        self.frame = frame

    def __str__(self):
        obj_name = "frame_no: {}, len: {}, ts: {}".format(self.frame_no, len(self.frame), self.frame_sent_ts)
        return obj_name
