#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self):
        super().__init__()
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(
            "( v4l2src device=/dev/video0 ! "
            "video/x-raw,format=YUY2,width=1920,height=1080,framerate=5/1 ! "
            "videoconvert ! "
            "x265enc tune=zerolatency speed-preset=ultrafast key-int-max=15 ! "
            "rtph265pay name=pay0 pt=96 config-interval=1 )"
        )
        factory.set_shared(True)
        self.get_mount_points().add_factory("/cam", factory)

server = RTSPServer()
server.attach(None)

loop = GLib.MainLoop()
loop.run()