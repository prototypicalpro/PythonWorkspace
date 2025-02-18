from enum import Enum, unique
import itertools
import random
import json
import cv2
import numpy as np
import os
from PIL import Image as pil_image
from keras.preprocessing import image
from keras.preprocessing.image import ImageDataGenerator
import copy

# Dataset Generation API
# Surroundings (background behind picture)
# Perpsective (rotation and translation)
# Reflection/Glare
# Lighting conditions
# Print fading
# Resolution 330x270
# Type: (left, right, center)

# TODO: Load image according to settings specified by size
# Using PIL and a linear interpolation algorithm to downscale
# Create generator using an ImageDataGenerator to process the data after the initial creation

PATH = 'C:\\Users\\Noah\\Documents\\code\\DataSet'

# Surroundings
# e.g. everywhere the pictogram isn't
@unique
class Surroundings(Enum):
    GENERATED_NOISE = "noise" # noise created by randomizing each pixel
    BLACK = "black" # a solid black
    MISMATCH_BACKGROUND = "misback"
    PICTURE_BACKGROUND = "background" # the background of the photo how it normally is

# Perspective
# contains a rotation and translation object, which can be used to determine how the image
# was processed
class Perspective:
    def __init__(self, rotation, translation): #rotation is (X, Y, Z) and translation is the same
        self.rotation = rotation
        self.translation = translation
    
    # Function to correct the image according to the perspective information
    def getCorrectedImage(self, img):
        #TODO: this function
        return False

# Glare
# Not computer generated, just recorded for informational purposes
@unique
class Glare(Enum):
    PAPER = "paper" # only catches ambient light reflecting off of the paper
    PLASTIC_SLEVE = "plastic" # catches light reflecting off of the plastic sleve
    PLEXIGLASS_COVER = "plexi" # catches light reflecting off of a sctratched plexiglass cover
    FLASHLIGHT_PLEXIGLASS = "flashlight" # flashlight is reflected off of the same plexiglass to intentionally obscure camera 
    # the above is probably closest to real world situations
    # the rest are provided for additional training

# Lighting
# The amount of surrounding lights, arbitrarily assigned values
@unique
class Lighting(Enum):
    NONE = "none" # A dark room
    POOR = "poor" # A not very well lit room
    GOOD = "good" # The best lighting availible given the equipment I have
    # Unfortunatly, we are probably looking at a near dark room due to the sports-like
    # aspect of the competitions later on

# Print Quality
# Again assigned arbitrary values
@unique
class PrintQuality(Enum):
    GOOD = "good" # saturated print
    BAD = "bad" # Faded print

# Pictogram type
# The thing the neural network wants to get
@unique
class PictogramType(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

# Blur, as in we shook the camera on accident
@unique
class Blur(Enum):
    NONE = "none"
    BLURRED = "blur"

# Ball present in image
# Will be present in the right corner of the pictogram if at all
@unique
class Balls(Enum):
    NONE = "none"
    BLUE = "blue"
    RED = "red"

# Class to represent the pictograms location within the image
class PictogramLocation:
    def __init__(self, points): # points are ((x, y), (x, y), (x, y), (x, y)) in pixels of corners 
    # in order of ((bottom left, top left, top right, bottom right)) 
        self.points = points
    # returns just the pictogram image cut out of the rest of the image
    def getLocalizedPictogram(self, img):
        #TODO: this function
        return False


class Pictogram:
    # each bit of data that can be assigned to a given pictogram picture
    # first the path of the image, then please use the above enums
    def __init__(self, img, surroundings, perspective, glare, lighting, printQual, pictogramType, blur, balls, location):
        self.img = img
        self.surroundings = surroundings
        self.perspective = perspective
        self.glare = glare
        self.lighting = lighting
        self.printQual = printQual
        self.pictogramType = pictogramType
        self.blur = blur
        self.balls = balls
        self.picLoc = location

    @classmethod
    def fromDataDict(self, img, surroundings, perspective, location, dataDict):
        return self(
            img,
            surroundings,
            perspective,
            dataDict['glare'],
            dataDict['light'],
            dataDict['print'],
            dataDict['type'],
            dataDict['blur'],
            dataDict['balls'],
            location
        )

# API use example:
# data = GetDataSet(surroundings="bad", type="left")

# img = data.next()

def wrapList(item):
    if hasattr(item, "__len__"):
        return item
    else:
        return [item]

def stringListToCoords(str):
    ray = json.loads('[' + str + ']')
    tempRay = [0, 0, 0, 0]
    # map flat string to coordinate arrays
    if len(ray) > 0:
        for i in range(0, 4):
            tempRay[i] = (ray[i * 2], ray[i * 2 + 1])
        # sort by X coordinate
        tempRay.sort(key=lambda coord: coord[0])
        # if Y of point 0 is greater than Y of point 1 and the opposite is true of the Y's of the next two points, switch em
        # also vice versa
        if (tempRay[0][1] > tempRay[1][1] and tempRay[2][1] > tempRay[3][1]) or (tempRay[0][1] < tempRay[1][1] and tempRay[2][1] < tempRay[3][1]):
            tempRay = (tempRay[0], tempRay[1], tempRay[3], tempRay[2])
        # switch points so origin is always a bottom left
        if tempRay[0][1] < tempRay[1][1]:
            return (tempRay[1], tempRay[0], tempRay[3], tempRay[2])
        else:
            return tempRay
    else:
        return None

def filterPictures(objs, critRay, anyType=False):
    def isMatch(pic):
        SEARCH_KEYS = ['type', 'glare', 'light', 'print', 'blur', 'balls']
        if anyType: 
            del SEARCH_KEYS[0]
        for key in SEARCH_KEYS:
            if(pic[key] != critRay[key].value):
                return False
        return True
    return filter(isMatch, objs)

def DataIterator(dataObject, # the parsed JSON from the dataset'
                 batch_size, # of image to run at once
                 loops, # the # of times to loop through every combination of factor
                 # using different images this time
                 image_generator, #image data generator from keras
                 target_type, # type of pictogram to generate a 1 in the target output
                 size=(64,64), #width/height to scale the image to
                 surroundings=list(Surroundings), 
                 glare=list(Glare),    
                 lighting=list(Lighting), 
                 printQuality=list(PrintQuality), 
                 pictogramType=list(PictogramType), 
                 blur=list(Blur), 
                 balls=list(Balls),
                 randomizePerspective=False): # not currently implemented

    # generate every possible combination
    # check every argument if value or array
    combo = (pictogramType, surroundings, glare, lighting, printQuality, blur, balls)
    combo = map(wrapList, combo)
    # generate every permutation
    combo = itertools.product(*combo)
    # and wrap it into a dict
    combo = list(map(lambda item: {
        'type' : item[0],
        'surr' : item[1],
        'glare' : item[2],
        'light' : item[3],
        'print' : item[4],
        'blur' : item[5],
        'balls' : item[6]
    }, combo))
    # and for every item in that dict, generate and shuffle all the picture possibilities
    # essentially creating a hash table
    for item in reversed(combo):
        # filter the images to the ones we are interested in, then
        # generate a special list for mismatched (since we have to keep track of combonations)
        if item['surr'] == Surroundings.MISMATCH_BACKGROUND:
            # this may take awhile
            # product of all pictogram images and all surrounding images
            item['combo'] = list(itertools.product(filterPictures(dataObject, item), filterPictures(dataObject, item, anyType=True)))
        # else filter and generate a normal list of just possible images
        else:
            item['combo'] = list(filterPictures(dataObject, item))
        # check it's length, if < 0 then remove and continue
        if item['combo'] == None or len(item['combo']) == 0:
            #print("skipping: ")
            #print(item)
            #print("-----")
            combo.remove(item)
            continue

    # iterate through it, returning a new object for each next() call
    i = 0
    while loops == None or i < loops:
        if loops != None: 
            i = i + 1
        # copy the combo array
        perm = copy.deepcopy(combo)
        # shuffle it
        random.shuffle(perm)
        # batch list 
        batch_x = []
        batch_y = []
        # boolean to break at the end of the for loop
        breakEnd = False
        while not breakEnd:
            for item in perm:                    
                # get the a combo from our shuffled list
                picItem = random.choice(item['combo']) # this wil be a list of dicts or a dict
                item['combo'].remove(picItem)
                # check if that list is emptey
                # if so, skip to the next set of image permutations after the end of this cycle
                # this will in theory balance out the catigories of images rather than relying on the images to be equally distributed
                if len(item['combo']) == 0: 
                    breakEnd = True
                # next, initialize the image loaded based on the type of surroundings
                img = None
                # if we have any surroundings except PICTURE_BACKGROUND, do processing
                if item['surr'] == Surroundings.PICTURE_BACKGROUND:
                    img = cv2.imread(os.path.join(PATH, picItem['type'], picItem['name']))
                # mismatch warping
                elif item['surr'] == Surroundings.MISMATCH_BACKGROUND:
                        backData = picItem[1]
                        pictoData = picItem[0]
                        # check if both images have coords
                        # else log and continue
                        if not hasattr(backData['picto'], "__len__") or not hasattr(pictoData['picto'], "__len__"):
                            print("Missing coords on image ")
                            if not hasattr(backData['picto'], "__len__"):
                                print(backData)
                            if not hasattr(pictoData['picto'], "__len__"):
                                print(pictoData)
                            continue
                        # get the background image
                        back = cv2.imread(os.path.join(PATH, backData['type'], backData['name']))
                        # get the pictogram image
                        picto = cv2.imread(os.path.join(PATH, pictoData['type'], pictoData['name']))
                        # check and see if we read the image
                        if not hasattr(back, "__len__") or not hasattr(picto, "__len__"):
                            print("Image failed to read!")
                            if not hasattr(back, "__len__"):
                                print(backData)
                            if not hasattr(picto, "__len__"):
                                print(pictoData)
                            continue
                        # The actual warping code
                        # warp pictograph of picto into position of background
                        pers = cv2.getPerspectiveTransform(np.float32(pictoData['picto']), np.float32(backData['picto']))
                        picto = cv2.warpPerspective(picto, pers, (back.shape[1], back.shape[0]))
                        # warp four point mask matrix to respective points
                        pers = cv2.getPerspectiveTransform(np.float32(((0, 0), (0, back.shape[0]), (back.shape[1], back.shape[0]), (back.shape[1], 0))), np.float32(backData['picto']))
                        mask = cv2.warpPerspective(np.full((back.shape[0], back.shape[1]), 255, dtype=np.uint8), pers, (back.shape[1], back.shape[0]))
                        # bitwise copy
                        img = cv2.bitwise_or(cv2.bitwise_or(0, back, mask=cv2.bitwise_not(mask)), cv2.bitwise_or(0, picto, mask=mask))
                        picItem = backData
                # every other kind of warping
                else:
                    # get image
                    img = cv2.imread(os.path.join(PATH, picItem['type'], picItem['name']))
                    # create mask
                    # warp four point mask matrix to respective points
                    pers = cv2.getPerspectiveTransform(np.float32(((0, 0), (0, img.shape[0]), (img.shape[1], img.shape[0]), (img.shape[1], 0))), np.float32(picItem['picto']))
                    mask = cv2.warpPerspective(np.full((img.shape[0], img.shape[1]), 255, dtype=np.uint8), pers, (img.shape[1], img.shape[0]))
                    # generate image to copy to depending on the type of surroundings
                    back = None
                    if item['surr'] == Surroundings.BLACK:
                        back = np.zeros(img.shape, dtype=np.uint8)
                    elif item['surr'] == Surroundings.GENERATED_NOISE:
                        back = np.random.randint(0, high=255, size=img.shape, dtype=np.uint8)
                    # bitwise copy
                    img = cv2.bitwise_or(cv2.bitwise_or(0, back, mask=cv2.bitwise_not(mask)), cv2.bitwise_or(0, img, mask=mask))
                # apply image transformations from keras onto image
                # downscale image to given size using nearest interpolation
                img = cv2.resize(img, size, interpolation=cv2.INTER_NEAREST)
                img = np.float64(img)
                # randomize image based on generator
                if image_generator != None:
                    img = image_generator.random_transform(img)
                    img = image_generator.standardize(img)
                # append the image to the batches
                batch_x.append(img)
                num = None
                # generate the bianary answer for our network
                if item['type'] == target_type: num = 1.
                else: num = 0.
                # append, and see if we can send off the batch
                batch_y.append(num)
                if(len(batch_x) >= batch_size):
                    yield np.array(batch_x), np.array(batch_y)
                    batch_x = []
                    batch_y = []

"""
# get the JSON and parse it
def mapDict(item):
    str = '[' + item['picto'] + ']'
    ray = json.loads(str)
    tempRay = [0, 0, 0, 0]
    # map flat string to coordinate arrays
    if len(ray) > 0:
        for i in range(0, 4):
            tempRay[i] = (ray[i * 2], ray[i * 2 + 1])
        # sort by X coordinate
        tempRay.sort(key=lambda coord: coord[0])
        # if Y of point 0 is greater than Y of point 1 and the opposite is true of the Y's of the next two points, switch em
        # also vice versa
        if (tempRay[0][1] > tempRay[1][1] and tempRay[2][1] > tempRay[3][1]) or (tempRay[0][1] < tempRay[1][1] and tempRay[2][1] < tempRay[3][1]):
            tempRay = (tempRay[0], tempRay[1], tempRay[3], tempRay[2])
        # switch points so origin is always a bottom left
        if tempRay[0][1] < tempRay[1][1]:
            item['picto'] = (tempRay[1], tempRay[0], tempRay[3], tempRay[2])
        else:
            item['picto'] = tempRay
    else:
        item['picto'] = None
    return item

with open("mostOfThem.json", 'r') as f:
    data = json.load(f)

data = list(map(mapDict, filter(lambda item: item['type'] != 'none', data)))

test_datagen = ImageDataGenerator(rescale=1./255)

train_datagen = ImageDataGenerator(rescale=1./255,
                                   shear_range=0.2,
                                   zoom_range=0.2,
                                   horizontal_flip=True)

iter = DataIterator(data, 
                32, 
                None, 
                train_datagen,
                PictogramType.LEFT, 
                pictogramType=(PictogramType.CENTER, PictogramType.LEFT))

for item in iter:
    print(len(item[0]))
    for i in range(len(item[0])):
        if not hasattr(item[0][i], "__len__") or not hasattr(item[0][i], "shape"):
            print(i)
            raise ValueError("HUR DUR")
"""