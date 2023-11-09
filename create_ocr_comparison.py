#!/bin/env python3
import argparse
import yaml
from statistics import mean
import unicodedata

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outputfile")
    parser.add_argument("tesseract")
    parser.add_argument("rekognize")
    parser.add_argument("insights")
    args = parser.parse_args()

    data = {}
    
    # do tesseract
    print("Reading tesseract")
    if False:
        with open(args.tesseract) as f:
            ocr = yaml.safe_load(f)
        for f in ocr['frames']:
            time = format_time(f['frame_ms'])
            if time not in data:
                data[time] = [[], [], []]
            for block in sorted(f['blocks'], key=lambda b: (b['page_num'], b['block_num'], b['par_num'], b['line_num'], b['word_num'])):
                data[time][0].append(block['text'].strip())

    # do rekognize
    print("Reading Rekognize")
    with open(args.rekognize) as f:
        ocr = yaml.safe_load(f)
    for f in ocr['TextDetections']:
        if f['TextDetection']['Type'] == 'LINE':
            time = format_time(f['Timestamp'] / 1000)
            if time not in data:
                data[time] = [[], [], []]
            data[time][1].append(f['TextDetection']['DetectedText'].strip())

    # do insights
    print("Reading Insights")
    with open(args.insights) as f:
        ocr = yaml.safe_load(f)
    for f in ocr['videos'][0]['insights']['ocr']:
        for i in f['instances']:
            time = format_time(parse_timestamp(i['start']))
            if time not in data:
                data[time] = [[], [], []]
            data[time][2].append(f['text'].strip())

    # sanitize and build the text...
    for t in list(data.keys()):
        for i in range(len(data[t])):
            data[t][i] = sanitize_text(data[t][i])
        if data[t] == ['', '', '']:
            data.pop(t)

    # dump the output
    print("Writing data")
    with open(args.outputfile, "w") as f:
        last = ['', '', '']
        for t in sorted(data.keys()):            
            if last != data[t]:
                f.write("\t".join([t, *data[t]]) + "\n")
            last = data[t]


def sanitize_text(wordlist):
    # convert to ascii.    
    wordlist = [x for x in [unicodedata.normalize('NFKD', x).encode("ascii", "ignore").decode() for x in wordlist] if len(x) > 0]

    # return nothing if we get nothing.
    if not wordlist:
        return ""

    # if it is > 33% non-alphanumeric characters, fail.
    wordbunch = ''.join(wordlist).replace(' ', '')
    wordbunch_alpha = len([x.isalnum() for x in wordbunch if x.isalnum()])
    ratio = wordbunch_alpha / len(wordbunch)
    if ratio < 0.50:
        print(f"Failing {wordbunch}: {ratio}")
        return ""

    aword = mean([len(x) for x in wordlist])
    res = " ".join(wordlist)
    if aword < 3:
        print(f"Average length: {aword}: {' '.join(wordlist)}")
        # we will save it if the average * number of words > 75% of the 
        # overall string length...
        if aword * len(wordlist) / len(res) > 0.75:
            print("Saving string!")
        else: 
            return ""
    return res


def format_time(seconds):
    hours = int(seconds / 3600)
    seconds -= hours * 3600
    minutes = int(seconds / 60)
    seconds -= minutes * 60
    return f"{hours:0d}:{minutes:02d}:{seconds:06.3f}"


def parse_timestamp(ts):
    hours, mins, secs = [float(x) for x in ts.split(':')]
    return hours * 3600 + mins * 60 + secs



if __name__ == "__main__":
    main()