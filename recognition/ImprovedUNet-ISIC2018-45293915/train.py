import os
import tensorflow as tf
from tensorflow import keras
import numpy as np
import matplotlib.pyplot as plt
from itertools import islice
import math
from keras.callbacks import Callback
import time

import modules as layers
from dataset import DataLoader

# string modifier for saving output files based on time
timestr = time.strftime("%Y%m%d-%H%M%S")
output_dir = "output"

# Constants related to training
EPOCHS = 5
LEARNING_RATE = 0.0005
BATCH_SIZE = 2  # set the batch_size
IMAGE_HEIGHT = 512  # the height input images are scaled to
IMAGE_WIDTH = 512  # the width input images are scaled to
CHANNELS = 3
STEPS_PER_EPOCH_TRAIN = math.floor(2076 / BATCH_SIZE)
STEPS_PER_EPOCH_TEST = math.floor(519 / BATCH_SIZE)
NUMBER_SHOW_TEST_PREDICTIONS = 3



# Define a callback to calculate Dice coefficient after each epoch
class DiceCoefficientCallback(Callback):
    def __init__(self, test_gen, steps_per_epoch_test):
        self.test_gen = test_gen
        self.steps_per_epoch_test = steps_per_epoch_test
        self.dice_coefficients = []

    def on_epoch_end(self, epoch, logs=None):
        test_loss, test_accuracy, test_dice = \
            self.model.evaluate(self.test_gen, steps=self.steps_per_epoch_test, verbose=0, use_multiprocessing=False)
        self.dice_coefficients.append(test_dice)
        print(f"Epoch {epoch + 1} - Test Dice Coefficient: {test_dice:.4f}")


# Plot the accuracy and loss curves of model training.
def plot_accuracy_loss(track):
    plt.figure(0)
    plt.plot(track.history['accuracy'])
    plt.plot(track.history['loss'])
    plt.title('Loss & Accuracy Curves')
    plt.xlabel('Epoch')
    plt.legend(['Accuracy', 'Loss'])
    
    # Generate a unique filename based on the current date and tim
    filename = os.path.join(output_dir, f"accuracy_loss_plot_{timestr}.png")
    
    # Save the plot to the output folder
    plt.savefig(filename, bbox_inches='tight', pad_inches=0.1)
    plt.close()

    print(f"Accuracy and loss plot saved as '{filename}'.")


# Metric for how similar two sets (prediction vs truth) are.
# Implementation based off https://en.wikipedia.org/wiki/S%C3%B8rensen%E2%80%93Dice_coefficient
# DSC = (2|X & Y|) / (|X| + |Y|) -> 'soft' dice coefficient.
def dice_coefficient(truth, pred, eps=1e-7, axis=(1, 2, 3)):
    numerator = (2.0 * (tf.reduce_sum(pred * truth, axis=axis))) + eps
    denominator = tf.reduce_sum(pred, axis=axis) + tf.reduce_sum(truth, axis=axis) + eps
    dice = tf.reduce_mean(numerator / denominator)
    return dice


# Loss function - DSC distance.
def dice_loss(truth, pred):
    return 1.0 - dice_coefficient(truth, pred)


# Plot the dice coefficient curve and save it as an image
def save_dice_coefficient_plot(dice_history):
    filename = os.path.join(output_dir, f"dice_coefficient_plot_{timestr}.png")
    plt.figure(1)
    plt.plot(dice_history)
    plt.title('Dice Coefficient Curve')
    plt.xlabel('Epoch')
    plt.ylabel('Dice Coefficient')
    plt.savefig(filename)  # Save the plot as an image
    plt.close()  # Close the figure to release resources
    print("Dice coefficeint saved as " + filename + ".")



def train_model_check_accuracy(train_gen, test_gen):
    model = layers.improved_unet(IMAGE_WIDTH, IMAGE_HEIGHT, CHANNELS)
    model.summary()
    # Define the DiceCoefficientCallback
    dice_coefficient_callback = DiceCoefficientCallback(test_gen, STEPS_PER_EPOCH_TEST)
    model.compile(optimizer=keras.optimizers.Adam(LEARNING_RATE),
                  loss=dice_loss, metrics=['accuracy', dice_coefficient])
    track = model.fit(
        train_gen,
        steps_per_epoch=STEPS_PER_EPOCH_TRAIN,
        epochs=EPOCHS,
        shuffle=True,
        verbose=1,
        use_multiprocessing=False,
        callbacks=[dice_coefficient_callback])  # Add the callback her
    plot_accuracy_loss(track)  # Plot accuracy and loss curves

    print("\nEvaluating test images...")
    test_loss, test_accuracy, test_dice = \
        model.evaluate(test_gen, steps=STEPS_PER_EPOCH_TEST, verbose=2, use_multiprocessing=False)
    print("Test Accuracy: " + str(test_accuracy))
    print("Test Loss: " + str(test_loss))
    print("Test DSC: " + str(test_dice) + "\n")
    
    return model, track.history['dice_coefficient']


# Test and visualize model predictions with a set amount of test inputs.
def test_visualise_model_predictions(model, test_gen):
    test_range = np.arange(0, stop=NUMBER_SHOW_TEST_PREDICTIONS, step=1)
    
    for i in test_range: 
        current = next(islice(test_gen, i, None))
        image_input = current[0]  # Image tensor
        mask_truth = current[1]  # Mask tensor
        # debug statements to check the types of the tensors and find the division by zero
        test_pred = model.predict(image_input, steps=1, use_multiprocessing=False)[0]
        truth = mask_truth[0]
        original = image_input[0]
        probabilities = keras.preprocessing.image.img_to_array(test_pred)
        test_dice = dice_coefficient(truth, test_pred, axis=None)


        # Create a unique filename for each visualization
        filename = os.path.join(output_dir, f"visualization_{i}_{timestr}.png")

        # Create a subplot for the visualization
        figure, axes = plt.subplots(1, 3)
        
        # Plot and save the input image
        axes[0].title.set_text('Input')
        axes[0].imshow(original, vmin=0.0, vmax=1.0)
        axes[0].set_axis_off()
        
        # Plot and save the model's output
        axes[1].title.set_text('Output (DSC: ' + str(test_dice.numpy()) + ")")
        axes[1].imshow(probabilities, cmap='gray', vmin=0.0, vmax=1.0)
        axes[1].set_axis_off()
        
        # Plot and save the ground truth
        axes[2].title.set_text('Ground Truth')
        axes[2].imshow(truth, cmap='gray', vmin=0.0, vmax=1.0)
        axes[2].set_axis_off()

        # Save the visualization to the output folder
        plt.axis('off')
        plt.savefig(filename, bbox_inches='tight', pad_inches=0.1)
        plt.close()

    print("Visualizations saved in the 'output' folder.")


# Run the test driver.
def main():
    # Constants related to preprocessing
    train_dir = "datasets/training_input"
    train_groundtruth_dir = "datasets/training_groundtruth"
    validation_dir = "datasets/validation_input"
    validation_groundtruth_dir = "datasets/validation_groundtruth"
    image_mode = "rgb"
    mask_mode = "grayscale"
    image_height = 512
    image_width = 512
    batch_size = 2
    seed = 45
    shear_range = 0.1
    zoom_range = 0.1
    horizontal_flip = True
    vertical_flip = True
    fill_mode = 'nearest'

    # print number of images in each directory
    print("Number of images in training_input:", len(os.listdir(train_dir)))
    print("Number of images in validation_input:", len(os.listdir(validation_dir)))
    print("Number of images in training_groundtruth:", len(os.listdir(train_groundtruth_dir)))
    print("Number of images in validation_groundtruth:", len(os.listdir(validation_groundtruth_dir)))
    test_data = DataLoader(
        validation_dir, validation_groundtruth_dir, image_mode, mask_mode, image_height, image_width, batch_size, seed,
        shear_range, zoom_range, horizontal_flip, vertical_flip, fill_mode)
    test_data = test_data.create_data_generators()
    train_data = DataLoader(
        train_dir, train_groundtruth_dir, image_mode, mask_mode, image_height, image_width, batch_size, seed,
        shear_range, zoom_range, horizontal_flip, vertical_flip, fill_mode)
    train_data = train_data.create_data_generators()
    print("\nPREPROCESSING IMAGES")
    print("\nTRAINING MODEL")
    model, dice_history = train_model_check_accuracy(train_data, test_data)
    # Save Dice coefficient
    save_dice_coefficient_plot(dice_history)
    # Save the trained model to a file
    print("\nSAVING MODEL")
    model.save("my_model.keras")
    print("\nVISUALISING PREDICTIONS")
    test_visualise_model_predictions(model, test_data)

    print("COMPLETED")
    return 0


if __name__ == "__main__":
    main()