#!/bin/env python3
import argparse
import yaml
from math import floor, ceil

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("basename")
    parser.add_argument("outfile")
    args = parser.parse_args()

    anno = {
        'annotations': {}
    }

    def add_anno(i, a):
        if i not in anno['annotations']:
            anno['annotations'][i] = []
        anno['annotations'][i].append(a)


    # load the text
    print("Loading text")
    with open(f"{args.basename}--rekognize-text.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata']['FrameRate']
    fwidth = data['VideoMetadata']['FrameWidth']
    fheight = data['VideoMetadata']['FrameHeight']

    for f in data['TextDetections']:
        frame_num = floor((f['Timestamp'] / 1000) * fps)
        t = f['TextDetection']
        if t['Type'] != 'LINE':
            continue
        bbox = t['Geometry']['BoundingBox']
        add_anno(frame_num + 1, {
            'style': 'ocr',
            'zone': 'content',
            'position': (floor(bbox['Left'] * fwidth), floor(bbox['Top'] * fheight)),
            'size': (floor(bbox['Width'] * fwidth), floor(bbox['Height'] * fheight)),
            'text': t['DetectedText']
        })

    # load the labels
    print("Loading labels")
    with open(f"{args.basename}--rekognize-labels.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata']['FrameRate']
    fwidth = data['VideoMetadata']['FrameWidth']
    fheight = data['VideoMetadata']['FrameHeight']

    fanno = {}
    for f in data['Labels']:
        frame_num = floor((f['Timestamp'] / 1000) * fps)
        if frame_num not in fanno:
            fanno[frame_num] = []
        lbl = f['Label']
        fanno[frame_num].append((lbl['Confidence'], f"{lbl['Name']} ({lbl['Categories'][0]['Name']}) {lbl['Confidence']:0.2f}%"))
        
    for fnum, things in fanno.items():
        add_anno(fnum + 1, {
            'zone': 'imageclassification',
            'text': ', '.join([x[1] for x in sorted(things, reverse=True, key=lambda n: n[0])])
        })


    # load the faces
    print("Loading Faces")
    with open(f"{args.basename}--rekognize-face.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata']['FrameRate']
    fwidth = data['VideoMetadata']['FrameWidth']
    fheight = data['VideoMetadata']['FrameHeight']

    for f in data['Faces']:
        frame_num = floor((f['Timestamp'] / 1000) * fps)
        face = f['Face']
        bbox = face['BoundingBox']

        # build a face description
        desc = f"{face['Gender']['Value'][0]}({face['AgeRange']['Low']}-{face['AgeRange']['High']}) "
        desc += f"{face['Emotions'][0]['Type']} ({face['Emotions'][0]['Confidence']:0.2f}%) "
        features = []
        for feature in ('Smile', 'Eyeglasses', 'Sunglasses', 'Beard', 
                        'Mustache', 'EyesOpen', 'MouthOpen'):
            if face[feature]['Value']:
                features.append(feature)
        desc += ','.join(features)

        add_anno(frame_num + 1, {
            'style': 'face',
            'zone': 'content',
            'position': (floor(bbox['Left'] * fwidth), floor(bbox['Top'] * fheight)),
            'size': (floor(bbox['Width'] * fwidth), floor(bbox['Height'] * fheight)),
            'text': desc
        })

    # moderation
    print("Loading Moderation")
    with open(f"{args.basename}--rekognize-moderation.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata']['FrameRate']
    fwidth = data['VideoMetadata']['FrameWidth']
    fheight = data['VideoMetadata']['FrameHeight']

    fanno = {}
    for f in data['ModerationLabels']:
        frame_num = floor((f['Timestamp'] / 1000) * fps)
        if frame_num not in fanno:
            fanno[frame_num] = []
        lbl = f['ModerationLabel']
        fanno[frame_num].append((lbl['Confidence'], f"{lbl['Name']} ({lbl['Confidence']:0.2f}%)"))
        
    for fnum, things in fanno.items():
        add_anno(fnum + 1, {
            'zone': 'whisper-en',
            'text': ', '.join([x[1] for x in sorted(things, reverse=True, key=lambda n: n[0])])
        })    


    # segments
    print("Loading Segments")
    with open(f"{args.basename}--rekognize-shots.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata'][0]['FrameRate']
    fwidth = data['VideoMetadata'][0]['FrameWidth']
    fheight = data['VideoMetadata'][0]['FrameHeight']

    fanno = {}
    for f in data['Segments']:
        fstart = f['StartFrameNumber']
        fend = f['EndFrameNumber']
        if f['Type'] == "SHOT":
            confidence = f['ShotSegment']['Confidence']
            text = f"Shot {f['ShotSegment']['Index']} ({confidence:0.2f}%) {f['StartTimecodeSMPTE']} - {f['EndTimecodeSMPTE']}"
        elif f['Type'] == "TECHNICAL_CUE":
            confidence = f['TechnicalCueSegment']['Confidence']
            text = f"{f['TechnicalCueSegment']['Type']} ({confidence:0.2f}%) {f['StartTimecodeSMPTE']} - {f['EndTimecodeSMPTE']}"            
        for i in range(fstart, fend + 1):
            if i not in fanno:
                fanno[i] = []
            fanno[i].append((confidence, text))

    for fnum, things in fanno.items():
        add_anno(fnum + 1, {
            'zone': 'audioclassifier',
            'text': ', '.join([x[1] for x in sorted(things, reverse=True, key=lambda n: n[0])])
        })    

    # load the people
    print("Loading Persons")
    with open(f"{args.basename}--rekognize-person.json") as f:
        data = yaml.safe_load(f)

    fps = data['VideoMetadata']['FrameRate']
    fwidth = data['VideoMetadata']['FrameWidth']
    fheight = data['VideoMetadata']['FrameHeight']

    for f in data['Persons']:
        frame_num = floor((f['Timestamp'] / 1000) * fps)
        person = f['Person']
        if 'BoundingBox' in person:
            bbox = person['BoundingBox']

            add_anno(frame_num + 1, {
                'style': 'person',
                'zone': 'content',
                'position': (floor(bbox['Left'] * fwidth), floor(bbox['Top'] * fheight)),
                'size': (floor(bbox['Width'] * fwidth), floor(bbox['Height'] * fheight)),
                'text': f"Person {person['Index']}"
            })


    print("Writing annotations")
    with open(args.outfile, "w") as f:
        yaml.safe_dump(anno, f)


def seconds2timestamp(seconds):
    hours = int(seconds / 3600)
    seconds -= (hours * 3600)
    minutes = int(seconds / 60)
    seconds -= minutes * 60    
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def timestamp2seconds(ts):
    hours, mins, secs = [int(x) for x in ts.split(':')]
    return hours * 3600 + mins * 60 + secs


if __name__ == "__main__":
    main()