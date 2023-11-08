#!/bin/env python3
import argparse
import yaml

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("unprompted_data")
    parser.add_argument("prompted_data")
    parser.add_argument("output_data")
    args = parser.parse_args()


    column = 0
    data = {}
    for file in (args.unprompted_data, args.prompted_data):
        with open(file) as f:
            script = yaml.safe_load(f)
        for word in script['words']:
            start = f"{word['start']:0.2f}"
            if start not in data:
                data[start] = ['', '']
            data[start][column] = word['word']
        column += 1

    with open(args.output_data, "w") as o:
        for pit in sorted(data.keys(), key=lambda x: float(x)):
            same = 'Y' if all([x == data[pit][0] for x in data[pit]]) else 'N'
            o.write('\t'.join([sec2time(pit), *data[pit], same]) + "\n")



    
def sec2time(s):
    s = float(s)
    h = int(s / 3600)
    s -= h * 3600
    m = int(s / 60)
    s -= m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


if __name__ == "__main__":
    main()