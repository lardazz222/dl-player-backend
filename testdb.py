from utils import Logger
from database import *

db = Database()

result = db.add_track_from_file("./the_weeknd_i_feel_it_coming.mp3")
print(result)