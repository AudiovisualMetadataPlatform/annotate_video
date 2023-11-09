#!/bin/env python3
import argparse
import yaml

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("structured_whisper")
    parser.add_argument("output_vtt")
    parser.add_argument("--phrase_gap", type=float, default=1.5, help="Minimum gap between phrases")
    parser.add_argument("--max_duration", type=float, default=3.0, help="Longest caption duration when splitting")
    parser.add_argument("--min_duration", type=float, default=2.0, help="Shortest caption duration when splitting")
    args = parser.parse_args()

    with open(args.structured_whisper) as f:
        stt = yaml.safe_load(f)
    # find the words....
    if 'words' in stt:
        words = stt['words']
    else:
        # from the command line the words are stored in the individual segments
        words = []
        for s in stt['segments']:
            words.extend(s['words'])        
        words.sort(key=lambda x: x['start'])
        
    # the words have spaces in the front, and maybe rear.  Let's strip them.
    # and the probability data
    for w in words:
        w['word'] = w['word'].strip()
        w.pop('probability', None)


    # group words together were there are gaps.
    phrases = []
    last_end = None
    buffer = []
    for word in words:
        if last_end == None or (word['start'] - last_end) < args.phrase_gap:
            # append to the current phrase
            buffer.append(word)
        else:
            # start a new buffer.
            phrases.append({'start': buffer[0]['start'],
                            'end': buffer[-1]['end'],
                            'phrase': buffer})
            buffer = [word]
        last_end = word['end']

    if buffer:
        phrases.append({'start': buffer[0]['start'],
                        'end': buffer[-1]['end'],
                        'phrase': buffer})


    # rephrase the text into smaller bits.
    rephrase = []
    for i, p in enumerate(phrases):
        #if p['end'] - p['start'] > args.max_duration:
        #    print(f"Phrase is too long: {p['end'] - p['start']} seconds: {phrase2text(p)}")
        #    splitphrase(p, args.max_duration)
        print("Phrase", i, p['end'] - p['start'], phrase2text(p))
        rephrase.extend(splitphrase(p, args.max_duration))
        print()   
         



    with open(args.output_vtt, "w") as f:
        f.write("WEBVTT\n\n")
        for p in rephrase:            
            f.write(f"{s2ts(p['start'])} --> {s2ts(p['end'])}\n")
            f.write(phrase2text(p) + "\n\n")
            


def s2ts(s):
    h = int(s / 3600)
    s -= h * 3600
    m = int(s / 60)
    s -= m * 60
    return f"{h:0d}:{m:02d}:{s:06.3f}"


def splitphrase(phrase, limit):
    # add words until we hit the limit.  then back up
    # until we hit a punctuation word.  If we don't hit
    # one, then we leave it as-is.    
    results = []
    here = 0
    buffer = []
    start = 0
    duration = 0
    while here < len(phrase['phrase']):
        word = phrase['phrase'][here]
        #print(here, word['word'], duration)
        if not buffer:
            buffer.append(word)
            start = word['start']
            duration = word['end'] - word['start']
        else:
            duration = word['end'] - start
            buffer.append(word)
            
        if duration > limit:
            if buffer[-1]['word'][-1] in ".,?!":
                # if we end with a punctuation character we're
                # just one word long...we can accept that.
                results.append(buffer)
                buffer = []
                here += 1
            else:
                # we're too long and in the middle of a sentence.
                # back up until we find a puncuated word.
                for i in range(1, len(buffer) - 1):
                    #print(i, buffer[-i])
                    if buffer[-i]['word'][-1] in '.,?!':
                        #print(f"Found punct word at {-i}: {buffer[-i]['word']}")
                        results.append(buffer[0 : -i + 1])
                        buffer = []
                        here = here - (i - 2)
                        #print(f"New here: {here}: {phrase['phrase'][here]['word']}")
                        break
                else:
                    # didn't find a punct word.  Leave it as-is
                    results.append(buffer)
                    buffer = []
                    here += 1
                    
        else:
            here += 1

    if buffer:
        # there's some leftover bits.
        results.append(buffer)

    # convert the results into phrases
    phrases = []
    for r in results:
        phrases.append({'start': r[0]['start'],
                        'end': r[-1]['end'],
                        'phrase': r})

    for i, p in enumerate(phrases):
        print(i, phrase2text(p))

    return phrases






def phrase2text(phrase):
    words = ""
    for w in phrase['phrase']:
        if not words:
            words = w['word']
        else:
            if w['word'][0] in "-%,":
                # glomming first characters (hyphenation, percentage, thousands comma)
                words += w['word']
            else:
                words += " " + w['word']
    return words


if __name__ == "__main__":
    main()