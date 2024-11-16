# -*- coding: utf-8 -*-
"""Plant_Disease_Detection.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Emd16eIuV2JXgmextk9VaN94OoBksAgr

**Plant Disease Detection**

**Machine Learning model using Tensorflow with Keras**

We designed algorithms and models to recognize species and diseases in the crop leaves by using Convolutional Neural Network

**Importing the Librairies**
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import tensorflow as tf
import tensorflow_hub as hub
from tensorflow.keras.applications import VGG16,VGG19
from tensorflow.keras.layers import Flatten, Dense, Dropout
import os
from zipfile import ZipFile
from urllib.request import urlretrieve
import time
from os.path import exists
from PIL import Image
import json
import matplotlib.pylab as plt
import numpy as np

# Import OpenCV
import cv2

# Utility
import itertools
import random
from collections import Counter
from glob import iglob

import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

"""**Mount Google Drive**"""

from google.colab import drive
drive.mount('/content/drive')

"""**Load the data**

We will download a public dataset of 54,305 images of diseased and healthy plant leaves collected under controlled conditions ( PlantVillage Dataset). The images cover 14 species of crops, including: apple, blueberry, cherry, grape, orange, peach, pepper, potato, raspberry, soy, squash, strawberry and tomato. It contains images of 17 basic diseases, 4 bacterial diseases, 2 diseases caused by mold (oomycete), 2 viral diseases and 1 disease caused by a mite. 12 crop species also have healthy leaf images that are not visibly affected by disease. Then store the downloaded zip file to the "/tmp/" directory.

we'll need to make sure the input data is resized to 224x224 or 229x229 pixels as required by the networks.
"""

from google.colab import files
files.upload()

! mkdir ~/.kaggle
! cp kaggle.json ~/.kaggle/
!chmod 600 ~/.kaggle/kaggle.json

!kaggle datasets download -d mohitsingh1804/plantvillage

!unzip {'plantvillage.zip'}

"""**Prepare training and validation dataset**

Create the training and validation directories
"""

data_dir = os.path.join(os.getcwd(), 'PlantVillage')
train_dir = os.path.join(data_dir, 'train')
validation_dir = os.path.join(data_dir, 'val')

def count(dir, counter=0):
    "returns number of files in dir and subdirs"
    for pack in os.walk(dir):
        for f in pack[2]:
            counter += 1
    return dir + " : " + str(counter) + "files"

print('total images for training :', count(train_dir))
print('total images for validation :', count(validation_dir))

# Get a list of subfolder names
subfolder_names = [f for f in os.listdir(train_dir) if os.path.isdir(os.path.join(train_dir, f))]

# Iterate through each subfolder
for folder_name in subfolder_names:
  folder_path = os.path.join(train_dir, folder_name)

  # Display the folder name
  print(folder_name)

  # Display the first image in the folder
  image_list = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
  first_image_path = os.path.join(folder_path, image_list[0])
  image = Image.open(first_image_path)
  display(image)

"""**Label mapping**

You'll also need to load in a mapping from category label to category name. You can find this in the file categories.json. It's a JSON object which you can read in with the json module. This will give you a dictionary mapping the integer encoded categories to the actual names of the plants and diseases.
"""

categories_file_path = "/content/drive/MyDrive/saved models/categories.json"

with open(categories_file_path, 'r') as file:
   # file_content = file.read()
#with open('Plant-Diseases-Detector-master/categories.json', 'r') as f:
    cat_to_name = json.load(file)
    classes = list(cat_to_name.values())

print('Number of classes:',len(classes))
print (classes)

"""**Setup Image shape and batch size**"""

module_selection = ("mobilenet_v2", 224, 1280) #@param ["(\"mobilenet_v2\", 224, 1280)", "(\"inception_v3\", 299, 2048)", "(\"VGG16\", 224, 4096)", "(\"VGG19\", 224, 4096)"] {type:"raw", allow-input: true}
handle_base, pixels, FV_SIZE = module_selection
IMAGE_SIZE = (pixels, pixels)
BATCH_SIZE = 64 #@param {type:"integer"}

"""**Data Preprocessing**"""

# Inputs are suitably resized for the selected module.
validation_datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1./255)
validation_generator = validation_datagen.flow_from_directory(
    validation_dir,
    shuffle=False,
    seed=42,
    color_mode="rgb",
    class_mode="categorical",
    target_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE)
do_data_augmentation = True #@param {type:"boolean"}
if do_data_augmentation:
  train_datagen = tf.keras.preprocessing.image.ImageDataGenerator(
      rescale = 1./255,
      rotation_range=40,
      horizontal_flip=True,
      width_shift_range=0.2,
      height_shift_range=0.2,
      shear_range=0.2,
      zoom_range=0.2,
      fill_mode='nearest' )
else:
  train_datagen = validation_datagen

train_generator = train_datagen.flow_from_directory(
    train_dir,
    subset="training",
    shuffle=True,
    seed=42,
    color_mode="rgb",
    class_mode="categorical",
    target_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE)

"""**Build the model**

All it takes is to put a linear classifier on top of the feature_extractor_layer with the Hub module.

For speed, we start out with a non-trainable feature_extractor_layer, but you can also enable fine-tuning for greater accuracy.
"""

if (handle_base == 'mobilenet_v2' or handle_base == 'inception_v3'):
  MODULE_HANDLE ="https://tfhub.dev/google/tf2-preview/{}/feature_vector/2".format(handle_base)
  feature_extractor = hub.KerasLayer(MODULE_HANDLE,
                                   input_shape=IMAGE_SIZE + (3,),
                                   output_shape=[FV_SIZE])
  do_fine_tuning = False  # @param {type:"boolean"}
  if do_fine_tuning:
      feature_extractor.trainable = True
      # unfreeze some layers of the base network for fine-tuning
      for layer in feature_extractor.layers[-30:]:
          layer.trainable = True
  else:
      feature_extractor.trainable = False

  model = tf.keras.Sequential([
    feature_extractor,
    Flatten(),
    Dense(512, activation='relu'),
    Dropout(rate=0.2),
    Dense(train_generator.num_classes, activation='softmax',
                           kernel_regularizer=tf.keras.regularizers.l2(0.0001))
])

if (handle_base == 'VGG16' or handle_base == 'VGG19'):
  if (handle_base == 'VGG16'):
    base_model = VGG16(weights='imagenet', include_top=False, input_shape=(pixels, pixels, 3))
    base_model.trainable = False


  if (handle_base == 'VGG19'):
    base_model = VGG19(weights='imagenet', include_top=False, input_shape=(pixels, pixels, 3))
    base_model.trainable = False


  # Build model
  model = tf.keras.Sequential([
      base_model,
      Flatten(),
      Dense(512, activation='relu'),
      Dropout(rate=0.2),
      Dense(train_generator.num_classes, activation='softmax',
            kernel_regularizer=tf.keras.regularizers.l2(0.0001))
  ])

"""**Specify Loss Function and Optimizer**"""

#Compile model specifying the optimizer learning rate
LEARNING_RATE = 0.001 #@param {type:"number"}
model.compile(
   optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
   loss='categorical_crossentropy',
   metrics=['accuracy'])

"""**Train Model**

**train model using validation dataset for validate each steps**
"""

import csv
import tensorflow.keras.backend as K
from tensorflow import keras
import os

model_directory='/content/drive/MyDrive/saved models/' # directory to save model history after every epoch
class StoreModelHistory(keras.callbacks.Callback):

  def on_epoch_end(self,batch,logs=None):
    if ('lr' not in logs.keys()):
      logs.setdefault('lr',0)
      logs['lr'] = K.get_value(self.model.optimizer.lr)

    if not (handle_base+'model_history.csv' in os.listdir(model_directory)):
      with open(model_directory+handle_base+'model_history.csv','a') as f:
        y=csv.DictWriter(f,logs.keys())
        y.writeheader()

    with open(model_directory+handle_base+'model_history.csv','a') as f:
      y=csv.DictWriter(f,logs.keys())
      y.writerow(logs)


EPOCHS=10 #@param {type:"integer"}
STEPS_EPOCHS = train_generator.samples//train_generator.batch_size
VALID_STEPS=validation_generator.samples//validation_generator.batch_size
history = model.fit(
          train_generator,
          steps_per_epoch=400,
          epochs=EPOCHS,
          validation_data=validation_generator,
          validation_steps=VALID_STEPS,
          callbacks=[StoreModelHistory()])


model.save(model_directory+handle_base)

"""**Load Model & History**"""

import pandas as pd
from tensorflow.keras.models import load_model

model_directory='/content/drive/MyDrive/saved models/' # directory to save model history after every epoch

history = pd.read_csv(model_directory+handle_base+'model_history.csv',sep=',')
model = load_model("/content/drive/MyDrive/saved models/"+handle_base)

print(history)

"""
**Check Performance**

Plot training and validation accuracy and loss

**Random test**

Random sample images from validation dataset and predict"""

acc = history['accuracy']
val_acc = history['val_accuracy']
loss = history['loss']
val_loss = history['val_loss']
epochs_range = range(10)
plt.figure(figsize=(8, 8))
plt.subplot(1, 2, 1)
plt.plot(epochs_range, acc, label='Training Accuracy')
plt.plot(epochs_range, val_acc, label='Validation Accuracy')
plt.legend(loc='lower right')
plt.title('Training and Validation Accuracy')
plt.ylabel("Accuracy (training and validation)")
plt.xlabel("Training Steps")
plt.subplot(1, 2, 2)
plt.plot(epochs_range, loss, label='Training Loss')
plt.plot(epochs_range, val_loss, label='Validation Loss')
plt.legend(loc='upper right')
plt.title('Training and Validation Loss')
plt.ylabel("Loss (training and validation)")
plt.xlabel("Training Steps")
plt.show()

def load_image(filename):
    img = cv2.imread(os.path.join(data_dir, validation_dir, filename))
    img = cv2.resize(img, (IMAGE_SIZE[0], IMAGE_SIZE[1]) )
    img = img /255

    return img


def predict(image):
    probabilities = model.predict(np.asarray([img]))[0]
    class_idx = np.argmax(probabilities)

    return {classes[class_idx]: probabilities[class_idx]}

for idx, filename in enumerate(random.sample(validation_generator.filenames, 5)):
    print("SOURCE: class: %s, file: %s" % (os.path.split(filename)[0], filename))

    img = load_image(filename)
    prediction = predict(img)
    print("PREDICTED: class: %s, confidence: %f" % (list(prediction.keys())[0], list(prediction.values())[0]))
    plt.imshow(img)
    plt.figure(idx)
    plt.show()

"""
**Confusion Matrix and Classification Report**"""

# Function to get predictions for all validation data
def get_predictions(generator, model):
    predictions = []
    true_labels = []

    # Loop through batches of validation data
    for i in range(generator.samples // generator.batch_size):
        x, y_true = generator.next()

        # Get model predictions
        y_pred = model.predict(x)

        # Append true labels and predictions
        true_labels.extend(np.argmax(y_true, axis=1))
        predictions.extend(np.argmax(y_pred, axis=1))

    return np.array(true_labels), np.array(predictions)

# Get true labels and predictions
true_labels, predictions = get_predictions(validation_generator, model)

# Compute confusion matrix
cm = confusion_matrix(true_labels, predictions)

# Print confusion matrix
print("Confusion Matrix:")
print(cm)

# Function to plot confusion matrix
def plot_confusion_matrix(conf_matrix, class_names, normalize=False):
    if normalize:
        conf_matrix = conf_matrix.astype('float') / conf_matrix.sum(axis=1)[:, np.newaxis]

    plt.figure(figsize=(18, 18))
    sns.heatmap(conf_matrix, annot=True, fmt="g" if normalize else "d", cmap="Blues", xticklabels=class_names, yticklabels=class_names)
    plt.title("Normalized Confusion Matrix" if normalize else "Confusion Matrix")
    plt.ylabel('Prediction',fontsize=5)
    plt.xlabel('Actual',fontsize=5)

    plt.show()

#confusion matrix
plot_confusion_matrix(cm, classes)

# Compute classification report
class_report = classification_report(true_labels, predictions, target_names=classes)

# Print classification report
print("\nClassification Report:")
print(class_report)

"""**Export as saved model and convert to TFLite**

Now that you've trained the model, export it as a saved model
"""

t = time.time()
print(tf.__version__)
export_path = "/tmp/saved_models/{}".format(int(t))
#tf.saved_model.save(model, export_path)
tf.keras.models.save_model(model, export_path)
export_path

# Now confirm that we can reload it, and it still gives the same results
reloaded = tf.keras.models.load_model(export_path, custom_objects={'KerasLayer': hub.KerasLayer})

def predict_reload(image):
    probabilities = reloaded.predict(np.asarray([img]))[0]
    class_idx = np.argmax(probabilities)

    return {classes[class_idx]: probabilities[class_idx]}

for idx, filename in enumerate(random.sample(validation_generator.filenames, 2)):
    print("SOURCE: class: %s, file: %s" % (os.path.split(filename)[0], filename))

    img = load_image(filename)
    prediction = predict_reload(img)
    print("PREDICTED: class: %s, confidence: %f" % (list(prediction.keys())[0], list(prediction.values())[0]))
    plt.imshow(img)
    plt.figure(idx)
    plt.show()

"""**Convert Model to TFLite**"""

# convert the model to TFLite
!mkdir "tflite_models"
TFLITE_MODEL = "tflite_models/plant_disease_model.tflite"


# Get the concrete function from the Keras model.
run_model = tf.function(lambda x : reloaded(x))

# Save the concrete function.
concrete_func = run_model.get_concrete_function(
    tf.TensorSpec(model.inputs[0].shape, model.inputs[0].dtype)
)

# Convert the model to standard TensorFlow Lite model
converter = tf.lite.TFLiteConverter.from_concrete_functions([concrete_func])
converted_tflite_model = converter.convert()
open(TFLITE_MODEL, "wb").write(converted_tflite_model)