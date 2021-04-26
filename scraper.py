from time import sleep

import os
import subprocess
import requests
from base64 import b64decode

import math
import numpy as np

from iteration_utilities import deepflatten
from requests import ReadTimeout
from url_normalize import url_normalize
from urllib import parse as urlparse

from PIL import Image
import imagehash

SPLASH_ENDPOINT = "http://localhost:8050/"

ACCETED_MIME_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp'
}

DEFAULT_HEADER = {
    'Content-Type': "application/json"
}

THRESHOLD = 2


def tri_matrix(lst, callback, paths=[], images=[]):
    deleted = []
    size = len(lst)
    m = np.zeros((size, size))
    for i in range(1, size):
        for j in range(0, i):
            m[i][j], deleted = callback(i, j, lst, paths=paths, images=images, deleted=deleted)
    return m


def perceptual_hash_cmp(x, y, lst, paths=[], images=[], deleted=[]):

    if x in deleted or y in deleted:
        return -1, deleted

    debug_a = paths[x]
    debug_b = paths[y]
    delta = (lst[x] - lst[y])

    if math.fabs(delta) < THRESHOLD:
        # Delete image with smaller dimensions
        if images[x].size[0]*images[x].size[1] > images[y].size[0]*images[y].size[1]:
            os.remove(paths[y])
            deleted.append(y)
        else:
            os.remove(paths[x])
            deleted.append(x)

    return delta, deleted

# Probably the best scraper i've ever made!
def scrape_har_extract(src, har=True, png=True, wait=3, output_folder='default', verbose=False):
    body = {
        "url": url_normalize(src),
        "wait": wait,
        "har": 1 if har else 0,
        "png": 1 if png else 0,
        "response_body": 1
    }

    try:
        res = requests.post(urlparse.urljoin(SPLASH_ENDPOINT, '/render.json'), headers=DEFAULT_HEADER, json=body, timeout=10)
        content = res.json()
    except ReadTimeout as e:
        print("FAILURE: The webdriver server was not responding (timeout). Ensure the server is working properly.")
        return -1
    except ConnectionError as e:
        print("FAILURE: A network error has occurred. Please check the server's internet connection.")
        return -2

    # Obtain image list from HAR
    entries = content['har']['log']['entries']
    image_requests = [x for x in entries if 'image' in x['response']['content']['mimeType'] and 'response' in x]

    # Create directory structure
    path = f"{output_folder}/"
    if not os.path.isdir(path):
        os.mkdir(path)

    # Download all images and save to machine
    results = []
    counter = 0
    for image in image_requests:
        content = image['response']['content']
        if any(x in content['mimeType'] for x in ACCETED_MIME_TYPES.keys()):
            extension = ACCETED_MIME_TYPES[content['mimeType']]
            filename = f"source_{counter:04}.{extension}"  # urlparse.urlparse(['response']['url']).path.rsplit("/")[-1]

            success = False
            error = None

            try:
                with open(os.path.join(path, filename), 'wb') as f:
                    f.write(b64decode(content['text']))
                    success = True
            except Exception as e:
                error = e

            results.append({
                "url": image['request']['url'],
                "filename": filename,
                "success": success,
                "error": error
            })
            if verbose:
                print(f"{filename} saved")

            counter += 1

    # Handle duplicates

    images = []
    for x in os.listdir(path):
        try:
            images.append(Image.open(os.path.join(path, x)))
        except Exception as e:
            print(e)
    # TODO: If file extension is of image

    try:
        hashes = [imagehash.whash(x) for x in images]
        tri_matrix(hashes, perceptual_hash_cmp, paths=[os.path.join(path, x) for x in os.listdir(path)], images=images)
    except Exception as e:
        print(e)

    return counter


# Requests and saves a working snapshot of the web page.
# Good for detecting background images
def scrape_splash_snap(src):
    params = {
        'url': src,
        'width': 1920,
        'wait': 3,
        'render_all': 1
    }

    print(f"GET {src}")
    return requests.get("http://localhost:8050/render.png", params)


def scrape_images_webdriver(url, output_path=""):
    # TODO: Validate for URL

    # Start webdriver
    driver = {}
    driver.get(url)

    sleep(3)

    # Get all images in DOM
    elements = list(deepflatten([x.get_property("currentSrc") for x in driver.execute_script("return document.images")],
                                types=list))

    # Get a list of all distinctive URL strings (Remove duplicates)
    srcs = []
    [srcs.append(x) for x in elements if x not in srcs]

    # Download image list
    log = []

    for src in srcs:

        success = False

        try:
            # TODO: Modify wget library to avoid overwriting
            code = subprocess.getoutput(f'wget "{src}" --no-check-certificate -T 15 -P {output_path} ')

            if code != 0:
                raise Exception(f"wget failed with code {code}")

            log.append({
                "src": src,
                "success": True,
                "file": os.path.basename(src),
                "error": ""
            })
        except Exception as e:
            print(f"\t'{src}' -> {e}")
            log.append({
                "src": src,
                "success": False,
                "file": "",
                "error": e
            })

    driver.close()

    return log
