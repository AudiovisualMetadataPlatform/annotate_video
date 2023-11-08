#!/bin/env python3
import argparse
import yaml
from math import floor, ceil

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("basename")
    parser.add_argument("outfile")
    parser.add_argument('--fps', type=float, default=30/1.001)
    args = parser.parse_args()

    anno = {
        'annotations': {}
    }

    def add_anno(i, a):
        if i not in anno['annotations']:
            anno['annotations'][i] = []
        anno['annotations'][i].append(a)

    # do the mediapipe objects
    print("Generating object annotations")
    with open(args.basename + "--mediapipe-objects.json") as f:
        data = yaml.safe_load(f)
    
    for f in data:
        for o in f['objects']:
            # in the file the frame index is 0-based but in ffmpeg the frames
            # start at 1
            if o['categories'][0][1] > 0.5:
                add_anno(f['frame_index'] + 1, {
                    'style': 'object',
                    'zone': 'content',                    
                    'position': (o['x'], o['y']),
                    'size': (o['w'], o['h']),
                    'text': f"{o['categories'][0][0]} ({int(o['categories'][0][1] * 100):d}%)"
                })

    # faces
    print("Generating face annotations")
    with open(args.basename + "--mediapipe-faces.json") as f:
        data = yaml.safe_load(f)
    for frame in data:
        fnum = 0
        for face in frame['faces']:
            fnum += 1
            add_anno(frame['frame_index'] + 1, {
                'style': 'face',
                'zone': 'content',
                'position': (face['x'], face['y']),
                'size': (face['w'], face['h']),
                'text': f"Face {fnum} ({int(face['score'] * 100):d}%)"
            })

    print("Generating OCR annotations")
    with open(args.basename + "--tesseract-ocr.json") as f:
        data = yaml.safe_load(f)
    for frame in data['frames']:
        for b in frame['blocks']:
            add_anno(frame['frame_num'] + 1, {
                'style': 'ocr',
                'zone': 'content',
                'position': (b['left'], b['top']),
                'size': (b['width'], b['height']),
                'text': b['text']
            })

    print("Generating Image classification")
    with open(args.basename + "--mediapipe-imageclassification.json") as f:
        data = yaml.safe_load(f)
    fdata = {}
    for frame in data:
        if frame['frame_index'] not in fdata:
            fdata[frame['frame_index']] = []        
        for c in frame['categories']:
            fdata[frame['frame_index']].append(f"{c[0]} ({int(c[1]* 100):d} %)")
    
    for i, x in fdata.items():
        add_anno(i + 1, {                
            'zone': 'imageclassification',
            'text': ', '.join(x)
        })    

    print("Generating scene detection")
    with open(args.basename + "--scenedetect-adaptive.json") as f:
        data = yaml.safe_load(f)
    scene = 0
    for s in data['scenes']:
        scene += 1
        for f in range(s['start_frame'], s['end_frame'] + 1):
            curstamp = seconds2timestamp(f * (1 / args.fps))
            add_anno(f + 1, {
                'zone': 'scenedetect',
                'text': f"Scene {scene}: {s['start_timecode']} - {s['end_timecode']}.    {curstamp}"
            })

    # mediapipe audio classifier
    print("Generating audio classification")
    with open(args.basename + "--mediapipe-audioclassifier.json") as f:
        data = yaml.safe_load(f)
    event_num = 0
    while event_num < len(data):
        event = data[event_num]
        if event_num == len(data) - 1:
            event_end = data[event_num]['timestamp_ms'] + 1000  # hold it for 1 second
        else:            
            event_end = data[event_num + 1]['timestamp_ms']
        
            
        start_frame = floor((event['timestamp_ms'] / 1000) * args.fps)
        end_frame = floor((event_end / 1000) * args.fps)
        print(event_num, len(data), event['timestamp_ms'], event_end, start_frame, end_frame)
        cats = [f"{x[0]} ({x[1] * 100:0.2f}%)" for x in event['categories'] if x[1] > 0]
        text = ', '.join(cats)
        for fnum in range(start_frame, end_frame + 1):
            add_anno(fnum + 1, {
                'zone': "audioclassifier",
                'text': text
            })
        event_num += 1

    # whisper languages
    for lang in ('en', 'es', 'fr', 'ja'):
        zone = f"whisper-{lang}"
        print(f"Creating {zone}")
        with open(args.basename + f"--whisper-{lang}-structured.yaml") as f:
            data = yaml.safe_load(f)

        for s in data['segments']:
            start_frame = floor(s['start'] * args.fps)
            end_frame = ceil(s['end'] * args.fps)
            for f in range(start_frame, end_frame + 1):
                add_anno(f + 1, {
                    'zone': zone,
                    'text': s['text']
                })
    





    with open(args.outfile, "w") as f:
        yaml.safe_dump(anno, f)


def seconds2timestamp(seconds):
    hours = int(seconds / 3600)
    seconds -= (hours * 3600)
    minutes = int(seconds / 60)
    seconds -= minutes * 60    
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


if __name__ == "__main__":
    main()