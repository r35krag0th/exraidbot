import pytest
import cv2
import sys
import json
import argparse
import os

from os.path import dirname
sys.path.append(dirname(dirname(__file__)))

from cv2utils import cv2utils
from pokeocr import pokeocr
from pokediscord import pokediscord

TEST_IMAGE_DIR = os.path.abspath(os.path.join(dirname(__file__), '..', 'test_images'))

VALIDATION_IMAGES_AND_DATA = (
  {
    'image': 'Champaign_IL/Blair-Park/20180902_Invite001.png',
    'expected': {
      'begin': '11:00AM',
      'city': 'Urbana',
      'day': '2',
      'end': '11:45AM',
      'location': 'Blair Park',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Boneyard-Creek-Second-Street-Basin/20180902_Invite001.png',
    'expected': {
      'begin': '12:00PM',
      'city': 'Champaign',
      'day': '2',
      'end': '12:45PM',
      'location': 'Boneyard Creek Second Street Basin',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Fred-B-Lamb-Trail/20180902_Invite001.png',
    'expected': {
      'begin': '1:00PM',
      'city': 'Champaign',
      'day': '2',
      'end': '1:45PM',
      'location': 'Fred B Lamb Trail',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Champaign-Waterfall/20180909_Invite001.png',
    'expected': {
      'begin': '5:00PM',
      'city': 'Champaign',
      'day': '9',
      'end': '5:45PM',
      'location': 'Champaign Waterfall',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Beckman-Institute-Upwells-Fountain/20180902_Invite002.png',
    'expected': {
      'begin': '4:30PM',
      'city': 'Urbana',
      'day': '9',
      'end': '5:15PM',
      'location': 'Beckman Institute - Upwells Fountain',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Police-and-Firefighters-Memorial/20180909_Invite001.jpg',
    'expected': {
      'begin': '2:30PM',
      'city': 'Champaign',
      'day': '9',
      'end': '3:15PM',
      'location': 'Police and Firefighters Memorial',
      'month': 'September'
    }
  },
  {
    'image': 'Champaign_IL/Beckman-Institute-Upwells-Fountain/20180902_Invite001.png',
    'expected': {
      'begin': '4:30PM',
      'city': 'Urbana',
      'day': '9',
      'end': '5:15PM',
      'location': 'Beckman Institute - Upwells Fountain',
      'month': 'September'
    }
  }
)


@pytest.mark.parametrize('filename,expected_result', [
  (a['image'], a['expected']) for a in VALIDATION_IMAGES_AND_DATA
])
def test_raidinfo_validation(filename, expected_result):
  filename = os.path.join(TEST_IMAGE_DIR, filename)
  bot_config = json.load(open('config/exraid.testing.json'))

  topleft = cv2.imread(bot_config['top_left_image'])
  bottom = cv2.imread(bot_config['bottom_image'])
  image = cv2.imread(filename)

  ocr = pokeocr(bot_config['location_regular_expression'])

  raid_info = ocr.scanExRaidImage(image, topleft, bottom)

  for k, v in expected_result.iteritems():
    assert v == getattr(raid_info, k)
