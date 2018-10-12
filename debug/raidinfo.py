#!/usr/bin/python
import cv2
import sys
import json
import argparse

from os.path import dirname
sys.path.append(dirname(dirname(__file__)))

from cv2utils import cv2utils
from pokeocr import pokeocr
from pokediscord import pokediscord

def print_kv_line(k, v):
    print('\033[36m%9s\033[32m=\033[37m%s\033[0m' % (k, v))

parser = argparse.ArgumentParser(description='Parse an EX raid image (high level)')
parser.add_argument('-f', dest='configfile', default='config/exraid.json')
parser.add_argument('image')
args = parser.parse_args()

f = open(args.configfile)
config = json.load(f)
f.close()

topleft = cv2.imread(config['top_left_image'])
bottom = cv2.imread(config['bottom_image'])
image = cv2.imread(args.image)

ocr = pokeocr(config['location_regular_expression'])

raidInfo = ocr.scanExRaidImage(image, topleft, bottom)


print('')
print('\033[1;35m *** Results *** \033[0m')
print('\033[35m=================\033[0m')
for key, value in raidInfo.__dict__.iteritems():
  print_kv_line(key, value)

print_kv_line('category', pokediscord.generateCategoryName(raidInfo))
print_kv_line('channel', pokediscord.generateChannelName(raidInfo))
# print('\033[% ==> \033[0m #%s' % pokediscord.generateChannelName(raidInfo))

