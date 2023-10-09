import cv2
import requests
import numpy as np
import datetime
from logger import logger
from config import image_url

# record images of solar panels and write the power text on it.
# source is an esp32-cam


def get_image(left,right, debug = False):
    # Download the image using requests
    try:
        response = requests.get(image_url, timeout=0.5)
    except requests.exceptions.ConnectionError as e:
        logger.log("Image ConnectionError", e)
        return
    except requests.exceptions.Timeout:
        logger.log("Image request timed out")
        return
    except requests.exceptions.RequestException as e:
        logger.log("Image An error occurred:", e)
        return

    if response.status_code == 200:
        # Convert the image data to a NumPy array
        image_data = np.frombuffer(response.content, np.uint8)

        # Read the image using OpenCV
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

        # Define the font settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_color = (0, 0, 255)  # White color in BGR
        font_thickness = 2

        # Add the text to the image
        cv2.putText(image, str(left), (350, 600) , font, font_scale, font_color, font_thickness)  # place text here
        cv2.putText(image, str(right), (700, 600), font, font_scale, font_color, font_thickness)

        now = datetime.datetime.now()
        text = now.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(image, text, (900, 1000), font, font_scale, font_color, font_thickness)

        # Generate a filename with the format "year-month-day-hour-min-sec"
        now = datetime.datetime.now()
        filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg"

        # Save the modified image
        cv2.imwrite(filename, image)

        if debug:
            # Display the image (optional)
            cv2.imshow('Image with Text', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    else:
        print("Failed to download the image.")

if __name__ == '__main__':
    get_image("ooh", "Noooo", True)


    '''
    mport cv2
import numpy as np
import glob
 
img_array = []
for filename in glob.glob('C:/New folder/Images/*.jpg'):
    img = cv2.imread(filename)
    height, width, layers = img.shape
    size = (width,height)
    img_array.append(img)
 
 
out = cv2.VideoWriter('project.avi',cv2.VideoWriter_fourcc(*'DIVX'), 15, size)
 
for i in range(len(img_array)):
    out.write(img_array[i])
out.release()
    '''
