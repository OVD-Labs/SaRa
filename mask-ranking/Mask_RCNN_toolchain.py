import os
import sys
import random
import cv2
import math
import numpy as np
import skimage.io
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import tensorflow as tf
import keras
import h5py
# import SaRa
import saraRC1 as sara

'''
Requirements:
    Tensorflow version: 1.5.0
    Keras version: 2.2.5
    Python version: 3.6.12

Software will run Mask RCNN on an image in the images folder and return the result.
'''
# SaRa segment dimensions
SEG_DIM = 8
# SaRa threshold
T = 0.6

# Variable to hold the current image
current_image = None

# Root directory of the project
ROOT_DIR = os.path.abspath("./")

# Import Mask RCNN
sys.path.append(ROOT_DIR)  # To find local version of the library
from mrcnn import utils
import mrcnn.model as modellib
from mrcnn import visualize
# Import COCO config
sys.path.append(os.path.join(ROOT_DIR, "samples/coco/"))  # To find local version
import coco

# Directory to save logs and trained model
MODEL_DIR = os.path.join(ROOT_DIR, "logs")

# Local path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
# Download COCO trained weights from Releases if needed
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)

# Directory of images to run detection on
IMAGE_DIR = os.path.join(ROOT_DIR, "images")

# Set the config
class InferenceConfig(coco.CocoConfig):
    # Set batch size to 1 since we'll be running inference on
    # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1

config = InferenceConfig()
# config.display()

# Create model object in inference mode.
model = modellib.MaskRCNN(mode="inference", model_dir=MODEL_DIR, config=config)

# Load weights trained on MS-COCO
model.load_weights(COCO_MODEL_PATH, by_name=True)

# COCO Class names
# Index of the class in the list is its ID. For example, to get ID of
# the teddy bear class, use: class_names.index('teddy bear')
class_names = ['BG', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
               'bus', 'train', 'truck', 'boat', 'traffic light',
               'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird',
               'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear',
               'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie',
               'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
               'kite', 'baseball bat', 'baseball glove', 'skateboard',
               'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
               'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
               'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
               'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
               'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
               'keyboard', 'cell phone', 'microwave', 'oven', 'toaster',
               'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
               'teddy bear', 'hair drier', 'toothbrush']


def get_mask_rcnn_object_detection(image_id):
    # Load a random image from the images folder
    file_names = next(os.walk(IMAGE_DIR))[image_id]
    image = skimage.io.imread(os.path.join(IMAGE_DIR, random.choice(file_names)))
    current_image = image

    # Run detection
    results = model.detect([image], verbose=1)

    # Visualize results
    result = results[0]
    visualize.display_instances(image, result['rois'], result['masks'], result['class_ids'], 
                                class_names, result['scores'])
    return image, results


def get_mask_rcnn_masks(image, results):
    result = results[0]
    visualize.display_top_masks(image, result['masks'], result['class_ids'], 
                            class_names)
    
    # Get the masks for the objects
    masks = {}

    for i in range(len(results[0]['class_ids'])):
        masks[i] = {}
        masks[i]['mask'] = np.array(results[0]['masks'][:, :, i], dtype=np.uint8) * 255

    # Grouping masks together in one image
    all_masks = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)

    for i in range(len(results[0]['class_ids'])):
        all_masks += masks[i]['mask']
        
    return masks, all_masks


def plot_sara_heatmap(im, grid_size, name=None):
    '''
    Given an image im, this function plots the heatmap generated by SaRa for the given grid size.
    '''

    heatmap, _ = sara.return_sara(im.copy(), grid_size)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    plt.figure(name + ' SaRa Output - Grid Size ' +
               str(grid_size) + ' x ' + str(grid_size))
    plt.gcf().set_size_inches(12, 6)
    plt.imshow(heatmap)
    plt.xticks([])
    plt.yticks([])
    plt.title('SaRa Output - Grid Size ' +
              str(grid_size) + ' x ' + str(grid_size))
    

def get_sara_ranking(image, grid_size):
    return sara.return_sara(image.copy(), grid_size)


def index_to_coordinates(index, grid_size, im_size):
    '''
    Given an index and a shape, this function returns the corresponding coordinates.
    '''

    x1 = int((index % grid_size) * (im_size[1] / grid_size))
    y1 = int((index // grid_size) * (im_size[0] / grid_size))

    x2 = int(x1 + (im_size[1] / grid_size))
    y2 = int(y1 + (im_size[0] / grid_size))
    
    return (x1, y1, x2, y2)

def get_mask_segments(image, sara_list, masks):
    
    # For each segment, check which mask falls under that segment using MRn = rank(Gi); (Gi interesect Mn) > T
    mask_segments = {}

    for segment in sara_list:
        # Convert index to coordinates, extract segment from heatmap
        x1, y1, x2, y2 = index_to_coordinates(segment[5], SEG_DIM, image.shape)

        for m in masks:
            if m not in mask_segments:
                mask_segments[m] = []

            # Extract mask from masks
            mask = masks[m]['mask'][y1:y2, x1:x2]

            # Calculate intersection over union
            intersection = np.sum(mask > 0)
            union = np.sum(mask > 0) + np.sum(mask == 0)

            iou = intersection / union

            # print('Segment: ', segment[2], 'Mask: ', m, 'IoU: ', iou)

            if iou > T:
                # index, rank
                mask_segments[m].append((segment[2], segment[0]))
        
    # For each mask, find the segment with the lowest rank
    mask_segments_min = {}

    for m in mask_segments:
        mask_segments_min[m] = min(mask_segments[m], key=lambda x: x[1])[0]

    mask_segments_min

    return mask_segments, mask_segments_min

def get_mask_segments_info(image, sara_list, masks):
    # For each segment, check which mask falls under that segment using MRn = rank(Gi); (Gi interesect Mn) > T
    mask_info = {}

    for segment in sara_list:
        # Convert index to coordinates, extract segment from heatmap
        x1, y1, x2, y2 = index_to_coordinates(segment[5], SEG_DIM, image.shape)

        for m in masks:
            if m not in mask_info:
                mask_info[m] = {}

            # Extract mask from masks
            mask = masks[m]['mask'][y1:y2, x1:x2]

            # Calculate intersection over union
            intersection = np.sum(mask > 0)
            union = np.sum(mask > 0) + np.sum(mask == 0)

            iou = intersection / union

            # print('Segment: ', segment[2], 'Mask: ', m, 'IoU: ', iou)

            if iou > T:
                # find tuple in sara_list where index = segment[2]
                i = 0
                while i < len(sara_list):
                    if sara_list[i][0] == segment[2]:
                        break
                    i += 1

                # Calculate entropy
                entropy = sara_list[i][1]
                # index, rank, iou, entropy
                if 'segments' not in mask_info[m]:
                    mask_info[m]['segments'] = []
                
                mask_info[m]['segments'].append((segment[2], segment[0], iou, entropy))

                # print('Segment: ', segment[2], 'Mask: ', m, 'IoU: ', iou, 'Entropy: ', entropy)
    
    # For each mask, find the segment with the lowest rank
    mask_segments_min = {}

    for m in mask_info:
        # rank, segment iou, segment entropy
        mask_segments_min[m] = [
            min(mask_info[m]['segments'], key=lambda x: x[1])[0],
            min(mask_info[m]['segments'], key=lambda x: x[1])[2],
            min(mask_info[m]['segments'], key=lambda x: x[1])[3]
        ]
    
    return mask_info, mask_segments_min

def get_colored_masks(image, masks, mask_segments_min):
    # Generating random colors for each rank
    num_ranks = len(mask_segments_min)
    rank_colors = [np.random.randint(0, 256, size=(1, 3), dtype=np.uint8) for _ in range(num_ranks)]

    # Ensuring that the colors are all unique
    while len(rank_colors) != len(set([tuple(color[0]) for color in rank_colors])):
        rank_colors = [np.random.randint(0, 256, size=(1, 3), dtype=np.uint8) for _ in range(num_ranks)]

    # Converting the colors to RGBA format
    rgba_colors = [(color[0][0] / 255, color[0][1] / 255, color[0][2] / 255, 1.0) for color in rank_colors]

    # Creating legend items
    legend_items = [Line2D([0], [0], marker='o', markerfacecolor=color, markersize=10, label=f"Rank: {rank}")
                    for rank, color in zip(mask_segments_min.values(), rgba_colors)]

    # Creating combined mask image
    combined_mask_image = np.zeros_like(image)
    for i, rank in enumerate(mask_segments_min):
        mask = masks[rank]['mask']
        # Creating a new image with the assigned color applied to white parts of the mask
        masked_image = combined_mask_image.copy()
        random_color = rank_colors[i]
        masked_image[mask > 0] = random_color

        # Combining the masked image with the original image
        combined_mask_image = cv2.bitwise_or(combined_mask_image, masked_image)

    # Displaying the resulting image with the legend
    plt.figure(figsize=(8, 8))
    plt.imshow(combined_mask_image)
    plt.legend(handles=legend_items, loc='upper left')
    plt.title("Color Ranked Masks")
    plt.axis('off')
    plt.show()

    # Saving the rank colors in a dictionary based on ranks
    rank_colors_dict = {}
    for rank, color in zip(mask_segments_min.values(), rgba_colors):
        rank_colors_dict[rank] = color

    return combined_mask_image, rank_colors_dict
