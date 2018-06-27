# This Python file uses the following encoding: utf-8
from PIL import Image
import pyocr
import pyocr.builders
import cv2
import sys
import re
from cv2utils import cv2utils

class InvalidCityException(Exception):
  pass

class InvalidDateTimeException(Exception):
  pass

class InvalidGetDirectionsException(Exception):
  pass

class MatchNotCenteredException(Exception):
  pass

class TooFewLinesException(Exception):
  pass

class pokeocr:
  def __init__(self, location_regex, date_regex, gd_regex):
    self.tool = pyocr.get_available_tools()[0]
    self.lang = self.tool.get_available_languages()[0]
    self.dateTimeRE = re.compile(date_regex)
    self.cityRE = re.compile(location_regex)
    self.getDirectionsRE = re.compile(gd_regex)
    self.alphaRE = re.compile('[A-Za-z]+')

  @staticmethod
  def isMatchCentered(width, startx, endx):
    matchw = endx - startx
    offset = (width - matchw) / 2
    diff = abs(offset - startx)

    # We want to return True/False, but we need to know the correct offset
    # if it's False. There's probably a better way to do this...
    if diff > (width * .04):
      return offset
    else:
      return True
  
  def scanExRaidImage(self, image, top, bottom, useCity=True, debug=False):
    # Find the source image dimensions
    height, width, channels = image.shape

    # Run the scaling matcher to find the template, then sanity check the
    # match
    ((b_startX, b_startY), (b_endX, b_endY)) = cv2utils.scalingMatch(top, image)
    val = self.isMatchCentered(width, b_startX, b_endX)
    if val != True:
      raise MatchNotCenteredException('Top template match not centered. Starts at ' + str(b_startX) + ', should be ' + str(val))
    ((t_startX, t_startY), (t_endX, t_endY)) = cv2utils.scalingMatch(bottom, image)
    val = self.isMatchCentered(width, t_startX, t_endX)
    if val != True:
      raise MatchNotCenteredException('Bottom template match not centered. Starts at ' + str(t_startX) + ', should be ' + str(val))

    # Crop the image
    image = image[b_endY:t_startY,b_startX:b_endX]

    # Scale up small images
    height, width = image.shape[:2]
    if width < 509:
      image = cv2.resize(image, (0,0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # Increase contrast. Must be done before grayscale conversion
    image = cv2utils.increaseContrast(image)

    # Convert to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Convert to PIL format
    pil = Image.fromarray(image)

    # OCR the text
    txt = self.tool.image_to_string(pil, lang=self.lang, builder=pyocr.builders.TextBuilder())
    lines = txt.split("\n")

    # Sometimes OCR will insert extra empty lines, so let's strip them out
    newlines = []
    for i in range(len(lines)):
      if not len(lines[i]) == 0:
        newlines.append(lines[i])
    lines = newlines

    if debug:
      return lines

    # If we're not going to use the city info anyway, we can process images
    # that are missing it
    if useCity:
      minlines = 4
    else:
      minlines = 3

    if len(lines) < minlines:
      raise TooFewLinesException('Found fewer lines of text than expected')

    ret = exRaidData()

    # A common issue is reading lowercase L as pipe. There should never
    # be pipes in this data, so let's just replace them...
    lines[0] = lines[0].replace('|', 'l')
    match = self.dateTimeRE.match(lines[0])
    if match:
      if self.alphaRE.match(match.group(2)):
        ret.month = match.group(2)
        ret.day = match.group(1)
      else:
        ret.month = match.group(1)
        ret.day = match.group(2)

      # Sometimes OCR drops the space between the minutes and AM/PM.  Let's
      # just strip all spaces for consistency
      ret.begin = match.group(3).replace(' ', '')
      ret.end = match.group(4).replace(' ', '')
    else:
      raise InvalidDateTimeException('Date/time line did not match: ' + lines[0].encode('utf-8'))

    ret.location = lines[1]

    gdindex = 3
    match = self.cityRE.match(lines[2])
    if match:
      ret.city = match.group(1)
    elif (not useCity) and self.getDirectionsRE.match(lines[2]):
      # When we're ignoring the city, it's okay for this line to be Get
      # Directions
      gdindex = 2
    else:
      raise InvalidCityException('City line did not match: ' + lines[2].encode('utf-8'))

    match = self.getDirectionsRE.match(lines[gdindex])
    if not match:
      raise InvalidGetDirectionsException('Get directions did not match: ' + lines[gdindex].encode('utf-8'))

    return ret

class exRaidData:
  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)
