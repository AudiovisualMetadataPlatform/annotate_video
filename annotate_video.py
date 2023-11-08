#!/bin/env python3
#
# Take an annotation file and annoate the
# video in question, producing a new video
#

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageColor
import subprocess
import tempfile
import yaml
from yaml import CSafeLoader as Loader, CSafeDumper as Dumper
from pydantic import BaseModel as PydanticBaseModel, Field, ValidationError
import pydantic
from typing import Self, Any
import shutil
from concurrent.futures import ProcessPoolExecutor, Future
import time
import traceback
import itertools
from math import floor

#
# Zone Configuration
#
class BaseModel(PydanticBaseModel):
    class Config:
        arbitrary_types_allowed = True

class Style(BaseModel):
    """Style information"""    
    foreground: str = "white"
    background: str | None = None # use complementary if None
    border: int = 2
    font: str | ImageFont.FreeTypeFont = "LiberationSans-Bold.ttf"
    fontsize: float = 0.02 # if < 1, it's a percentage of content size


class Zone(BaseModel):
    """Definition of a zone"""
    title: str | None = None
    location: str
    size: float # if < 1 then it's a percentage of content size
    style: str | Style | None = None  # style will use the zone name, or default if None

    # physical location on the frame
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    def get_xy(self, x: int, y: int) -> tuple[int, int]:
        """Get the physical location of this spot in the zone"""
        return (self.x + x, self.y + y)


class ZoneConfig(BaseModel):
    zones: dict[str, Zone]
    styles: dict[str, Style] = Field(default_factory=dict)

    @staticmethod
    def load(filename) -> Self:
        with open(filename) as f:
            zdata = yaml.safe_load(f)
        zc = ZoneConfig(**zdata)
        if 'content' in zc.zones:
            raise ValidationError("You cannot define the 'content' zone")
        # create the content zone
        zc.zones['content'] = Zone(location='c', size=1)
        # create the default style if it doesn't exist.
        if 'default' not in zc.styles:
            zc.styles['default'] = Style()
        # resolve and verify all of the styles (and normalize the location)      
        for zn, zd in zc.zones.items():
            zd.location = zd.location.strip().lower()[0]
            if zd.location not in ('n', 's', 'e', 'w', 'c'):
                raise ValidationError("Zone location must be one of north, south, east or west")
            if zd.style is None:
                zd.style = 'default'
            if not isinstance(zd.style, Style):                
                if zd.style not in zc.styles:
                    raise ValidationError(f"Zone {zn} refers to non-existing style {zd.style}")
                # substitute the style as a string with the style as data.
                zd.style = zc.styles[zd.style]
        
        # while I'm here, I probably should fix up any None background colors
        for s in zc.styles.values():
            s.foreground = ImageColor.getrgb(s.foreground)
            if not s.background:
                s.background = (255 - s.foreground[0],
                                255 - s.foreground[1],
                                255 - s.foreground[2])
            else:
                s.background = ImageColor.getrgb(s.background)

        return zc
    

    def set_content_size(self, width: int, height: int) -> tuple[int, int]:
        """set the content size and create the zone offset+size and return the
           overall size of the image"""
        # set the content zone.
        czone = self.zones['content']
        czone.x, czone.y, czone.w, czone.h = 0, 0, width, height
        pwidth, pheight = width, height

        # walk through the zones and set their x, y, w, h
        curzones = [czone]
        for zn, z in self.zones.items():
            # adjust percentage sizes.
            if z.size < 1:
                print(zn, z.size)
                z.size = int(z.size * (czone.h if z.location in ('n', 's') else czone.w))
                print(f"New {zn}.size: {z.size} for zone {z}")
            else:
                z.size = int(z.size)
            match z.location:
                case 'n':
                    # Add a new box on the north. 
                    z.x, z.y, z.w, z.h = 0, 0, pwidth, z.size
                    pheight += z.size
                    # shift every box downward.
                    for ez in curzones:
                        ez.y += z.size                    
                case 's':
                    # Add a new box to the south
                    z.x, z.y, z.w, z.h = 0, pheight, pwidth, z.size
                    pheight += z.size
                case 'e':
                    # add a new box on the east
                    z.x, z.y, z.h, z.w = pwidth, 0, z.size, pheight
                    pwidth += z.size
                case 'w':
                    # add a new box on the west
                    z.x, z.y, z.h, z.w = 0, 0, z.size, pheight
                    pwidth += z.size
                    # shift everything to the right
                    for ez in curzones:
                        ez.x += z.size                    
            curzones.append(z)
        
        # adjust the font sizes in the styles
        for s in self.styles.values():
            if s.fontsize < 1:
                s.fontsize = int(height * s.fontsize)
            # and load the font into the style itself
            s.font = ImageFont.truetype(s.font, size=floor(s.fontsize))

        # make sure the height is even so ffmpeg is happy.
        if pheight % 2:
            pheight += 1
        return (pwidth, pheight)
    

    def get_zone(self, zone) -> Zone:
        """ Get the named zone"""
        return self.zones[zone]


    def get_style(self, style) -> Style:
        """Get the named style"""
        return self.styles[style if style is not None else 'default']


#
# Annotation Configuration
#
class BaseAnnotation(BaseModel):
    """Base class for an annotation"""
    zone: str | Zone
    position: tuple[int, int] = (0, 0)
    style: str | Style | None = None # if none use zone default

    def annotate(self, canvas: ImageDraw.ImageDraw):
        raise NotImplementedError("Implement this!")


    def drawtext(self, canvas: ImageDraw.ImageDraw, x, y, text, fill: bool = False, anchor='la'):
        """Draw text, with an optional background box"""
        if fill:
            bbox = self.style.font.getbbox(text=text, anchor='ld')
            origin = self.zone.get_xy(*self.position)
            canvas.rectangle([(origin[0] + bbox[0], origin[1] + bbox[1]),
                              (origin[0] + bbox[2], origin[1] + bbox[3])],
                              fill=self.style.background)
        try:
            canvas.text(self.zone.get_xy(*self.position),
                        text, anchor=anchor, font=self.style.font, fill=self.style.foreground)
        except Exception as e:
            print(f"**** Cannot draw text on canvas: {e}.  Style: {self.style}.  Text is '{text}'")

    def drawborder(self, canvas: ImageDraw.ImageDraw, x, y, w, h):
        """Draw a border box"""        
        if self.style.border:
            origin = self.zone.get_xy(x, y)
            canvas.rectangle([origin, (origin[0] + w, origin[1] + h)],
                            width=self.style.border, outline=self.style.foreground)
            canvas.rectangle([(origin[0] - 1 , origin[1] - 1), (origin[0] + w + 1, origin[1] + h + 1)],
                            width=1, outline=self.style.background)
                            

class TextAnnotation(BaseAnnotation):
    """perform a text annotation"""
    text: str
    fill: bool = False
    
    def annotate(self, canvas: ImageDraw.ImageDraw):
        # draw the text annotation
        self.drawtext(canvas, *self.position, self.text, fill=self.fill)
              

class BoxAnnotation(BaseAnnotation):
    """perform a box annotation"""
    text: str
    size: tuple[int, int]

    def annotate(self, canvas: ImageDraw.ImageDraw):
        self.drawborder(canvas, *self.position, *self.size)
        if self.text != '':
            self.drawtext(canvas, *self.position, self.text, fill=True, anchor='ld')


class AnnotationConfig(BaseModel):
    """Annotation configuration"""
    annotations: dict[int, list[BoxAnnotation | TextAnnotation]]


class Annotate:
    def __init__(self, zoneconfig: ZoneConfig, content_width: int, content_height: int):
        "Create an annotation engine"
        self.zc = zoneconfig
        # initialize the zones with the correct content size
        self.width, self.height = self.zc.set_content_size(content_width, content_height)
        self.cx, self.cy = self.zc.get_zone('content').get_xy(0, 0)
        self.anno: dict[int, list[BaseAnnotation]] = {}


    def add_annotations(self, annotations: AnnotationConfig):
        "add a list of annotations to the engine"
        for k, v in annotations.annotations.items():
            # fixup the style and zone for each annotation
            for a in v:
                a: BaseAnnotation = a
                if not isinstance(a.zone, Zone):
                    a.zone = self.zc.get_zone(a.zone)
                if isinstance(a.style, str):
                    a.style = self.zc.get_style(a.style)
                elif not isinstance(a.style, Style):
                    a.style = a.zone.style

            if k not in self.anno:
                self.anno[k] = []
            self.anno[k].extend(v)


    def annotate_frame(self, frameid: int, frame: Image.Image) -> Image.Image:
        # create a new image which is the full frame size
        newframe = Image.new(mode=frame.mode, size=(self.width, self.height))
        # copy the original image into the frame at the right place
        newframe.paste(frame, (self.cx, self.cy))
        # get our canvas and draw the borders/titles for all our zones.
        canvas = ImageDraw.Draw(newframe)
        for z in self.zc.zones.values():
            canvas.rectangle((z.x, z.y, z.x + z.w, z.y + z.h))
        
        if frameid in self.anno:
            for a in self.anno[frameid]:
                a.annotate(canvas)

        return newframe
      

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputvideo", help="Input Video")
    parser.add_argument("outputvideo", help="Output Video")
    parser.add_argument("zoneconfig", help="Zone configurationf file")
    parser.add_argument("annotations", nargs='+', help="Annotations")
    args = parser.parse_args()

    # get framerate
    p = subprocess.run(['ffprobe', args.inputvideo], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                        encoding='utf-8', check=True)
    for l in p.stdout.splitlines():
        if 'Stream' in l and 'Video' in l and 'fps' in l:
            parts = [x.strip() for x in l.split(',') if 'fps' in x]
            fps = parts[0].split()[0]
            break
    else:
        raise ValueError("Cannot determine video framerate")

    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "input").mkdir()
        Path(tmpdir, "output").mkdir()
        # some magick is needed to make sure we get absolutely every
        # frame out of the video.
        subprocess.run(['ffmpeg', 
                        '-fflags', '+genpts', '-r', str(fps),
                        '-i', args.inputvideo, 
                        #'-vsync', '0',
                        '-fps_mode', 'passthrough',
                        f'{tmpdir}/input/%06d.jpg', f'{tmpdir}/audio.wav'],
                       stdin=subprocess.DEVNULL, check=True)

        # we need the first frame to get the content dimensions so we can
        # compute the location of all of the zones.
        print("Loading Zone Configuration...")
        zconf = ZoneConfig.load(args.zoneconfig)
        im = Image.open(f'{tmpdir}/input/000001.jpg')

        anno = Annotate(zconf, im.width, im.height)

        for afile in args.annotations:
            print(f"Loading annotation file {afile}")
            with open(afile) as f:
                aconf = AnnotationConfig(**yaml.safe_load(f))
            anno.add_annotations(aconf)        

        # process the frames
        ppe = ProcessPoolExecutor()
        futures = {}
        all_frames = [(x, Path(tmpdir, "output", x.name), int(x.stem)) for x in Path(tmpdir, "input").glob("*.jpg")]
        
        def batched(iterable, chunk_size):
            iterator = iter(iterable)
            while chunk := tuple(itertools.islice(iterator, chunk_size)):
                yield chunk
        
        for batch in batched(all_frames, 500):
            futures[batch[0][2]] = ppe.submit(annotate_files, anno, batch)
        print("Waiting for everything to complete")
        ppe.shutdown(True)

        # put it back together.
        subprocess.run(['ffmpeg', '-y', '-r', fps, '-i', f'{tmpdir}/output/%06d.jpg', '-i', f'{tmpdir}/audio.wav',
                        '-r', fps, args.outputvideo], check=True, stdin=subprocess.DEVNULL)

    
def annotate_files(anno: Annotate, frames: list[set]): #, infile, outfile, framenum):    
    for infile, outfile, framenum in frames:
        t = time.time()
        try:      
            im = Image.open(infile)
            new_image = anno.annotate_frame(framenum, im)
            new_image.save(outfile)
            print(f"Modfied frame {infile} and wrote it to {outfile}:  {time.time() - t} seconds")
        except Exception as e:
            print(f"Caught exception for frame {framenum}: {e}")
            traceback.print_exc() 


if __name__ == "__main__":
    main()