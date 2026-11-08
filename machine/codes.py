"""Numbers the watch understands: element kinds, data sources and tap targets.

Everything here was read out of existing watch faces and checked against what they
draw. Entries marked 'verified' were confirmed on a real watch with faces built by
this machine; the rest are observed usage, likely but untested.
"""

# ---- element kinds: (kind number, field that carries the element body)
IMAGE = 1          # static picture                                   verified
IMAGE_LIST = 2     # picture chosen by a data value                   verified
NUMBER = 3         # value drawn from a digit set                     verified
HAND = 5           # picture rotated around a pivot                   verified
PROGRESS = 6       # picture revealed in proportion to a value         observed
TEXT = 0           # value written in the system font                 observed
TEXT_FORMATTED = 10  # system-font value with a unit or format       observed
ARC = 7            # picture revealed along an arc                    observed

# Frame animations are not elements: they sit in their own field of a group.

BODY_FIELD = {TEXT: 3, IMAGE: 4, IMAGE_LIST: 5, NUMBER: 6, HAND: 8, PROGRESS: 9,
              ARC: 10, TEXT_FORMATTED: 11}

# ---- number alignment
ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT = 0, 1, 2   # right: verified

# ---- data sources for image lists (index into the list)
HOUR_TENS = 59         # 0..2                                          verified
HOUR_UNITS = 60        # 0..9                                          verified
MINUTE_TENS = 61       # 0..5                                          verified
MINUTE_UNITS = 62      # 0..9                                          verified
SECOND_TENS = 63       # 0..5                                          verified
SECOND_UNITS = 64      # 0..9                                          verified
MONTH = 51             # 1..12, list needs a dummy at index 0          verified
WEEKDAY = 52           # 1..7 from Monday, dummy at index 0            verified
WEATHER_ICON = 53      # 0..10, order in WEATHER_STATES is observed   verified
BATTERY_LEVEL = 54     # 0..10, tenths of charge                       verified
DAY_TENS = 70          # 0..3                                          observed
DAY_UNITS = 71         # 0..9                                          observed
UNREAD_MESSAGES = 72   # 0 none, 1 some                                observed

# ---- data sources for numbers and text
STEPS = 0              # verified
CALORIES = 1           # observed
HEART_RATE = 2         # verified
TEMPERATURE = 4        # current, needs a minus image                  verified
TEMPERATURE_HIGH = 20  # observed
TEMPERATURE_LOW = 21   # observed
BATTERY_PERCENT = 9    # verified
DAY_OF_MONTH = 17      # verified
HOURS = 12             # observed
MINUTES = 13           # observed
SECONDS = 14           # observed
SUNRISE = 121          # text only                                     observed
SUNSET = 122           # text only                                     observed

# ---- data sources for progress bars and arcs (share of a goal or a range)
PROGRESS_CALORIES = 158  # observed
PROGRESS_STEPS = 161     # observed
PROGRESS_BATTERY = 163   # observed

# ---- data sources for hands
HAND_HOUR = 150        # verified
HAND_MINUTE = 153      # verified
HAND_SECOND = 154      # observed

# ---- weather icon order for WEATHER_ICON
WEATHER_STATES = ['unknown', 'sunny', 'clear night', 'cloudy', 'partly cloudy', 'rain',
                  'thunderstorm', 'snow', 'wind', 'haze', 'fog']

# ---- tap targets: what a touch zone opens
OPEN_STEPS = 10        # verified
OPEN_HEART_RATE = 11   # verified
OPEN_WEATHER = 21      # verified
OPEN_SETTINGS = 50     # observed
OPEN_BATTERY = 17      # does nothing on newer watches                 verified
OPEN_MESSAGES = 18     # observed

# ---- function codes of choice slots: the editor lists slots under these names
#      and folds slots that share a code, so variants of one thing need distinct codes
FUNCTION_DATE = 1      # shown as Date                                  verified
FUNCTION_WEEKDAY = 2   # shown as Day of week                           verified
FUNCTION_SUN = 9       # shown as Sun                                   verified
