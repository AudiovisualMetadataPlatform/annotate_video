#!/bin/env python3
import argparse
import yaml
from math import floor, ceil

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("insights")
    parser.add_argument("outfile")
    parser.add_argument("--fps", type=float, default=30/1.001)
    args = parser.parse_args()

    anno = {
        'annotations': {}
    }

    def add_anno(i, a):
        if i not in anno['annotations']:
            anno['annotations'][i] = []
        anno['annotations'][i].append(a)

    # load the insights
    with open(args.insights) as f:
        data = yaml.safe_load(f)['videos'][0]

    groups = {'audioclassifier': [], # topics
              'imageclassification': [], # labels
              'whisper-es': [],  # brands
              'whisper-fr': [], # named locations
              'whisper-ja': [], # named people
              }
    for insight in ('transcript', 'ocr', 'topics', 'faces', 'labels',
                    'scenes', 'shots', 'brands', 'namedPeople', 'namedLocations'):
        item_num = 0
        for t in data['insights'][insight]:
            item_num += 1
            for i in t['instances']:
                start_frame = floor(timestamp2seconds(i['start']) * args.fps)
                end_frame = ceil(timestamp2seconds(i['end']) * args.fps)
                for f in range(start_frame, end_frame + 1):
                    if insight == 'transcript':                                            
                        add_anno(f + 1, {
                            'zone': 'whisper-en',
                            'text': t['text']
                        })
                    elif insight == 'ocr':
                        add_anno(f + 1, {
                            'style': 'ocr',
                            'zone': 'content',
                            'position': (t['left'], t['top']),
                            'size': (t['width'], t['height']),
                            'text': t['text']                            
                        })
                    elif insight == 'topics':
                        groups['audioclassifier'].append((f + 1, t['confidence'], t['name']))
                    elif insight == 'labels':
                        groups['imageclassification'].append((f + 1, i['confidence'], t['name']))
                    elif insight == 'scenes':
                        add_anno(f + 1, {
                            'zone': 'scenedetect',
                            'text': f"Scene {item_num} {i['start']} - {i['end']}"
                        })                           
                    #elif insight == 'shots':
                    #    add_anno(f + 1, {
                    #        'zone': 'whisper-fr',
                    #        'text': f"Shot {item_num} {i['start']} - {i['end']}"
                    #    })      
                    elif insight == 'brands':
                        groups['whisper-es'].append((f + 1, t['confidence'], t['name']))
                    elif insight == "namedLocations":
                        groups['whisper-fr'].append((f + 1, t['confidence'], f"{t['name']} ({i['instanceSource']})"))
                    elif insight == "namedPeople":
                        groups['whisper-ja'].append((f + 1, t['confidence'], f"{t['name']} ({i['instanceSource']})"))


    # handle each of the groups
    for g in groups:
        data = {}
        for f, c, n in groups[g]:
            if f not in data:
                data[f] = []
            data[f].append([c, f"{n} ({c * 100:0.2f}%)"])
        for f in data:
            add_anno(f, {
                'zone': g,
                'text': ', '.join([x[1] for x in sorted(data[f], key=lambda n: n[0], reverse=True)])
            })


    with open(args.outfile, "w") as f:
        yaml.safe_dump(anno, f)


def seconds2timestamp(seconds):
    hours = int(seconds / 3600)
    seconds -= (hours * 3600)
    minutes = int(seconds / 60)
    seconds -= minutes * 60    
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def timestamp2seconds(ts):
    hours, mins, secs = [float(x) for x in ts.split(':')]
    return hours * 3600 + mins * 60 + secs


if __name__ == "__main__":
    main()