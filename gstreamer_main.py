#!/usr/bin/env python3

# Install the following required packages before running this script:
# sudo apt update
# sudo apt install -y python3-gi gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-gl gstreamer1.0-alsa fbset python3-rpi.gpio

#############################################################################
# CONFIGURATION
#############################################################################

# distance threshold in cm to switch from video to images
threshold_cm = 120

# directories for videos and images
videos_dir = "videos"
images_dir = "images"

IMAGE_EXTS = ("jpg", "jpeg", "png")
VIDEO_EXTS = ("mp4", "mkv", "webm", "avi", "mov")

#############################################################################


import os
import sys
import glob
from time import sleep
import gi


gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gst, GLib
import subprocess
from sensor import SensorThread


def get_framebuffer_size():
    # Try sysfs first
    try:
        with open('/sys/class/graphics/fb0/virtual_size', 'r') as f:
            s = f.read().strip()
            if s:
                parts = s.split(',') if ',' in s else s.split('x')
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])
    except Exception:
        pass
    # Fallback to fbset
    try:
        out = subprocess.check_output(['fbset', '-s'], stderr=subprocess.DEVNULL).decode('utf-8')
        # look for "geometry" line
        for line in out.splitlines():
            if 'geometry' in line:
                vals = line.split()
                # geometry: width height ...
                if len(vals) >= 3:
                    w = int(vals[1])
                    h = int(vals[2])
                    return w, h
    except Exception:
        pass
    # final fallback
    return 1920, 1080


class FullscreenPlayer:
    def __init__(self, videos_dir, width, height):
        self.videos = self._scan_videos(videos_dir)
        if not self.videos:
            print("No videos found in:", videos_dir)
            sys.exit(1)
        self.index = 0

        # Create a more detailed pipeline
        self.player = Gst.Pipeline.new("player")
        
        # Create elements
        self.source = Gst.ElementFactory.make("filesrc", "source")
        demuxer = Gst.ElementFactory.make("decodebin", "demuxer")
        videoconvert = Gst.ElementFactory.make("videoconvert", "colorspace")
        videoscale = Gst.ElementFactory.make("videoscale", "scaler")

        # Audio elements
        audioconvert = Gst.ElementFactory.make("audioconvert", "audioconv")
        audioresample = Gst.ElementFactory.make("audioresample", "audioresample") # Recommended
        audiosink = Gst.ElementFactory.make("autoaudiosink", "audiosink")
        
        caps = Gst.Caps.from_string(f"video/x-raw,width={width},height={height}")
        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        capsfilter.set_property("caps", caps)
        
        # Use fbdevsink for direct framebuffer output
        sink = Gst.ElementFactory.make("fbdevsink", "sink")
        if not sink:
            print("Failed to create fbdevsink. Make sure gstreamer1.0-plugins-bad is installed")
            sys.exit(1)
        
        sink.set_property("device", "/dev/fb0")  # Use primary framebuffer
        
        # Add elements to pipeline
        elements = [self.source, demuxer, videoconvert, videoscale, capsfilter, sink, audioconvert, audioresample, audiosink]
        for element in elements:
            if element:
                self.player.add(element)
        
        # Link static elements
        self.source.link(demuxer)
        videoconvert.link(videoscale)
        videoscale.link(capsfilter)
        capsfilter.link(sink)

        audioconvert.link(audioresample)
        audioresample.link(audiosink)
        
        # Connect to pad-added signal for dynamic linking
        demuxer.connect("pad-added", self.on_pad_added, self.player)
        
        # Bus to receive messages (EOS, ERROR)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)

        # Start playing first file
        self.play_current()

    def start(self):
        # Start or resume playback
        self.player.set_state(Gst.State.PLAYING)

    def stop(self):
        # Stop playback
        self.player.set_state(Gst.State.NULL)

    def _scan_videos(self, videos_dir):
        vids = []
        if not os.path.isabs(videos_dir):
            videos_dir = os.path.join(os.path.dirname(__file__), videos_dir)
        if not os.path.isdir(videos_dir):
            return []
        for ext in VIDEO_EXTS:
            vids.extend(glob.glob(os.path.join(videos_dir, f"*.{ext}")))
        vids.sort()
        return vids

    def play_current(self):
        path = self.videos[self.index]
        print("Playing:", path)
        self.player.set_state(Gst.State.NULL)
        self.source.set_property("location", os.path.abspath(path))
        self.player.set_state(Gst.State.PLAYING)

    def on_pad_added(self, element, pad, target):
        """Handler for linking dynamic pads when they become available"""
        pad_caps = pad.get_current_caps()
        if not pad_caps:
            return
        
        structure = pad_caps.get_structure(0)
        if structure.get_name().startswith('video/'):
           
            sink_element = self.player.get_by_name("colorspace")
            target_pad = sink_element.get_static_pad("sink")
            if not target_pad.is_linked():
                pad.link(target_pad)
        
        elif structure.get_name().startswith('audio/'):
            # Check if pad is already linked to avoid errors
            if pad.is_linked():
                print("Audio pad already linked.")
                return

            # Get the element to link to (audioconvert is the next static element)
            sink_element = self.player.get_by_name("audioconv") 
            
            # Request a pad from the sink element
            sink_pad = sink_element.get_static_pad("sink")

            # Attempt to link the pads
            if pad.link(sink_pad) == Gst.PadLinkReturn.OK:
                print("Successfully linked audio pad.")
            else:
                print("Failed to link audio pad.")

    def on_bus_message(self, bus, message):
        """Handle pipeline messages"""
        t = message.type
        if t == Gst.MessageType.EOS:
            # End of stream - move to next video
            self.index = (self.index + 1) % len(self.videos)
            self.play_current()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("Error:", err, debug)
            # Try to continue with next video
            self.index = (self.index + 1) % len(self.videos)
            self.play_current()

    def quit(self):
        try:
            self.player.set_state(Gst.State.NULL)
        except Exception:
            pass


class ImageSlideshow:
    """Slideshow using input-selector to switch between two image chains."""
    def __init__(self, images_dir, width, height, duration=5):
        self.images = self._scan_images(images_dir)
        print(f"Found {len(self.images)} images: {self.images}")
        
        if not self.images:
            print("No images found in:", images_dir)
            sys.exit(1)
            
        self.width = width
        self.height = height
        self.duration = duration
        self.pipeline = None
        self._running = False
        self.current_index = 0
        self.active_pad = 0  # Which input-selector pad is active
        
    def _create_image_bin(self, name, image_path):
        """Create a bin containing filesrc -> decodebin -> imagefreeze -> convert -> scale"""
        bin = Gst.Bin.new(name)
        
        src = Gst.ElementFactory.make("filesrc", f"{name}_src")
        src.set_property("location", image_path)
        
        dec = Gst.ElementFactory.make("decodebin", f"{name}_dec")
        freeze = Gst.ElementFactory.make("imagefreeze", f"{name}_freeze")
        conv = Gst.ElementFactory.make("videoconvert", f"{name}_conv")
        scale = Gst.ElementFactory.make("videoscale", f"{name}_scale")
        
        caps = Gst.ElementFactory.make("capsfilter", f"{name}_caps")
        caps.set_property("caps", 
            Gst.Caps.from_string(f"video/x-raw,width={self.width},height={self.height}"))
        
        # Add elements to bin
        elements = [src, dec, freeze, conv, scale, caps]
        for e in elements:
            bin.add(e)
        
        # Link static elements
        src.link(dec)
        dec.connect("pad-added", self._on_pad_added, freeze)
        freeze.link(conv)
        conv.link(scale)
        scale.link(caps)
        
        # Add ghost pad
        pad = caps.get_static_pad("src")
        ghost_pad = Gst.GhostPad.new("src", pad)
        bin.add_pad(ghost_pad)
        
        return bin

    def _scan_images(self, images_dir):
        imgs = []
        if not os.path.isabs(images_dir):
            images_dir = os.path.join(os.path.dirname(__file__), images_dir)
        if not os.path.isdir(images_dir):
            return []
        for ext in IMAGE_EXTS:
            pattern = os.path.join(images_dir, f"*.{ext}")
            matches = glob.glob(pattern)
            # Convert to absolute paths
            matches = [os.path.abspath(p) for p in matches]
            imgs.extend(matches)
        imgs.sort()
        return imgs

    def start(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        print(f"Starting slideshow with {len(self.images)} images")
        
        # Create pipeline
        self.pipeline = Gst.Pipeline.new("slideshow")
        
        # Create input-selector
        self.selector = Gst.ElementFactory.make("input-selector", "selector")
        
        # Create two image bins
        self.bin1 = self._create_image_bin("bin1", self.images[0])
        if len(self.images) > 1:
            self.bin2 = self._create_image_bin("bin2", self.images[1])
            self.current_index = 1
        else:
            self.bin2 = self._create_image_bin("bin2", self.images[0])
            self.current_index = 0
            
        # Create sink
        sink = Gst.ElementFactory.make("fbdevsink", "sink")
        sink.set_property("device", "/dev/fb0")
        
        # Add everything to pipeline
        elements = [self.bin1, self.bin2, self.selector, sink]
        for e in elements:
            self.pipeline.add(e)
            
        # Link bins to selector
        self.bin1.link_pads("src", self.selector, "sink_0")
        self.bin2.link_pads("src", self.selector, "sink_1")
        
        # Link selector to sink
        self.selector.link(sink)
        
        # Start with first bin
        self.selector.set_property("active-pad", 
            self.selector.get_static_pad("sink_0"))
        
        # Setup switching timer
        GLib.timeout_add_seconds(self.duration, self._switch_image)
        
        # Setup error handling
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._on_bus_message)
        
        # Start playback
        self._running = True
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self._running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def _switch_image(self):
        """Switch to the other bin and update its image"""
        if not self._running:
            return False
            
        # Switch active pad
        next_pad = 1 if self.active_pad == 0 else 0
        self.selector.set_property("active-pad",
            self.selector.get_static_pad(f"sink_{next_pad}"))
        self.active_pad = next_pad
        
        # Update the inactive bin with next image
        next_index = (self.current_index + 1) % len(self.images)
        inactive_bin = self.bin1 if next_pad == 1 else self.bin2
        
        # Update source
        src = inactive_bin.get_by_name(f"{'bin1' if next_pad == 1 else 'bin2'}_src")
        self.pipeline.set_state(Gst.State.READY)
        src.set_property("location", self.images[next_index])
        self.pipeline.set_state(Gst.State.PLAYING)
        
        self.current_index = next_index
        return True  # Keep the timer running
            
    def _on_pad_added(self, element, pad, target):
        """Handler for linking dynamic pads when they become available"""
        pad_caps = pad.get_current_caps()
        if not pad_caps:
            return
            
        name = pad_caps.get_structure(0).get_name()
        if name.startswith('video/') or name.startswith('image/'):
            target_pad = target.get_static_pad("sink")
            if not target_pad.is_linked():
                pad.link(target_pad)
                print(f"Linked pad with caps: {pad_caps.to_string()}")
                
    def _on_bus_message(self, bus, message):
        """Handle pipeline messages"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Pipeline error: {err.message}")
            print(f"Debug info: {debug}")
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            print(f"Pipeline warning: {err.message}")
            print(f"Debug info: {debug}")
        elif t == Gst.MessageType.INFO:
            err, debug = message.parse_info()
            print(f"Pipeline info: {err.message}")
            print(f"Debug info: {debug}")


class SensorController:
    """Polls the SensorThread and switches between video and image slideshow."""
    def __init__(self, player: FullscreenPlayer, slideshow: ImageSlideshow, threshold_cm=100):
        self.player = player
        self.slideshow = slideshow
        self.threshold = threshold_cm
        self.sensor = SensorThread(interval=0.2, use_dummy=False)
        self.sensor.start()
        self.mode = 'video'  # current mode: 'video' or 'images'
        # poll sensor every second
        GLib.timeout_add_seconds(1, self._poll)

    def _poll(self):
        try:
            dist = float(self.sensor.distance)
        except Exception:
            dist = 0.0
        # debug
        print('Sensor distance:', dist)
        if dist > 0 and dist <= self.threshold:
            # object nearby -> images
            if self.mode != 'images':
                self._switch_to_images()
        else:
            # no nearby object -> video
            if self.mode != 'video':
                self._switch_to_video()
        return True

    def _switch_to_images(self):
        print('Switching to images')
        try:
            self.player.stop()
        except Exception:
            pass
        # start slideshow
        try:
            self.slideshow.start()
            self.mode = 'images'
        except Exception as e:
            print('Failed to start slideshow:', e)

    def _switch_to_video(self):
        print('Switching to video')
        try:
            self.slideshow.stop()
        except Exception:
            pass
        try:
            self.player.start()
            self.mode = 'video'
        except Exception as e:
            print('Failed to start video:', e)


if __name__ == "__main__":
    # Stop display manager to free framebuffer
    os.system('sudo service lightdm stop')

    # Clear the screen and hide the cursor
    os.system('sudo sh -c \'echo -e "\033[9;0]" > /dev/tty0\'')  # Set blank console
    os.system('sudo sh -c \'setterm -blank 0 > /dev/tty0\'')     # Disable console blanking
    os.system('sudo sh -c \'echo -e "\033[?25l" > /dev/tty0\'')  # Hide cursor
    os.system('sudo sh -c \'clear > /dev/tty0\'')                # Clear the screen

    # Give permissions to framebuffer device
    os.system('sudo chmod 666 /dev/fb0')

    # Add current user to video group if not already added
    os.system('sudo usermod -a -G video $USER')

    # Give some time for the system to settle
    sleep(1)
    Gst.init(None)
    
    fb_w, fb_h = get_framebuffer_size()
    player = FullscreenPlayer(videos_dir, fb_w, fb_h)
    slideshow = ImageSlideshow(images_dir, fb_w, fb_h, duration=5)
    
    controller = SensorController(player, slideshow, threshold_cm=50)
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        try:
            controller.sensor.stop()
        except Exception:
            pass
        try:
            controller.slideshow.stop()
        except Exception:
            pass
    
    player.quit()
    os.system('sudo sh -c \'echo -e "\033[?25h" > /dev/tty0\'')
    os.system('sudo service lightdm start')
    sys.exit(0)