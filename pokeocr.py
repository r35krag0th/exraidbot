# This Python file uses the following encoding: utf-8
from PIL import Image
import pyocr
import pyocr.builders
import cv2
import sys
import re
import unicodedata
import json
import calendar
from cv2utils import cv2utils
import dateparser


COMBINE_SPACES_RE = re.compile('\s{1,}').sub

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
  def __init__(self, location_regex):
    self.preferred_language = None
    self.gym_name_corrections = {}
    with open('config/exraid.json', 'r') as fp:
      json_data = json.load(fp)
      self.preferred_language = json_data.get('preferred_language')

      if 'gym_name_corrections' in json_data and isinstance(json_data['gym_name_corrections'], dict):
        # Use a dictionary comprehension to flip the dictionary around.  The "correction_name" should be
        # unique (when case sensitive).
        self.gym_name_corrections = {
          correction_name: actual_name
          for actual_name, correction_names in json_data['gym_name_corrections'].iteritems()
          for correction_name in correction_names
        }

    # Get the first available tool
    self.tool = pyocr.get_available_tools()[0]

    available_languages = self.tool.get_available_languages()
    if self.preferred_language is not None and self.preferred_language in available_languages:
      self.lang = self.preferred_language
    else:
      self.lang = self.tool.get_available_languages()[0]

    self.dateTimeRE = re.compile('^([A-Z][a-z]+)\s+?([0-9]{1,2})\s+([0-9]{1,2}:[0-9]{2} ?[AP]M) .+ ([0-9]{1,2}:[0-9]{2} ?[AP]M)')
    self.cityRE = re.compile(location_regex)
    self.getDirectionsRE = re.compile('Get.*ns')

    self.short_months_to_known_months = {calendar.month_name[a][:3].lower(): calendar.month_name[a] for a in range(1, 13)}
    self.long_month_names = [calendar.month_name[a].lower() for a in range(1,13)]

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

  def fix_datetime_nuances(self, a_string):
    a_string = a_string.replace('|', 'l')

    # Sometimes dash shows up as emdash (unicode 2014)
    a_string = a_string.replace(u'\u2014', '-')

    #
    # Attempt to further shore up issues with Month recognition
    #
    # Get the first three of the month we've been given
    # NOTE:
    #  - Normally [0=Month] [1=Day] [2=Start] [3=Dash] [4=End]
    #  - Alternatively [0=Month] [1=Day] [2=Start] [3=Dash] [4=End]
    date_line_fragments = a_string.split(' ')
    first_three_letters = date_line_fragments[0][:3]  # type: str
    month_fragment = 0
    day_fragment = 1

    use_day_month_format = False

    # print('>>> Date Line Frags: %s' % date_line_fragments)

    if first_three_letters.isdigit():
      # We have "DAY MONTH TIME - TIME"
      month_fragment = 1
      day_fragment = 0
      use_day_month_format = True
      first_three_letters = date_line_fragments[month_fragment][:3]

    # Select the known month
    known_month = self.short_months_to_known_months[first_three_letters.lower()]

    # Find the offset and slice the remainder of the string out
    # gives "Z 1:00 PM - 1:45 PM" from "SeptemberZ 1:00 PM - 1:45 PM"
    remainder_of_string = a_string[len(known_month):]

    if use_day_month_format:
      remainder_of_string = a_string[:len(date_line_fragments[day_fragment])]
      # lines[0] = '%s %s'

    # print('>>> Known Month >>> %s' % known_month)
    # print('>>> Remainder of String >>> %s' % remainder_of_string)

    # OCR tends to confused the following
    # 2 -> Z
    remainder_of_string = remainder_of_string.replace('Z', '2')

    # Replace the string with sanitized goodies.
    if use_day_month_format:
      offset = len(known_month) + len(remainder_of_string) + 1
      a_string = '%s' % ' '.join([
        known_month,
        remainder_of_string,
        a_string[offset:]
      ])
    else:
      a_string = '%s %s' % (known_month, remainder_of_string)

    # print('>>> New String >>> %s' % a_string)
    return a_string

  def cropExRaidImage(self, image, topleft, bottom, debug=False):
    height, width = image.shape[:2]

    # Run the scaling matcher to find the template, then sanity check the
    # match
    ((tl_left, tl_top), (tl_right, tl_bottom)) = cv2utils.scalingMatch(topleft, image)
    ((b_left, b_top), (b_right, b_bottom)) = cv2utils.scalingMatch(bottom, image)
    if not debug:
      val = self.isMatchCentered(width, b_left, b_right)
      if val != True:
        raise MatchNotCenteredException('Bottom template match not centered. Starts at ' + str(b_left) + ', should be ' + str(val))

    # Let's assume that the right offset is the same as the left. We could
    # match on a top-right image, but it would tank performance even more.
    right = width - tl_left

    # Crop the image
    return image[tl_bottom:b_top,tl_left:right]

  def scanExRaidImage(self, image, topleft, bottom, useCity=True, debug=False):
    image = self.cropExRaidImage(image, topleft, bottom)

    # Scale up, which oddly helps with OCR
    height, width = image.shape[:2]
    image = cv2.resize(image, (0,0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # Increase contrast. Must be done before grayscale conversion
    image = cv2utils.increaseContrast(image)

    # Convert to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Convert to PIL format
    pil = Image.fromarray(image)
    # pil.show()

    # OCR the text
    txt = self.tool.image_to_string(
      pil, 
      lang=self.lang, 
      builder=pyocr.builders.TextBuilder()
    )

    # text_two = self.tool.image_to_string(
    #   pil,
    #   lang=self.lang,
    #   builder=pyocr.builders.LineBoxBuilder()
    # )
    #
    # print("\033[36m%s\033[0m" % text_two)
    #
    # for i in text_two:
    #   print(i)
    #   print("\033[33m==> \033[0m%s" % i.content)
    #
    # return

    # Replace any non-ASCII unicode characters with their closest
    # equivalents.  This is bad news for i18n, but helps us with a lot of
    # OCR issues
    txt = unicodedata.normalize('NFKD', txt)

    lines = txt.split("\n")
    # print("LINES ...")
    # print("\033[31m%s\033[0m" % lines)

    # Sometimes OCR will insert extra empty lines, so let's strip them out
    newlines = []
    for i in range(len(lines)):
      stripped_line = lines[i].strip()
      if not len(stripped_line) <= 1 and not stripped_line.startswith('Get directions'):
        newlines.append(lines[i])
    lines = newlines
    # print("\033[33m%s\033[0m" % lines)

    structured_lines = {
      'gym_line': None,
      'city_line': None,
      'datetime_line': None
    }
    for line in lines:
      line = line.replace("'", '').strip()
      line_parts = line.split(' ')
      lpzero = line_parts[0]
      
      # print(u'Checking lines_parts[0] against months --> {lpzero} in {lmn}'.format(
      #   lpzero=lpzero.lower(),
      #   lmn=self.long_month_names
      # ))

      check_a = lpzero.lower() in self.long_month_names
      check_b = lpzero[:3].lower() in self.short_months_to_known_months.keys()
      check_c = lpzero.isdigit() and line_parts[1][:3] in self.short_months_to_known_months.keys()

      # print("LPZero[:3] is %s" % lpzero[:3].lower())
      # print(" LPOne[:3] is %s" % line_parts[1][:3].lower())

      # print("\033[35mCHECK(a) ==> %s (line_part[0] lowercased is in long month names)\033[0m" % check_a)
      # print("\033[35mCHECK(b) ==> %s (line_part[0]'s first three letters are in known short month names)\033[0m" % check_b)
      # print("\033[35mCHECK(c) ==> %s (line_part[0] is a digit AND line_part[1]'s first three digits are in short known short month names)\033[0m" % check_c)

      # Closely check to see if this is a datetime line
      # if lpzero.lower() in self.long_month_names or lpzero[:3].lower() in self.short_months_to_known_months.keys():
      if check_a or check_b or check_c:
        # print("\033[35m---->> OKAY, IS DATE... \033[0m")
        structured_lines['datetime_line'] = self.fix_datetime_nuances(line)
        # print("\033[32m---->> NEW DT STRING is ... %s\033[0m" % structured_lines['datetime_line'])
      else:
        city_check = self.cityRE.match(line)
        if city_check is not None:
          structured_lines['city_line'] = line
        else:
          structured_lines['gym_line'] = line
    # print(u"\033[32m%s\033[0m" % structured_lines)

    if debug:
      return lines

    # So it's actually possible that the lines can be completely out of order...
    # 0 = GYM
    # 1 = CITY
    # 2 = WHEN
    # new_lines = []
    # for line in lines:
    #   print(line)
    lines = [
      normalize_datetime_line(structured_lines['datetime_line']),
      structured_lines['gym_line'],
      structured_lines['city_line'],
      'Get directions'
    ]

    # If we're not going to use the city info anyway, we can process images
    # that are missing it
    if useCity:
      minlines = 4
    else:
      minlines = 3

    if len(lines) < minlines:
      raise TooFewLinesException('Found fewer lines of text than expected')

    ret = exRaidData()

    # print('')
    # print('\033[33m==> Attempting to Match Date/Time -- Try 1\033[0m')

    match = self.dateTimeRE.match(lines[0])
    # print("\033[32m==> Date: \033[0m%s" % lines[0])
    # print(lines)


    if not match:
      # Let's try to work around some common problems

      # "[Month] 5" gets read as "[Month] S".  This should be safe because
      # "S " and " S" shouldn't appear in legitimate date/time
      lines[0] = lines[0].replace('S ', '5 ', 1)
      lines[0] = lines[0].replace(' S', ' 5', 1)

      # Sometimes spaces get dropped. There's no reason a letter and number
      # should appear immediately next to each other in a date line
      lines[0] = re.sub('([0-9])([a-zA-Z])', r'\1 \2', lines[0])
      lines[0] = re.sub('([a-zA-Z])([0-9])', r'\1 \2', lines[0])

      # print('')
      # print('\033[33m==> Attempting to Match Date/Time -- Try 2\033[0m')
      match = self.dateTimeRE.match(lines[0])

    # Sometimes we get a leading jibberish line
    if not match:
      del lines[0]
      match = self.dateTimeRE.match(lines[0])

    if match:
      ret.month = match.group(1)
      ret.day = match.group(2)

      # Sometimes OCR drops the space between the minutes and AM/PM.  Let's
      # just strip all spaces for consistency
      ret.begin = match.group(3).replace(' ', '')
      ret.end = match.group(4).replace(' ', '')
    else:
      raise InvalidDateTimeException('Date/time line did not match: ' + lines[0].encode('utf-8'))

    # If you have problematic OCR results for some gyms, we can maintain overrides here.
    # print(self.gym_name_corrections)
    if lines[1] in self.gym_name_corrections:
      ret.location = self.gym_name_corrections[lines[1]]
    else:
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


def fix_ocr_digit_mistakes(ocr_string):
  """
  For the day or time fields, this will help correct some OCR detection issues

  :param ocr_string:
  :type ocr_string: str
  :return: Corrected String
  :rtype: str
  """
  return ocr_string.replace('S', '5').replace('Z', '2')


def normalize_datetime_line(some_string):
  """
  Take a date string in two formats (12/24hrs as well) and turn it into a normalized
  string that US English uses in the PoGo Client.

  >>> normalize_datetime_line('9 september 17:00 - 17:45')
    September 9 5:00 PM - 5:45 PM

  >>> normalize_datetime_line('September 2 11:00AM - 11:45AM')
    September 2 11:00 AM - 11:45 AM

  :param some_string:
  :type some_string: str
  :return:
  """
  parts = combine_spaces(some_string).replace(' PM', 'PM').replace(' AM', 'AM').split(' ')

  # 0 = month or day
  # 1 = month or day
  # 2 = start time
  # 3 = ***DASH***
  # 4 = end time

  # Apply fixes for commonly mistaken digits
  if parts[0].isdigit():
    parts[0] = fix_ocr_digit_mistakes(parts[0])

  if parts[1].isdigit():
    parts[1] = fix_ocr_digit_mistakes(parts[1])

  for index in range(0, len(parts)):
    if parts[index].find(':') > 0:
      parts[index] = fix_ocr_digit_mistakes(parts[index])

  start_string = ' '.join([
    parts[0],
    parts[1],
    parts[2]
  ])
  end_string = ' '.join([
    parts[0],
    parts[1],
    parts[4]
  ])

  start = dateparser.parse(start_string)
  end = dateparser.parse(end_string)

  # print('*> Start String *> %s' % start_string)
  # print('*> End String   *> %s' % end_string)

  # print('|> Parts |> %s' % parts)
  # print('// START // %s' % start)
  # print('// END   // %s' % end)

  # Terrible python hack since Python 2.7 doesn't understand the concept
  # of non-zero-prefixed datetime stuff.  So annoying.
  return '{month} {day} {start_time} - {end_time}'.format(
    month=start.strftime('%B'),
    day=start.strftime('X%d'),
    start_time=start.strftime('X%I:%M %p'),
    end_time=end.strftime('X%I:%M %p')
  ).replace('X0', 'X').replace('X', '')


def combine_spaces(a_string):
  return COMBINE_SPACES_RE(' ', a_string)
