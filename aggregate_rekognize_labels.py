#!/bin/env python3
import argparse
import yaml
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_data")
    parser.add_argument("aggregate_data")
    parser.add_argument("--confidence", type=float, default=50, help="filter by confidence (0-100)")
    parser.add_argument("--length", type=float, default=2, help="Minimum length of time to be considered a sighting")
    parser.add_argument("--gap", type=float, default=1, help="number of seconds to be considered a gap")
    args = parser.parse_args()

    # convert length and gap to ms
    args.gap *= 1000
    args.length *= 1000

    print("Loading labels")
    with open(args.raw_data) as f:
        #raw = yaml.safe_load(f)
        raw = json.load(f)

    print("Parsing data")
    fps = raw['VideoMetadata']['FrameRate']
    data = {'framerate': fps,
            'labels': {}}
    for label in raw['Labels']:
        lbl = label['Label']
        con = lbl['Confidence']   
        cat = '/'.join([x['Name'] for x in lbl['Categories']])
        nam = lbl['Name']
        key = '/'.join([x['Name'] for x in lbl['Parents']])        
        if cat not in data['labels']:
            data['labels'][cat] = {}
        if nam not in data['labels'][cat]:
            data['labels'][cat][nam] = {}
        if key not in data['labels'][cat][nam]:            
            data['labels'][cat][nam][key] = []
        data['labels'][cat][nam][key].append([label['Timestamp'], con])    

    print("Filtering content")
    for cat in data['labels']:
        for nam in data['labels'][cat]:
            for key in data['labels'][cat][nam]:
                count = start = last = confidence = -1
                ndata = []
                for item in data['labels'][cat][nam][key]:            
                    ts, con = item
                    if start == -1:
                        start = last = ts
                        count = 1
                        confidence = con
                    else:
                        if ts - last > args.gap:
                            # too far apart...commit the last one
                            rcon = confidence / count
                            span = last - start
                            if rcon >= args.confidence and span >= args.length:
                                ndata.append([ms2ts(start), ms2ts(last), confidence / count])
                            start = last = ts
                            count = 1
                            confidence = con
                        else:
                            # adjust values as necessary
                            last = ts
                            confidence += con
                            count += 1
                # we've reached the end.  Clean up anything that's left.
                rcon = confidence / count
                span = last - start
                if rcon >= args.confidence and span >= args.length:
                    ndata.append([ms2ts(start), ms2ts(last), confidence / count])

                data['labels'][cat][nam][key] = ndata

    # prune empty things
    print("Pruning tree")
    for cat in list(data['labels'].keys()):
        for nam in list(data['labels'][cat].keys()):
            for key in list(data['labels'][cat][nam].keys()):
                if not len(data['labels'][cat][nam][key]):
                    data['labels'][cat][nam].pop(key)
            if not len(data['labels'][cat][nam]):
                data['labels'][cat].pop(nam)
        if not len(data['labels'][cat]):
            data['labels'].pop(cat)



    print("Writing aggregate data")
    with open(args.aggregate_data, "w") as f:
        yaml.safe_dump(data, f)



def ms2ts(ms):
    ms /= 1000
    hours = int(ms / 3600)
    ms -= hours * 3600
    mins = int(ms / 60)
    ms -= mins * 60
    return f"{hours:02d}:{mins:02d}:{ms:06.3f}"



if __name__ == "__main__":
    main()